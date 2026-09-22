"""Coding + organizing lane: organize the goal into a plan, then consult the
Business-Logic-MCP contract for any entities mentioned so the plan carries the
domain constraints before code is written. Honest: if the BLMCP is unreachable
the plan still succeeds with a `contract: unavailable` note — never a fake
contract."""

from __future__ import annotations

import re
import time
from typing import Any, Dict

from planners.project_organizer import organize_goal, render_plan_markdown


def _mentioned_entities(goal: str) -> list[str]:
    """CamelCase words that look like domain entities.

    Drops sentence-initial words (sentence starts are capitalized prose, not
    entities), all-caps acronyms (CRUD, REST, API), and a common-word stoplist.
    """
    sentences = re.split(r"[.!?]\s+", goal or "")
    first_words = {s.split()[0] for s in sentences if s.split()}
    seen: list[str] = []
    for m in re.finditer(r"\b([A-Z][A-Za-z]{2,})\b", goal or ""):
        word = m.group(1)
        if word in first_words or word == word.upper() and len(word) <= 5:
            continue
        if word in ("The", "And", "For", "With", "Web", "App"):
            continue
        if word not in seen:
            seen.append(word)
    return seen


def organize_and_code(goal: str, requested_shape: str | None = None) -> Dict[str, Any]:
    """Deterministic organize + contract-guard lane.

    Returns {ok, plan, contracts, markdown}. Contracts carry the BLMCP verdict
    per entity ({ok, tool, result} or {ok: False, error}) — the caller decides
    whether a missing contract blocks implementation.
    """
    t0 = time.time()
    plan = organize_goal(goal, requested_shape)
    entities = _mentioned_entities(goal)
    contracts: Dict[str, Any] = {}
    if entities:
        try:
            from tools.business_logic_bridge import biz_entity_contract

            for entity in entities:
                contracts[entity] = biz_entity_contract(entity)
        except Exception as exc:  # BLMCP not spawnable/installed
            for entity in entities:
                contracts[entity] = {"ok": False, "error": f"BLMCP unavailable: {exc}"}
    elif not entities:
        contracts = {"_note": "no entity-like names detected in the goal"}

    return {
        "ok": True,
        "goal": goal,
        "plan": plan,
        "contracts": contracts,
        "latency_ms": int((time.time() - t0) * 1000),
        "markdown": render_plan_markdown(plan),
    }