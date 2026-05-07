"""Evolution + Health Monitor routes — skill scoring, evolution, health checks."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from typing import Dict

from orchestration.kairos_daemon import kairos_status as _kairos_status
from orchestration.event_bus import event_bus

router = APIRouter(tags=["evolution"])


# ── Health Monitor ─────────────────────────────────────────────

@router.get("/health/monitor")
def health_monitor() -> Dict:
    """Aggregated health: daemon, circuit breakers, evolution, error rate."""
    circuits, heals = [], []
    try:
        from orchestration.runtime_healer import runtime_healer
        circuits = runtime_healer.all_circuit_states()
        heals = runtime_healer.recent_heals(10)
    except Exception as e:
        return {"error": f"RuntimeHealer: {e}", "circuit_breakers": [],
                "recent_heals": [], "skills_health": [], "error_rate": None}

    skills = []
    try:
        from evolution.skill_evolver import SkillEvolver
        evolver = SkillEvolver()
        skills = evolver.all_stats()
    except Exception as e:
        return {"error": f"SkillEvolver: {e}", "daemon": _kairos_status(),
                "circuit_breakers": circuits, "recent_heals": heals,
                "skills_health": [], "error_rate": None}

    total_runs = sum(s.get("runs", 0) for s in skills)
    total_successes = sum(s["runs"] * s.get("success_rate", 0) for s in skills)
    error_rate = round(1 - (total_successes / max(total_runs, 1)), 4)

    return {
        "daemon": _kairos_status(),
        "circuit_breakers": circuits,
        "recent_heals": heals,
        "skills_health": skills[:10],
        "error_rate": error_rate,
        "total_skills_tracked": len(skills),
        "last_evolve": max((s.get("last_run_ts", 0) for s in skills), default=0),
    }


@router.get("/health/heals")
def health_heals(limit: int = 20) -> Dict:
    """Recent heal events."""
    try:
        from orchestration.runtime_healer import runtime_healer
        return {"heals": runtime_healer.recent_heals(limit)}
    except Exception:
        return {"heals": []}


@router.get("/health/skills")
def health_skills() -> Dict:
    """Per-skill health."""
    try:
        from evolution.skill_evolver import SkillEvolver
        return {"skills": SkillEvolver().all_stats()}
    except Exception:
        return {"skills": []}


# ── Evolution ──────────────────────────────────────────────────

@router.post("/evolution/nightly-score")
def nightly_score() -> Dict:
    """Run daily skill scoring and evolution."""
    try:
        from evolution import NightlyScorer
        scorer = NightlyScorer()
        report = scorer.run_daily_score()
        event_bus.emit("evolution_ran", evolved_skills=report["evolved_skills"])
        return report
    except ImportError as e:
        raise HTTPException(status_code=501, detail=str(e))


@router.get("/evolution/report")
def evolution_report() -> Dict:
    """Get last nightly score report."""
    try:
        from evolution import NightlyScorer
        return NightlyScorer().generate_report()
    except ImportError:
        return {"status": "module_not_available"}
