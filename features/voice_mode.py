from __future__ import annotations
"""
VOICE_MODE — Voice input via native audio capture.

Captures microphone input, transcribes via OpenAI Whisper (via OpenRouter
or local whisper.cpp), and injects the transcript as a query to the brain.
"""
import os
import tempfile
from typing import Any

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

_SAMPLE_RATE = 16000
_CHANNELS = 1
_OPENAI_KEY = os.getenv('OPENROUTER_API_KEY', '') or os.getenv('OPENAI_API_KEY', '')


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
