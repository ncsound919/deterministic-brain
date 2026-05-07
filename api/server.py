"""FastAPI server v2.5 — /task /reason /bundle /skills /forge /dashboard /relay /health"""
from __future__ import annotations
import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from orchestration.dca_engine import DeterministicCodingAgent
from orchestration.swarm_dispatcher import SwarmDispatcher
from orchestration.kairos_daemon import (
    get_daemon, start_kairos, stop_kairos,
    kairos_status as _kairos_status,
)
from orchestration.event_bus import event_bus
from brain.autodream import run_autodream
from tools.forge import Forge, forge_diff
from tools.dashboard import Dashboard
from tools.web_fetcher import web_fetch
from tools.relay import relay
from api.middleware import RequestLoggingMiddleware, get_route_stats

# Route modules
from api.routes.settings import router as settings_router
from api.routes.voice import router as voice_router
from api.routes.devpets import router as devpets_router
from api.routes.kairos import router as kairos_router
from api.routes.evolution import router as evolution_router

app   = FastAPI(title="Deterministic Brain", version="2.5.0")
agent = DeterministicCodingAgent()
swarm = SwarmDispatcher()
forge = Forge()
dash  = Dashboard()

# Middleware
app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(RequestLoggingMiddleware)

# Routers
app.include_router(settings_router)
app.include_router(voice_router)
app.include_router(devpets_router)
app.include_router(kairos_router)
app.include_router(evolution_router)


# ── Models ─────────────────────────────────────────────────────────
class TaskRequest(BaseModel):
    query: str
    lane_override: Optional[str] = None

class BundleRequest(BaseModel):
    bundle: str
    inputs: Dict[str, Any] = {}

class DiffRequest(BaseModel):
    old: str
    new: str
    filename: str = "file"

class FetchRequest(BaseModel):
    url: str

class RelayRequest(BaseModel):
    agent:  str
    path:   str  = "/task"
    method: str  = "POST"
    body:   Dict[str, Any] = {}
    verify: bool = False

class RegisterAgentRequest(BaseModel):
    name:     str
    base_url: str

class AutoDreamRequest(BaseModel):
    dry_run: bool = True

class DialogueRequest(BaseModel):
    text: str
    seed: Optional[int] = None


# ── Bundle Definition (Gap 7: validation) ──────────────────────────
class BundleDefinition(BaseModel):
    description: str = ""
    lanes: List[str] = []


# ── Core ───────────────────────────────────────────────────────────
@app.post("/task")
def run_task(req: TaskRequest) -> Dict:
    return agent.handle(req.query)


@app.post("/reason")
def reason_only(req: TaskRequest) -> Dict:
    """Run ONLY the reasoning pipeline — no skill execution."""
    task = agent.parser.parse(req.query)
    enriched = agent.router.enriched_candidates()
    text_to_id = {t: sid for sid, t in enriched}
    enriched_texts = [t for _, t in enriched]

    decision = agent.reasoner.decide(
        task=task,
        skill_candidates=enriched_texts,
        scorer_fn=agent._decision_scorer,
        constraints=agent._build_constraints(task),
        variable_domains=agent._variable_domains(task),
    )
    if decision.chosen_skill and decision.chosen_skill in text_to_id:
        decision.chosen_skill = text_to_id[decision.chosen_skill]
    return {"query": req.query, "task": task, "decision": decision.to_dict()}


@app.post("/bundle")
def run_bundle(req: BundleRequest) -> Dict:
    return swarm.dispatch(req.bundle, req.inputs)


@app.get("/skills")
def list_skills() -> Dict:
    return {"skills": forge.list_skills()}


# ── Bundles (Gap 7: schema validation) ─────────────────────────────
@app.get("/bundles")
def list_bundles() -> Dict[str, List[Dict]]:
    import yaml
    config_path = os.environ.get("SWARM_CONFIG", "swarm.yaml")
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
    except Exception:
        config = {}
    bundles = []
    for name, data in config.get("bundles", {}).items():
        try:
            bd = BundleDefinition(**data)
            bundles.append({"name": name, "description": bd.description, "lanes": bd.lanes})
        except Exception:
            continue  # skip malformed bundle entries
    return {"bundles": bundles}


# ── Relay (Gap 8: broadcast rate limit) ────────────────────────────
@app.post("/relay")
def relay_forward(req: RelayRequest) -> Dict:
    return relay.forward(req.agent, req.path, req.body, req.method, verify_inbound=req.verify)


@app.post("/relay/broadcast")
def relay_broadcast(body: Dict) -> Dict:
    if len(relay.agents) > 10:
        raise HTTPException(status_code=400, detail="Too many registered agents for broadcast (max 10)")
    path = body.pop("path", "/task")
    return relay.broadcast(path, body)


@app.get("/relay/agents")
def relay_agents() -> Dict:
    return {"agents": relay.agents}


@app.post("/relay/register")
def relay_register(req: RegisterAgentRequest) -> Dict:
    relay.register(req.name, req.base_url)
    return {"registered": req.name, "url": req.base_url, "agents": relay.agents}


# ── Forge ──────────────────────────────────────────────────────────
@app.post("/forge/diff")
def diff(req: DiffRequest) -> Dict:
    return forge_diff(req.old, req.new, req.filename)


@app.post("/forge/validate")
def validate(body: Dict) -> Dict:
    return forge.validate_skill(body.get("path", ""))


@app.post("/forge/fetch")
def fetch_url(req: FetchRequest) -> Dict:
    return web_fetch(req.url)


# ── Dashboard ──────────────────────────────────────────────────────
@app.get("/dashboard/feed")
def feed() -> Dict:
    return {"events": dash.recent_events(50)}


@app.get("/dashboard/audit")
def audit() -> Dict:
    return {"events": dash.audit_feed()}


@app.get("/dashboard/stats")
def stats() -> Dict:
    return {"bundles": dash.bundle_stats(), "skills": dash.skill_stats()}


@app.get("/dashboard/middleware-stats")
def middleware_stats_route() -> Dict:
    return {"routes": get_route_stats()}


# ── AutoDream ──────────────────────────────────────────────────────
@app.post("/autodream")
def autodream(req: AutoDreamRequest) -> Dict:
    return run_autodream(dry_run=req.dry_run)


@app.post("/autodream/run")
def autodream_run() -> Dict:
    return run_autodream(dry_run=False)


@app.get("/autodream/status")
def autodream_status() -> Dict:
    path = ".autodream_last_run.json"
    if os.path.exists(path):
        return json.loads(open(path).read())
    return {"status": "never_run"}


# ── Dialogue ───────────────────────────────────────────────────────
@app.post("/dialogue/process")
def dialogue_process(req: DialogueRequest) -> Dict:
    from dialogue import create_dialogue_pipeline

    pipeline = create_dialogue_pipeline(seed=req.seed)
    result = pipeline.process(req.text)
    pipeline.close()

    event_bus.emit("dialogue_turn",
        input_text=req.text, intent=result.intent,
        response=result.response, state=result.state)

    return {
        "response": result.response, "intent": result.intent,
        "confidence": result.intent_confidence, "slots": result.slots,
        "state": result.state, "action": result.action,
        "session_id": result.session_id,
    }


# ── Health ─────────────────────────────────────────────────────────
@app.get("/health")
def health() -> Dict:
    return dash.health()


# ── UI ─────────────────────────────────────────────────────────────
@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse("ui/index.html")
