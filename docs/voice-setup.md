# Voice Setup

The voice stack uses **faster-whisper** (STT) and **piper-tts** (TTS) — both fully offline.

## Prerequisites

```bash
pip install -r requirements-voice.txt
```

## piper-tts (Platform-Specific)

piper-tts is a compiled C/Rust binary with Python bindings. Pre-built wheels exist for:
- Linux x86_64, aarch64
- macOS x86_64, arm64
- Windows x86_64

Install matching your platform:
```bash
pip install piper-tts
```

## Download Voice Model

piper-tts requires a voice model file (.onnx + .json). Download one:

```bash
python -c "
from piper.download_voices import download_voice
from pathlib import Path
download_voice('en_US-lessac-medium', Path('piper_voices'))
"
```

Available voice qualities (size/quality tradeoff):
- `en_US-lessac-low` (~30MB, fastest)
- `en_US-lessac-medium` (~50MB, balanced)
- `en_US-lessac-high` (~100MB, best quality)
- `en_US-amy-medium` (~50MB, female voice)

## Verify

```bash
python -c "
from dialogue.voice_mode import VoiceTranscriber, VoiceSynthesizer
stt = VoiceTranscriber('tiny.en')
tts = VoiceSynthesizer()
print('Voice stack ready')
"
```

First-run will download the whisper model (~75MB for tiny.en, ~150MB for base.en).

## WebSocket Streaming

The `WS /voice/stream` endpoint handles real-time audio. The browser sends PCM 16-bit 16kHz mono chunks.

No additional server setup needed — audio processing runs on the server CPU.
