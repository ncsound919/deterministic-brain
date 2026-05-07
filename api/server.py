"""FastAPI server — /task /bundle /skills /forge /dashboard /relay /health"""
from __future__ import annotations
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Dict, Optional

from orchestration.dca_engine import DeterministicCodingAgent
from orchestration.swarm_dispatcher import SwarmDispatcher
from tools.forge import Forge, forge_diff
from tools.dashboard import Dashboard
from tools.web_fetcher import web_fetch
from tools.relay import relay, verify_request

app   = FastAPI(title="Deterministic Brain", version="2.2.0")
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
    path:   str   = "/task"
    method: str   = "POST"
    body:   Dict[str, Any] = {}
    verify: bool  = False

class RegisterAgentRequest(BaseModel):
    name:     str
    base_url: str


# ── Core ───────────────────────────────────────────────────────────
@app.post("/task")
def run_task(req: TaskRequest) -> Dict:
    return agent.handle(req.query)

@app.post("/bundle")
def run_bundle(req: BundleRequest) -> Dict:
    return swarm.dispatch(req.bundle, req.inputs)

@app.get("/skills")
def list_skills() -> Dict:
    return {"skills": forge.list_skills()}


# ── Relay ──────────────────────────────────────────────────────────
@app.post("/relay")
def relay_forward(req: RelayRequest) -> Dict:
    """Sign + forward to a named agent."""
    return relay.forward(req.agent, req.path, req.body,
                        req.method, verify_inbound=req.verify)

@app.post("/relay/broadcast")
def relay_broadcast(body: Dict) -> Dict:
    """Forward same payload to all registered agents."""
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

@app.get("/health")
def health() -> Dict:
    return dash.health()


# ── UI ─────────────────────────────────────────────────────────────
@app.get("/")
def serve_ui() -> FileResponse:
    return FileResponse("ui/index.html")
