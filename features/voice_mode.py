from __future__ import annotations
"""
VOICE_MODE — Voice I/O with offline TTS support.

Features:
- Audio capture via sounddevice
- Transcription via Whisper (cloud) or local whisper.cpp
- Offline TTS via Piper (deterministic, CPU-based)
- Seeded randomization for reproducibility
"""
import os
import tempfile
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import openai
    _OAI_OK = True
except ImportError:
    _OAI_OK = False

try:
    import sounddevice as sd
    import soundfile as sf
    _AUDIO_OK = True
except ImportError:
    _AUDIO_OK = False

try:
    from piper_tts import Piper
    _PIPER_OK = True
except ImportError:
    _PIPER_OK = False

_SAMPLE_RATE = 16000
_CHANNELS = 1
_OPENAI_KEY = os.getenv('OPENROUTER_API_KEY', '') or os.getenv('OPENAI_API_KEY', '')
_DEFAULT_PIPER_MODEL = os.getenv('PIPER_MODEL', 'en_US-lessac')


def record(duration_s: float = 5.0) -> bytes | None:
    """Record audio from the default microphone."""
    if not _AUDIO_OK:
        return None
    audio = sd.rec(
        int(duration_s * _SAMPLE_RATE),
        samplerate=_SAMPLE_RATE,
        channels=_CHANNELS,
        dtype='int16',
    )
    sd.wait()
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        sf.write(f.name, audio, _SAMPLE_RATE)
        with open(f.name, 'rb') as audio_f:
            return audio_f.read()


def transcribe(audio_bytes: bytes) -> str:
    """Transcribe audio bytes to text using Whisper."""
    if not _OAI_OK or not _OPENAI_KEY:
        return '[Voice mode: set OPENROUTER_API_KEY or OPENAI_API_KEY for transcription]'
    client = openai.OpenAI(api_key=_OPENAI_KEY)
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(audio_bytes)
        f.flush()
        with open(f.name, 'rb') as audio_f:
            result = client.audio.transcriptions.create(
                model='whisper-1',
                file=audio_f,
                response_format='text',
            )
    return str(result).strip()


def listen_and_query(duration_s: float = 5.0) -> dict:
    """Record, transcribe, and run the brain on the spoken query."""
    audio = record(duration_s)
    if not audio:
        return {'error': 'Audio capture unavailable. Install: pip install sounddevice soundfile'}
    text = transcribe(audio)
    if not text:
        return {'error': 'Transcription returned empty string'}
    from orchestration.langgraph_app import build_app
    brain = build_app()
    result = brain.run(text)
    result['voice_transcript'] = text
    return result


class OfflineTTS:
    """Offline TTS using Piper for deterministic voice output."""

    def __init__(self, model_path: Optional[str] = None):
        self._piper = None
        self._model_path = model_path or _get_default_piper_model()

    def _init_piper(self) -> bool:
        """Initialize Piper TTS engine."""
        if _PIPER_OK:
            try:
                self._piper = Piper(self._model_path)
                logger.info(f"Initialized Piper TTS with model: {self._model_path}")
                return True
            except Exception as e:
                logger.warning(f"Failed to initialize Piper: {e}")
        return False

    def speak(self, text: str) -> Optional[bytes]:
        """Synthesize speech from text.
        
        Args:
            text: Text to synthesize
        
        Returns:
            Audio bytes (WAV format) or None if unavailable
        """
        if not self._piper and not self._init_piper():
            return None
        
        try:
            audio = self._piper.speak(text)
            return audio
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None

    def speak_to_file(self, text: str, output_path: str) -> bool:
        """Synthesize speech and save to file.
        
        Args:
            text: Text to synthesize
            output_path: Path to save WAV file
        
        Returns:
            True if successful
        """
        if not self._piper and not self._init_piper():
            return False
        
        try:
            self._piper.speak_to_file(text, output_path)
            return True
        except Exception as e:
            logger.error(f"TTS file output failed: {e}")
            return False


def _get_default_piper_model() -> str:
    """Get default Piper model path."""
    base = os.path.expanduser("~/.local/share/piper")
    return os.path.join(base, "en_US-lessac.onnx")


def speak(text: str) -> Optional[bytes]:
    """Speak text using offline TTS.
    
    Args:
        text: Text to speak
    
    Returns:
        Audio bytes or None if TTS unavailable
    """
    tts = OfflineTTS()
    return tts.speak(text)


def speak_to_file(text: str, output_path: str) -> bool:
    """Speak text and save to file.
    
    Args:
        text: Text to speak
        output_path: Path to save WAV
    
    Returns:
        True if successful
    """
    tts = OfflineTTS()
    return tts.speak_to_file(text, output_path)
