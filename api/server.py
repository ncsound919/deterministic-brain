from __future__ import annotations
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import cfg
from features import is_enabled, all_flags, enabled_list
from orchestration.langgraph_app import build_app
from tools.tracing import get_trace, list_sessions, log_event

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title='Lane-First Deterministic Brain',
    description='Neuro-symbolic AI brain: LangGraph + PyReason + Z3 + MCTS + Qdrant + Neo4j + 22 feature modules',
    version='2.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

brain = build_app()

# ---------------------------------------------------------------------------
# Feature startup
# ---------------------------------------------------------------------------

if is_enabled('PROACTIVE'):
    from features.proactive import start as start_proactive
    start_proactive()

if is_enabled('AGENT_TRIGGERS'):
    from features.agent_triggers import start as start_triggers
    start_triggers()

if is_enabled('BRIDGE_MODE'):
    from features.bridge_mode import start as start_bridge
    start_bridge()

if is_enabled('KAIROS_GITHUB_WEBHOOKS'):
    from features.kairos_github_webhooks import handle_webhook, verify_signature, get_results as gh_results

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    query: str
    lane_override: str | None = None
    coordinator: bool = False   # Use COORDINATOR_MODE for this request
    ultraplan: bool = False     # Use ULTRAPLAN for this request


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
    actions: list[Any] = []


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------

@app.get('/health')
def health():
    if is_enabled('MONITOR_TOOL'):
        from features.monitor_tool import health_check
        return health_check()
    return {'status': 'ok', 'config': cfg.summary()}


@app.get('/features')
def features():
    return {'enabled': enabled_list(), 'all': all_flags()}


@app.post('/run', response_model=RunResponse)
def run_query(payload: RunRequest) -> RunResponse:
    t0 = time.perf_counter()

    # TRANSCRIPT_CLASSIFIER
    if is_enabled('TRANSCRIPT_CLASSIFIER'):
        from features.transcript_classifier import classify
        classification = classify(payload.query)
        if classification.get('requires_approval') and classification.get('risk') == 'HIGH':
            raise HTTPException(status_code=403, detail=f'Query classified HIGH risk: {classification["reason"]}')

    # COORDINATOR_MODE
    if payload.coordinator and is_enabled('COORDINATOR_MODE'):
        from features.coordinator_mode import coordinate
        coord_result = coordinate(payload.query)
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return RunResponse(
            session_id='coordinator',
            lane='cross_domain',
            status='ok',
            output_mode='answer',
            final_output=coord_result['final_output'],
            confidence=0.9,
            elapsed_ms=elapsed,
        )

    try:
        result = brain.run(payload.query, lane_override=payload.lane_override)
    except Exception as exc:
        log_event('run_error', {'query': payload.query, 'error': str(exc)})
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    elapsed = round((time.perf_counter() - t0) * 1000, 2)

    # MONITOR_TOOL
    if is_enabled('MONITOR_TOOL'):
        from features.monitor_tool import record_request
        record_request(result.get('lane', ''), elapsed, result.get('confidence', 0), result.get('status', 'ok'))

    # KAIROS
    if is_enabled('KAIROS'):
        from features.kairos import log_turn
        log_turn(payload.query, result.get('final_output', ''), result.get('session_id', ''))

    # EXTRACT_MEMORIES
    if is_enabled('EXTRACT_MEMORIES'):
        from features.extract_memories import extract_async
        extract_async(payload.query, result.get('final_output', ''), result.get('session_id', ''))

    # MESSAGE_ACTIONS
    if is_enabled('MESSAGE_ACTIONS'):
        from features.message_actions import attach
        result = attach(result)

    # KAIROS_CHANNELS
    if is_enabled('KAIROS_CHANNELS'):
        from features.kairos_channels import broadcast
        broadcast(result)

    log_event('run_complete', {
        'session_id': result.get('session_id', ''),
        'lane':       result.get('lane', ''),
        'status':     result.get('status', ''),
        'confidence': result.get('confidence', 0),
        'elapsed_ms': elapsed,
    })

    history_summary = [h.get('node', h.get('action', '?')) for h in result.get('history', [])]
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
        actions=result.get('actions', []),
    )


@app.post('/chat', response_model=RunResponse)
def chat(payload: RunRequest) -> RunResponse:
    return run_query(payload)


# ---------------------------------------------------------------------------
# Trace / session endpoints
# ---------------------------------------------------------------------------

@app.get('/trace/{session_id}')
def trace(session_id: str) -> dict:
    result = get_trace(session_id)
    if not result['checkpoints']:
        raise HTTPException(status_code=404, detail=f'No trace found for session {session_id}')
    return result


@app.get('/sessions')
def sessions() -> dict:
    return {'sessions': list_sessions()}


# ---------------------------------------------------------------------------
# Feature-gated endpoints
# ---------------------------------------------------------------------------

@app.get('/kairos/today')
def kairos_today():
    if not is_enabled('KAIROS'):
        raise HTTPException(status_code=404, detail='KAIROS feature not enabled')
    from features.kairos import get_today
    return get_today()


@app.get('/kairos/{date}')
def kairos_date(date: str):
    if not is_enabled('KAIROS'):
        raise HTTPException(status_code=404, detail='KAIROS feature not enabled')
    from features.kairos import get_date
    return get_date(date)


@app.get('/proactive/results')
def proactive_results():
    if not is_enabled('PROACTIVE'):
        raise HTTPException(status_code=404, detail='PROACTIVE feature not enabled')
    from features.proactive import get_results
    return {'results': get_results()}


@app.post('/proactive/register')
def proactive_register(payload: dict):
    if not is_enabled('PROACTIVE'):
        raise HTTPException(status_code=404, detail='PROACTIVE feature not enabled')
    from features.proactive import register
    return register(payload['query'], payload.get('interval_s', 3600))


@app.get('/triggers')
def triggers_list():
    if not is_enabled('AGENT_TRIGGERS'):
        raise HTTPException(status_code=404, detail='AGENT_TRIGGERS feature not enabled')
    from features.agent_triggers import list_triggers
    return {'triggers': list_triggers()}


@app.post('/triggers/register')
def trigger_register(payload: dict):
    if not is_enabled('AGENT_TRIGGERS'):
        raise HTTPException(status_code=404, detail='AGENT_TRIGGERS feature not enabled')
    from features.agent_triggers import register
    return register(payload['query'], payload.get('cron', '3600'))


@app.post('/coordinator')
def coordinator(payload: dict):
    if not is_enabled('COORDINATOR_MODE'):
        raise HTTPException(status_code=404, detail='COORDINATOR_MODE feature not enabled')
    from features.coordinator_mode import coordinate
    return coordinate(payload['query'], payload.get('max_workers', 4))


@app.post('/review')
def review_artifact(payload: dict):
    if not is_enabled('REVIEW_ARTIFACT'):
        raise HTTPException(status_code=404, detail='REVIEW_ARTIFACT feature not enabled')
    from features.review_artifact import review
    return review(payload['artifact'], payload.get('type', 'code'), payload.get('context', ''))


@app.get('/memory/team')
def team_memory_list():
    if not is_enabled('TEAMMEM'):
        raise HTTPException(status_code=404, detail='TEAMMEM feature not enabled')
    from features.teammem import list_keys
    return {'keys': list_keys()}


@app.post('/memory/team')
def team_memory_write(payload: dict):
    if not is_enabled('TEAMMEM'):
        raise HTTPException(status_code=404, detail='TEAMMEM feature not enabled')
    from features.teammem import write
    return write(payload['key'], payload['value'], payload.get('author', 'api'))


@app.get('/memory/team/{key}')
def team_memory_read(key: str):
    if not is_enabled('TEAMMEM'):
        raise HTTPException(status_code=404, detail='TEAMMEM feature not enabled')
    from features.teammem import read
    entry = read(key)
    if not entry:
        raise HTTPException(status_code=404, detail=f'Key {key} not found')
    return entry


@app.get('/memories')
def memories_list():
    if not is_enabled('EXTRACT_MEMORIES'):
        raise HTTPException(status_code=404, detail='EXTRACT_MEMORIES feature not enabled')
    from features.extract_memories import all_memories
    return {'memories': all_memories()}


@app.get('/skills')
def skills_list():
    if not is_enabled('MCP_SKILLS'):
        raise HTTPException(status_code=404, detail='MCP_SKILLS feature not enabled')
    from features.mcp_skills import list_skills
    return {'skills': list_skills()}


@app.post('/skills/{name}')
def skill_invoke(name: str, payload: dict):
    if not is_enabled('MCP_SKILLS'):
        raise HTTPException(status_code=404, detail='MCP_SKILLS feature not enabled')
    from features.mcp_skills import invoke
    return invoke(name, payload.get('params'), payload.get('query', ''))


@app.get('/monitor')
def monitor():
    if not is_enabled('MONITOR_TOOL'):
        raise HTTPException(status_code=404, detail='MONITOR_TOOL feature not enabled')
    from features.monitor_tool import get_metrics, health_check
    return {'health': health_check(), 'metrics': get_metrics()}


@app.post('/webhooks/github')
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default='ping'),
    x_hub_signature_256: str = Header(default=''),
):
    if not is_enabled('KAIROS_GITHUB_WEBHOOKS'):
        raise HTTPException(status_code=404, detail='KAIROS_GITHUB_WEBHOOKS feature not enabled')
    body = await request.body()
    if not verify_signature(body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail='Invalid webhook signature')
    payload = await request.json()
    return handle_webhook(x_github_event, payload)


@app.get('/webhooks/github/results')
def webhook_results():
    if not is_enabled('KAIROS_GITHUB_WEBHOOKS'):
        raise HTTPException(status_code=404, detail='KAIROS_GITHUB_WEBHOOKS feature not enabled')
    return {'results': gh_results()}


@app.get('/settings')
def settings_get():
    if not is_enabled('DOWNLOAD_USER_SETTINGS'):
        raise HTTPException(status_code=404, detail='DOWNLOAD_USER_SETTINGS feature not enabled')
    from features.download_user_settings import all_settings
    return all_settings()


@app.post('/settings/sync')
def settings_sync(payload: dict):
    if not is_enabled('DOWNLOAD_USER_SETTINGS'):
        raise HTTPException(status_code=404, detail='DOWNLOAD_USER_SETTINGS feature not enabled')
    from features.download_user_settings import sync
    return sync(payload.get('url'))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('api.server:app', host=cfg.api_host, port=cfg.api_port, reload=False)
