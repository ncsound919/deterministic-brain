"""Deterministic project organizer for the DCA brain.

Given a goal, produce a structured, deterministic project plan: shape, name,
exports, directory layout with responsibilities, and an ordered task list
(plan -> scaffold -> implement -> test -> verify). Same goal -> same plan.
Zero LLM. The coding lane can then hand the plan to deterministic scaffolders
(Cheetah/BigBack) and the verify gate.

This is the "coding and organizing" surface the brain needs: it turns a messy
goal into an organized, actionable plan before any code is written.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

SHAPES = ("full-stack", "web-app", "api", "python-pkg", "node-lib", "cli", "service", "generic")

_SHAPE_HINTS: List[tuple[str, str]] = [
    ("full-stack", r"\b(full[ -]stack|frontend and backend|spa and api|monorepo)\b"),
    ("web-app", r"\b(web app|website|dashboard|ui|frontend|react|spa)\b"),
    ("api", r"\b(api|rest|crud|endpoint|backend|server|service endpoint)\b"),
    ("cli", r"\b(cli|command[- ]line|terminal tool)\b"),
    ("python-pkg", r"\b(python|pyproject|pip|package)\b"),
    ("node-lib", r"\b(lib|library|module|npm|node|typescript)\b"),
    ("service", r"\b(worker|daemon|cron|job|service)\b"),
]

_STRUCTURE: Dict[str, List[str]] = {
    "full-stack": ["web/src", "web/src/components", "api/src", "api/src/routes", "tests", "docs"],
    "web-app": ["src", "src/components", "src/pages", "public", "tests"],
    "api": ["src", "src/routes", "src/models", "tests"],
    "python-pkg": ["src", "tests", "docs"],
    "node-lib": ["src", "tests"],
    "cli": ["src", "tests"],
    "service": ["src", "workers", "tests", "config"],
    "generic": ["src", "tests", "docs"],
}

_STOP = {"create", "build", "make", "write", "tool", "with", "that", "using", "tests", "test", "the", "and", "for", "app", "api", "rest", "crud", "restful", "endpoint", "server", "web", "cli"}


def detect_shape(goal: str, requested: str | None = None) -> str:
    if requested in SHAPES:
        return requested
    text = (goal or "").lower()
    for shape, pattern in _SHAPE_HINTS:
        if re.search(pattern, text):
            return shape
    return "generic"


def project_name(goal: str, fallback: str = "app") -> str:
    text = goal or ""
    m = re.search(r"\b(?:called|named)\s+[\"']?([A-Za-z][A-Za-z0-9_-]{1,30})", text, re.I)
    if m:
        return m.group(1).lower()
    for m in re.finditer(r"(?:[\w./-]*/)?([A-Za-z_][A-Za-z0-9_-]*)\.[A-Za-z]+", text):
        cand = m.group(1).lower()
        if cand not in ("index", "main", "app", "lib", "src"):
            return cand
    words = re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", text)
    for w in words:
        if w.lower() not in _STOP:
            return w.lower()[:24]
    return fallback


def goal_exports(goal: str, limit: int = 8) -> List[str]:
    text = goal or ""
    found: List[str] = []
    for m in re.finditer(r"\b(?:export(?:ing|s)?|functions?|methods?)\s+([^.;]+)", text, re.I):
        for call in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", m.group(1)):
            if call.group(1) not in found:
                found.append(call.group(1))
    if not found:
        for m in re.finditer(r"\bexport(?:ing|s)?\s+([A-Za-z_][A-Za-z0-9_]*(?:\s*(?:,|\band\b)\s*[A-Za-z_][A-Za-z0-9_]*)+)", text, re.I):
            for tok in re.split(r",|\band\b", m.group(1)):
                tok = tok.strip()
                if tok and tok not in found:
                    found.append(tok)
    return found[:limit]


def organize_goal(goal: str, requested_shape: str | None = None) -> Dict[str, Any]:
    """Deterministic project organization plan. Same goal -> same plan."""
    shape = detect_shape(goal, requested_shape)
    name = project_name(goal)
    exports = goal_exports(goal)
    structure = _STRUCTURE.get(shape, _STRUCTURE["generic"])
    directories = sorted(structure)
    tasks = [
        {"id": 1, "phase": "plan", "task": f"Write the project brief for '{name}' ({shape})"},
        {"id": 2, "phase": "scaffold", "task": f"Scaffold {shape} layout: {', '.join(directories)}"},
        {"id": 3, "phase": "implement", "task": f"Implement core exports: {', '.join(exports) if exports else '(derive from goal)'}"},
        {"id": 4, "phase": "test", "task": "Add tests covering the core exports"},
        {"id": 5, "phase": "verify", "task": "Run the verify gates (typecheck, lint, tests, build)"},
    ]
    return {
        "ok": True,
        "shape": shape,
        "name": name,
        "exports": exports,
        "directories": directories,
        "tasks": tasks,
        "goal": (goal or "").strip()[:500],
        "notes": ["Deterministic plan — same goal yields the same layout and tasks. Zero LLM."],
    }


def render_plan_markdown(plan: Dict[str, Any]) -> str:
    out: List[str] = [
        f"# Project Plan — {plan['name']}",
        "",
        f"- shape: `{plan['shape']}`",
        f"- exports: {', '.join(plan['exports']) or '—'}",
        "",
        "## Layout",
        "",
    ]
    for d in plan["directories"]:
        out.append(f"- `{d}/`")
    out += ["", "## Tasks", ""]
    for t in plan["tasks"]:
        out.append(f"{t['id']}. **{t['phase']}** — {t['task']}")
    out.append("")
    return "\n".join(out)