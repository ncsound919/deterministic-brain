"""Integrated no-LLM build lane: organize -> design (JEV via OG-Glass) ->
backend generation (BigBack) -> optional acceptance gate (Beta Team).

Every step is deterministic and honest: a step that cannot run (server offline,
SDK missing) reports its real status (SKIP/ERROR + detail) and never fabricates
output. The DESIGN.md contract from OG-Glass is attached to the plan so a
frontend generator follows the same design system end to end.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from planners.project_organizer import organize_goal, render_plan_markdown

DEFAULT_BACKEND_SCHEMA = """\
entity Item {
  id string pk
  name string
  description string optional
}
"""


def _step(step: str, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"step": step, **result}


def design_and_build(
    goal: str,
    requested_shape: Optional[str] = None,
    backend_schema: Optional[str] = None,
    framework: str = "fastapi",
    run_beta: bool = False,
) -> Dict[str, Any]:
    """Run the integrated lane. Returns {ok, plan, steps[], design_md, backend,
    beta, markdown}. `ok` is true when the plan + at least one generation step
    ran; missing fleet servers are reported per-step, never fatal to the plan."""
    from tools.fleet_bridges import bigback_generate, og_glass_brief, beta_team_run, fleet_status

    t0 = time.time()
    plan = organize_goal(goal, requested_shape)
    steps: List[Dict[str, Any]] = []

    # 1. Design direction (JEV via OG-Glass REST)
    design = og_glass_brief(goal)
    steps.append(_step("design", design))
    design_md: Optional[str] = None
    refined_design_md: Optional[str] = None
    preset_id: Optional[str] = None
    quality_passed: Optional[bool] = None
    refinement: Optional[Dict[str, Any]] = None
    if design.get("ok"):
        preset_id = design.get("preset_resolved")
        quality_passed = design.get("quality", {}).get("passed")
        design_md = design.get("design_md")
        refined = design.get("refined") or {}
        refined_design_md = refined.get("refined_design_md")
        if refined.get("strategy"):
            refinement = {"strategy": refined.get("strategy"), "math_report": refined.get("math_report"), "quality": refined.get("refined_quality")}

    # 2. Backend generation (BigBack REST)
    spec: Dict[str, Any] = {
        "project": plan["name"],
        "framework": framework,
        "schema": backend_schema or DEFAULT_BACKEND_SCHEMA,
        "goal": goal,
    }
    backend = bigback_generate(spec)
    steps.append(_step("backend", backend))

    # 3. Optional acceptance gate (Beta Team) — needs a built app on disk
    beta: Dict[str, Any] = {"ok": False, "step": "beta", "status": "SKIP", "error": "skipped (run_beta=False)"}
    if run_beta:
        beta = beta_team_run(f"out/{plan['name']}", kind="web")
    steps.append(beta)

    ok = plan["ok"] and (design.get("ok") or backend.get("ok"))
    return {
        "ok": ok,
        "goal": goal,
        "plan": plan,
        "design": {"preset_id": preset_id, "quality_passed": quality_passed, "source": design.get("source")},
        "design_md": design_md,
        "refined_design_md": refined_design_md,
        "refinement": refinement,
        "backend": {"framework": framework, "files": len(backend.get("files", [])) if backend.get("ok") else 0, "ok": backend.get("ok")},
        "beta": {"status": beta.get("status")},
        "steps": steps,
        "fleet": fleet_status(),
        "latency_ms": int((time.time() - t0) * 1000),
        "markdown": render_plan_markdown(plan),
    }