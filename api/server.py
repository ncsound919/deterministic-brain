from __future__ import annotations
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import cfg
from orchestration.langgraph_app import build_app
from tools.tracing import get_trace, list_sessions, log_event

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title='Lane-First Deterministic Brain',
    description='Neuro-symbolic AI brain: LangGraph + PyReason + Z3 + MCTS + Qdrant + Neo4j',
    version='1.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

brain = build_app()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    query: str
    lane_override: str | None = None


class RunResponse(BaseModel):
    session_id: str
    lane: str
    status: str
    output_mode: str
    final_output: str
    confidence: float
    tool_calls: list[Any] = []
    verification_results: list[Any] = []
    history_summary: list[str] = []
    elapsed_ms: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get('/health')
def health():
    return {'status': 'ok', 'config': cfg.summary()}


@app.post('/run', response_model=RunResponse)
def run_query(payload: RunRequest) -> RunResponse:
    t0 = time.perf_counter()
    try:
        result = brain.run(payload.query, lane_override=payload.lane_override)
    except Exception as exc:
        log_event('run_error', {'query': payload.query, 'error': str(exc)})
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    log_event('run_complete', {
        'session_id': result.get('session_id', ''),
        'lane': result.get('lane', ''),
        'status': result.get('status', ''),
        'confidence': result.get('confidence', 0),
        'elapsed_ms': elapsed,
    })
    history_summary = [
        h.get('node', h.get('action', '?'))
        for h in result.get('history', [])
    ]
    return RunResponse(
        session_id=result.get('session_id', ''),
        lane=result.get('lane', ''),
        status=result.get('status', ''),
        output_mode=result.get('output_mode', ''),
        final_output=str(result.get('final_output', '')),
        confidence=float(result.get('confidence', 0.0)),
        tool_calls=result.get('tool_calls', []),
        verification_results=result.get('verification_results', []),
        history_summary=history_summary,
        elapsed_ms=elapsed,
    )


# Keep backward-compat /chat alias
@app.post('/chat', response_model=RunResponse)
def chat(payload: RunRequest) -> RunResponse:
    return run_query(payload)


@app.get('/trace/{session_id}')
def trace(session_id: str) -> dict:
    """Return the full reasoning trace for a prior session."""
    result = get_trace(session_id)
    if not result['checkpoints']:
        raise HTTPException(status_code=404, detail=f'No trace found for session {session_id}')
    return result


@app.get('/sessions')
def sessions() -> dict:
    """List all session IDs that have stored traces."""
    return {'sessions': list_sessions()}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('api.server:app', host=cfg.api_host, port=cfg.api_port, reload=False)
