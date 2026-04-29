from __future__ import annotations
"""
ULTRAPLAN — Ultra-detailed planning mode.

Pre-processes every query through a 5-stage deep planning pipeline
before the lane executes:

  1. GOALS       — What does success look like?
  2. CONSTRAINTS — What must NOT happen?
  3. STRATEGY    — Ranked approaches (with pros/cons)
  4. STEPS       — Ordered execution steps with acceptance criteria
  5. RISKS       — What could go wrong and how to mitigate

The plan is stored in working_memory['ultraplan'] and the lane runners
can access it for richer context.
"""
import json
from tools.llm.router import chat

_SYSTEM = """You are an ultra-precise planning engine.
Given a query and lane, produce a comprehensive plan in JSON:
{
  "goals": ["goal1", ...],
  "constraints": ["constraint1", ...],
  "strategy": [{"approach": str, "pros": [str], "cons": [str], "rank": int}],
  "steps": [{"step": int, "action": str, "acceptance_criteria": str}],
  "risks": [{"risk": str, "likelihood": "LOW|MEDIUM|HIGH", "mitigation": str}],
  "estimated_complexity": "LOW|MEDIUM|HIGH|EXTREME"
}"""


def plan(query: str, lane: str, context_snippets: list[str] | None = None) -> dict:
    ctx = '\n'.join(f'- {s[:100]}' for s in (context_snippets or [])[:3])
    user_msg = (
        f'Query: {query}\n'
        f'Lane: {lane}\n'
        + (f'Context:\n{ctx}\n' if ctx else '')
        + '\nProduce the UltraPlan:'
    )
    raw = chat(system=_SYSTEM, user=user_msg, lane=lane, max_tokens=1500)
    try:
        clean = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        return json.loads(clean)
    except Exception:
        return {
            'goals': [query],
            'constraints': [],
            'strategy': [{'approach': 'Direct execution', 'pros': ['Simple'], 'cons': ['Less thorough'], 'rank': 1}],
            'steps': [{'step': 1, 'action': f'Execute {lane} lane', 'acceptance_criteria': 'Output produced'}],
            'risks': [],
            'estimated_complexity': 'MEDIUM',
            'raw': raw[:500],
        }
