from __future__ import annotations
from typing import Any, Dict, List, Literal, TypedDict

LaneName = Literal['coding', 'business_logic', 'agent_brain', 'tool_calling', 'cross_domain']
OutputMode = Literal['clarify', 'answer', 'plan', 'code', 'action']

class ContextItem(TypedDict, total=False):
    source: str
    id: str
    text: str
    score: float
    metadata: Dict[str, Any]

class ToolCall(TypedDict, total=False):
    tool: str
    args: Dict[str, Any]
    approved: bool

class Verdict(TypedDict, total=False):
    stage: str
    passed: bool
    reason: str
    details: Dict[str, Any]

class BrainState(TypedDict, total=False):
    session_id: str
    query: str
    lane: LaneName
    goal_stack: List[str]
    permission_context: Dict[str, Any]
    working_memory: Dict[str, Any]
    retrieved_contexts: List[ContextItem]
    graph_refs: List[str]
    tool_budget: Dict[str, Any]
    browser_sessions: Dict[str, Any]
    candidate_artifacts: List[Dict[str, Any]]
    tool_calls: List[ToolCall]
    verification_results: List[Verdict]
    history: List[Dict[str, Any]]
    confidence: float
    output_mode: OutputMode
    final_output: str
    status: Literal['ok', 'needs_clarification', 'retry', 'failed']
