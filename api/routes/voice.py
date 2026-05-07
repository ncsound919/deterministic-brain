"""Voice routes — STT, TTS, and WebSocket streaming."""
from __future__ import annotations
import struct
from fastapi import APIRouter, WebSocket, HTTPException
from typing import Dict
import numpy as np

router = APIRouter(prefix="/voice", tags=["voice"])

_voice_mode = None


def _get_voice():
    global _voice_mode
    if _voice_mode is None:
        from dialogue.voice_mode import VoiceMode
        _voice_mode = VoiceMode(seed=42)
    return _voice_mode


@router.get("/status")
def voice_status() -> Dict:
    return {
        "status": "ready",
        "stt": "faster-whisper (tiny.en)",
        "tts": "piper-tts (en_US-lessac-medium)",
        "stream": "ws://localhost:8000/voice/stream",
    }


@router.post("/transcribe")
async def voice_transcribe(body: Dict) -> Dict:
    """Transcribe base64 PCM audio to text using faster-whisper."""
    import base64
    vm = _get_voice()
    raw = body.get("audio", "")
    if not raw:
        return {"text": "", "error": "No audio data"}
    try:
        audio_bytes = base64.b64decode(raw)
        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        text = vm.transcriber.transcribe(audio_np, sample_rate=16000)
        return {"text": text, "confidence": 0.9 if text else 0.0}
    except Exception as e:
        return {"text": "", "error": str(e)}


@router.post("/speak")
async def voice_speak(body: Dict) -> bytes:
    """Synthesize text to WAV audio using piper-tts."""
    from fastapi.responses import Response
    vm = _get_voice()
    text = body.get("text", "")
    if not text:
        return Response(content=vm.synthesizer.synthesize("No text provided."),
                        media_type="audio/wav")
    audio = vm.synthesizer.synthesize(text)
    return Response(content=audio, media_type="audio/wav")


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    """Real-time voice streaming — mic → STT → pipeline → TTS → speaker."""
    await websocket.accept()
    vm = _get_voice()
    vm.reset()
    try:
        while True:
            data = await websocket.receive()
            if data["type"] == "websocket.disconnect":
                break
            if "bytes" in data:
                audio_bytes = data["bytes"]
                audio_np = (np.frombuffer(audio_bytes, dtype=np.int16)
                             .astype(np.float32) / 32768.0)
                text = vm.add_audio_chunk(audio_np)
                if text:
                    result = vm.process(text)
                    await websocket.send_json({
                        "type": "transcription", "text": text,
                        "dialogue": result.get("dialogue", {}),
                    })
                    audio_wav = vm.synthesizer.synthesize(result["response"])
                    await websocket.send_bytes(audio_wav)
    except Exception:
        pass
    finally:
        vm.close()
