from __future__ import annotations
from typing import Any, Dict, List, Literal
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    query: str = Field(min_length=1)
    session_id: str | None = None

class ChatResponse(BaseModel):
    lane: Literal['coding', 'business_logic', 'agent_brain', 'tool_calling', 'cross_domain']
    status: Literal['ok', 'needs_clarification', 'retry', 'failed']
    output_mode: Literal['clarify', 'answer', 'plan', 'code', 'action']
    final_output: str
    confidence: float
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    verification_results: List[Dict[str, Any]] = Field(default_factory=list)
