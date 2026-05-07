from __future__ import annotations
"""
BRIDGE_MODE — VS Code / JetBrains IDE bridge.

Exposes a local HTTP server that IDE extensions can call to:
- Send selected code + query to the brain
- Receive diffs/code suggestions
- Get inline completions

Running on a separate port (default 8001) from the main API.
"""
import os
import threading
from typing import Any

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
    import uvicorn
    _OK = True
except ImportError:
    _OK = False

_PORT = int(os.getenv('BRIDGE_PORT', '8001'))
_app: Any = None
_thread: threading.Thread | None = None


class BridgeRequest(BaseModel):
    query: str
    selected_code: str = ''
    file_path: str = ''
    language: str = 'python'
    action: str = 'explain'  # explain | refactor | complete | review


class BridgeResponse(BaseModel):
    output: str
    lane: str
    confidence: float
    diff: str = ''


def _build_bridge_app():
    app = FastAPI(title='Deterministic Brain IDE Bridge', version='1.0.0')

    @app.post('/bridge', response_model=BridgeResponse)
    def bridge(payload: BridgeRequest):
        from orchestration.langgraph_app import build_app
        brain = build_app()
        query = payload.query
        if payload.selected_code:
            query = f'{payload.action} the following {payload.language} code:\n```\n{payload.selected_code}\n```\n\n{payload.query}'
        result = brain.run(query, lane_override='coding' if payload.selected_code else None)
        return BridgeResponse(
            output=result.get('final_output', ''),
            lane=result.get('lane', 'coding'),
            confidence=result.get('confidence', 0.0),
        )

    @app.get('/bridge/health')
    def health():
        return {'status': 'ok', 'mode': 'bridge'}

    return app


def start() -> None:
    global _app, _thread
    if not _OK:
        return
    _app = _build_bridge_app()
    _thread = threading.Thread(
        target=lambda: uvicorn.run(_app, host='127.0.0.1', port=_PORT, log_level='warning'),
        daemon=True,
    )
    _thread.start()


def get_port() -> int:
    return _PORT
