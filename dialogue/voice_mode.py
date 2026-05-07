"""Voice mode — real STT/TTS with faster-whisper + piper-tts.

Architecture:
    Browser mic (MediaRecorder) → WS /voice/stream → VoiceMode
    ├─ Audio chunks (PCM 16kHz mono) → faster-whisper → text
    ├─ Text → DialoguePipeline → response text + backend action
    └─ Response text → piper-tts → WAV bytes → browser speaker

Intent routing:
    run_task    → agent.handle(query)
    run_bundle  → swarm.dispatch(bundle, inputs)
    relay       → relay.forward(agent, path, body)
    kairos_*    → kairos start/stop/status
    devpet_*    → DevPetTracker
    autodream   → run_autodream(dry_run)
    query_*     → dashboard queries
"""

from __future__ import annotations
import io
import time
import wave
import threading
from pathlib import Path
from typing import Any, Dict, Optional, List

import numpy as np

from dialogue import create_dialogue_pipeline, DialoguePipeline, DialogueResult
from orchestration.event_bus import event_bus


# ── STT: faster-whisper ────────────────────────────────────────

class VoiceTranscriber:
    """Offline STT using faster-whisper (4x faster than openai-whisper)."""

    def __init__(self, model_size: str = "tiny.en"):
        """
        Args:
            model_size: tiny.en (~75MB), base.en (~150MB), small.en (~500MB)
                       smaller = faster, larger = more accurate
        """
        self.model_size = model_size
        self._model = None
        self._lock = threading.Lock()

    @property
    def model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size, device="cpu", compute_type="int8"
            )
        return self._model

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe raw audio samples to text.

        Args:
            audio_data: float32 numpy array, shape (n_samples,)
            sample_rate: sample rate in Hz (default 16000)

        Returns:
            Transcribed text string
        """
        if len(audio_data) < sample_rate * 0.3:  # < 0.3 seconds, skip
            return ""

        with self._lock:
            segments, _ = self.model.transcribe(
                audio_data.astype(np.float32),
                language="en",
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    threshold=0.5,
                ),
            )
            text = " ".join(s.text.strip() for s in segments)
        return text


# ── TTS: piper-tts ─────────────────────────────────────────────

class VoiceSynthesizer:
    """Offline neural TTS using piper-tts."""

    def __init__(self, voice_model: str = "en_US-lessac-medium"):
        """
        Args:
            voice_model: piper voice name (e.g., en_US-lessac-medium)
        """
        self.voice_name = voice_model
        self._voice = None
        self._lock = threading.Lock()

    @property
    def voice(self):
        if self._voice is None:
            from piper import PiperVoice
            model_path = Path("piper_voices") / f"{self.voice_name}.onnx"
            if not model_path.exists():
                raise FileNotFoundError(
                    f"Voice model not found: {model_path}. Run: "
                    f"python -c \"from piper.download_voices import download_voice; "
                    f"download_voice('{self.voice_name}', Path('piper_voices'))\""
                )
            self._voice = PiperVoice.load(str(model_path))
        return self._voice

    def synthesize(self, text: str) -> bytes:
        """
        Convert text to WAV audio bytes.

        Args:
            text: Text to synthesize

        Returns:
            WAV file bytes (16-bit PCM, 22050 Hz mono)
        """
        if not text.strip():
            return self._silence_wav(0.1)

        with self._lock:
            audio = b""
            for chunk in self.voice.synthesize_stream_raw(text):
                audio += chunk

        # Wrap raw PCM in WAV container
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(22050)
            wf.writeframes(audio)
        return wav_buffer.getvalue()

    def synthesize_raw(self, text: str) -> bytes:
        """Return raw PCM bytes (no WAV header) — for streaming."""
        if not text.strip():
            return b""
        audio = b""
        for chunk in self.voice.synthesize_stream_raw(text):
            audio += chunk
        return audio

    @staticmethod
    def _silence_wav(duration_s: float) -> bytes:
        frames = int(duration_s * 22050)
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            wf.writeframes(b"\x00\x00" * frames)
        return wav_buffer.getvalue()


# ── Voice Mode (orchestrates STT → Pipeline → TTS) ─────────────

class VoiceMode:
    """Orchestrates voice input through dialogue pipeline to backend actions."""

    def __init__(self, seed: Optional[int] = None):
        self.pipeline: DialoguePipeline = create_dialogue_pipeline(seed)
        self.transcriber = VoiceTranscriber(model_size="tiny.en")
        self.synthesizer = VoiceSynthesizer()
        self._backends: Dict[str, callable] = {}
        self._session_id = f"voice_{int(time.time())}"
        self._audio_buffer: List[np.ndarray] = []
        self._buffer_samples = 0

    def register_backend(self, intent_key: str, handler: callable) -> None:
        """Register a handler for a specific intent routing key."""
        self._backends[intent_key] = handler

    def add_audio_chunk(self, audio_data: np.ndarray) -> Optional[str]:
        """
        Add an audio chunk to the buffer. Returns transcribed text
        if enough audio has accumulated, otherwise None.
        """
        self._audio_buffer.append(audio_data)
        self._buffer_samples += len(audio_data)

        # Transcribe when we have ~2 seconds of audio
        sample_rate = 16000
        if self._buffer_samples >= sample_rate * 2:
            combined = np.concatenate(self._audio_buffer)
            self._audio_buffer.clear()
            self._buffer_samples = 0
            return self.transcriber.transcribe(combined, sample_rate)
        return None

    def process(self, text: str) -> Dict[str, Any]:
        """
        Run speech input through the full pipeline and route to backend.

        Returns:
            dict with response text, backend result, and dialogue metadata
        """
        if not text.strip():
            return {"response": "I didn't catch that.", "result": None, "dialogue": {}}

        # Step 1: Dialogue pipeline
        dialogue_result: DialogueResult = self.pipeline.process(text)

        # Step 2: Route intent to backend
        backend_result = self._route_intent(dialogue_result)

        # Step 3: Build final response
        response_text = dialogue_result.response or ""
        if backend_result and isinstance(backend_result, dict):
            status = backend_result.get("status", "ok")
            if status == "ok":
                response_text += " Task completed successfully."
            elif status == "failed":
                response_text += (
                    f" Task failed: {backend_result.get('error', 'unknown error')}")
            elif status == "blocked":
                response_text += " Task was blocked by pre-audit checks."

        # Step 4: Emit event
        event_bus.emit("voice_turn",
            session_id=self._session_id,
            input_text=text,
            intent=dialogue_result.intent,
            response=response_text,
        )

        return {
            "response": response_text,
            "result": backend_result,
            "dialogue": {
                "intent": dialogue_result.intent,
                "confidence": dialogue_result.intent_confidence,
                "slots": dialogue_result.slots,
                "state": dialogue_result.state,
                "action": dialogue_result.action,
            },
        }

    def process_and_speak(self, text: str) -> Dict[str, Any]:
        """Process text and return result with synthesized audio bytes."""
        result = self.process(text)
        result["audio"] = self.synthesizer.synthesize(result["response"])
        return result

    def _route_intent(self, result: DialogueResult) -> Optional[Dict]:
        """Route the dialogue result intent to the appropriate backend handler."""
        intent = result.intent
        text = result.normalized_text or result.input_text
        slots = result.slots or {}

        handler = self._backends.get(intent)
        if handler:
            return handler(text=text, slots=slots, result=result)

        if intent in ("command", "statement"):
            action = slots.get("action", text)
            obj = slots.get("object", "")
            query = f"{action} {obj}".strip()
            handler = self._backends.get("run_task")
            if handler:
                return handler(text=query, slots=slots, result=result)

        return {"status": "unrouted", "intent": intent,
                "message": f"No handler for intent: {intent}"}

    def reset(self) -> None:
        self.pipeline.reset()
        self._session_id = f"voice_{int(time.time())}"
        self._audio_buffer.clear()
        self._buffer_samples = 0

    def close(self) -> None:
        self.pipeline.close()


def create_default_voice_mode() -> VoiceMode:
    """Create a VoiceMode with default backend handlers."""
    return VoiceMode(seed=42)
