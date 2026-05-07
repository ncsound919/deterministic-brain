"""FastAPI MCP-compatible server — exposes DCA as a JSON-RPC tool endpoint."""
from __future__ import annotations
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional

from orchestration.dca_engine import DeterministicCodingAgent
from orchestration.swarm_dispatcher import SwarmDispatcher

app   = FastAPI(title="Deterministic Brain", version="2.0.0")
agent = DeterministicCodingAgent()
swarm = SwarmDispatcher()


class TaskRequest(BaseModel):
    query: str
    lane_override: Optional[str] = None


class BundleRequest(BaseModel):
    bundle: str
    inputs: Dict[str, Any] = {}


@app.post("/task")
def run_task(req: TaskRequest) -> Dict:
    """Run a single natural-language task through the DCA engine."""
    return agent.handle(req.query)


@app.post("/bundle")
def run_bundle(req: BundleRequest) -> Dict:
    """Fire a full swarm bundle by name."""
    return swarm.dispatch(req.bundle, req.inputs)


@app.get("/skills")
def list_skills() -> Dict:
    """List all indexed skill.md files."""
    return {"skills": list(agent.skills.keys())}


@app.get("/health")
def health() -> Dict:
    return {"status": "ok", "llm": False, "deterministic": True}
