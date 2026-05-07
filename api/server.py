"""FastAPI server v2.3 — /task /reason /bundle /skills /forge /dashboard /relay /health"""
from __future__ import annotations
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional

from orchestration.dca_engine import DeterministicCodingAgent
from orchestration.swarm_dispatcher import SwarmDispatcher
from orchestration.kairos_daemon import get_daemon, start_kairos, stop_kairos, kairos_status
from brain.autodream import run_autodream
from tools.forge import Forge, forge_diff
from tools.dashboard import Dashboard
from tools.web_fetcher import web_fetch
from tools.relay import relay

app   = FastAPI(title="Deterministic Brain", version="2.3.0")
agent = DeterministicCodingAgent()
swarm = SwarmDispatcher()
forge = Forge()
dash  = Dashboard()

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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


# ── Core ───────────────────────────────────────────────────────────
@app.post("/task")
def run_task(req: TaskRequest) -> Dict:
    """Parse → Reason → Execute. Returns full state including reasoning trace."""
    return agent.handle(req.query)


@app.post("/reason")
def reason_only(req: TaskRequest) -> Dict:
    """
    Run ONLY the reasoning pipeline — no skill execution.
    Returns the full DecisionResult breakdown so the UI can show
    chosen_skill, chosen_config, confidence, pre_audit, and step trace
    before anything is written to disk.
    """
    task = agent.parser.parse(req.query)
    decision = agent.reasoner.decide(
        task             = task,
        skill_candidates = list(agent.skills.keys()),
        scorer_fn        = agent._decision_scorer,
        constraints      = agent._build_constraints(task),
        variable_domains = agent._variable_domains(task),
    )
    return {
        "query":    req.query,
        "task":     task,
        "decision": decision.to_dict(),
    }


@app.post("/bundle")
def run_bundle(req: BundleRequest) -> Dict:
    return swarm.dispatch(req.bundle, req.inputs)

@app.get("/skills")
def list_skills() -> Dict:
    return {"skills": forge.list_skills()}


# ── Relay ──────────────────────────────────────────────────────────
@app.post("/relay")
def relay_forward(req: RelayRequest) -> Dict:
    return relay.forward(req.agent, req.path, req.body,
                         req.method, verify_inbound=req.verify)

@app.post("/relay/broadcast")
def relay_broadcast(body: Dict) -> Dict:
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

# ── autoDream ────────────────────────────────────────────────
@app.post("/autodream/run")
def autodream_run() -> Dict:
    return run_autodream(dry_run=False)

@app.get("/autodream/status")
def autodream_status() -> Dict:
    import os
    path = ".autodream_last_run.json"
    if os.path.exists(path):
        import json
        return json.loads(open(path).read())
    return {"status": "never_run"}


# ── KAIROS ───────────────────────────────────────────────────
@app.post("/kairos/start")
def kairos_start() -> Dict:
    return start_kairos()

@app.post("/kairos/stop")
def kairos_stop() -> Dict:
    return stop_kairos()

@app.get("/kairos/status")
def kairos_status_endpoint() -> Dict:
    return kairos_status()

@app.get("/kairos/today")
def kairos_today() -> Dict:
    from features.kairos import get_today
    return get_today()

@app.get("/kairos/{date}")
def kairos_date(date: str) -> Dict:
    from features.kairos import get_date
    return get_date(date)

@app.get("/kairos/stats")
def kairos_stats() -> Dict:
    from features.kairos import get_stats
    return get_stats()

@app.get("/health")
def health() -> Dict:
    return dash.health()


# ── UI ─────────────────────────────────────────────────────────────
@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse("ui/index.html")
