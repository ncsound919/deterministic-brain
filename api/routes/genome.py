"""Genome council compounding routes.

Exposes the *local* deterministic genome council (`reasoning/dev_brain.py`) and
its durable compounding ledger (`reasoning/genome_ledger.py`) over HTTP.

These are distinct from the external dev-brain proxy (`/advisory/dev-brain/*`,
which forwards to DEV_BRAIN_URL:3450). This router is the deterministic-brain's
own council: LLM-free, fully reproducible, and able to persist the believability
adjustments and lessons that let it compound toward better decisions across
restarts.

Routes
------
POST  /genome-council/decide        run one council over the learned weights
POST  /genome-council/post-mortem   record an outcome -> persist weight + lessons
GET   /genome-council/state         ledger overview + learned weights
GET   /genome-council/lessons       recent lessons learned
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from reasoning.dev_brain import load_genomes
from reasoning.genome_ledger import get_genome_ledger, run_council
from reasoning.post_mortem import PostMortemCalibrationEngine

router = APIRouter(tags=["genome-council"])

Outcome = Literal["success", "partial", "failure"]


class DecideRequest(BaseModel):
    problem: str = Field(min_length=1)
    selected_genomes: Optional[List[str]] = None
    active_sectors: Optional[List[str]] = None


class PostMortemRequest(BaseModel):
    decision_title: str = Field(min_length=1)
    sector: str = "dev"
    chosen_option: str = ""
    predicted_probability: float = Field(ge=0.0, le=1.0)
    actual_outcome: Outcome
    leader_ids: List[str] = Field(min_length=1)
    metric_variances: List[Dict[str, Any]] = Field(default_factory=list)
    root_causes: List[str] = Field(default_factory=list)
    key_lessons: List[str] = Field(default_factory=list)
    retrospective_summary: str = ""


# --------------------------------------------------------------- helpers

def _resolve_genomes(
    req: DecideRequest,
) -> List[str]:
    canon = load_genomes()
    if req.selected_genomes is None or len(req.selected_genomes) == 0:
        return list(canon.keys())
    missing = [k for k in req.selected_genomes if k not in canon]
    if missing:
        raise HTTPException(status_code=422, detail=f"unknown genomes: {missing}")
    return list(req.selected_genomes)


# ----------------------------------------------------------------- decide

@router.post("/genome-council/decide")
def council_decide(req: DecideRequest) -> Dict[str, Any]:
    """Run the deterministic genome council over *learned* believability."""
    selected = _resolve_genomes(req)
    return run_council(
        req.problem,
        selected,
        active_sectors=req.active_sectors,
        ledger=get_genome_ledger(),
    )


# ------------------------------------------------------------- post-mortem

@router.post("/genome-council/post-mortem")
def council_post_mortem(req: PostMortemRequest) -> Dict[str, Any]:
    """Record a real outcome and persist the compounding response.

    Computes a Brier-scored post-mortem, applies the guarded believability step
    for each named leader, stores the lessons that leader contributed, and
    returns the traceable record + before/after weights. Durable across
    restarts via the ledger file."""
    ledger = get_genome_ledger()
    canon = load_genomes()
    missing = [k for k in req.leader_ids if k not in canon]
    if missing:
        raise HTTPException(status_code=422, detail=f"unknown genomes: {missing}")

    actual_binary = (
        1.0 if req.actual_outcome == "success"
        else 0.5 if req.actual_outcome == "partial"
        else 0.0
    )
    pm = PostMortemCalibrationEngine()
    brier = pm.calculate_brier_score(req.predicted_probability, actual_binary)
    rating = pm.get_calibration_rating(
        brier, req.predicted_probability, actual_binary
    )

    adjustments: List[Dict[str, Any]] = []
    reasoning_id = f"council-{int(time.time() * 1000)}"
    reason = (
        f"Outcome calibration: {req.actual_outcome.upper()} (Brier {brier}) "
        f"on \"{req.decision_title}\"."
    )

    for leader_id in req.leader_ids:
        genome = canon[leader_id]
        current = ledger.current_believability(
            leader_id, float(genome["believabilityWeight"])
        )
        new_weight = ledger.apply_adjustment(
            genome_id=leader_id,
            current_weight=current,
            actual_outcome=req.actual_outcome,
            reason=reason,
            reasoning_id=reasoning_id,
            sector=req.sector,
        )
        adjustments.append({
            "leaderId": leader_id,
            "leaderName": genome["name"],
            "sector": genome["sector"],
            "currentBelievability": round(current, 4),
            "recommendedBelievability": new_weight,
            "delta": round(new_weight - current, 4),
            "reason": reason,
        })

    leader = canon[req.leader_ids[0]]
    lessons_stored = ledger.add_lessons(
        key_lessons=req.key_lessons,
        actual_outcome=req.actual_outcome,
        leader_id=req.leader_ids[0],
        sector=req.sector,
        decision_title=req.decision_title,
    )

    record = {
        "id": f"pm-{format(int(time.time() * 1000), 'x')}",
        "decisionTitle": req.decision_title,
        "sector": req.sector,
        "status": req.actual_outcome,
        "chosenOption": req.chosen_option,
        "predictedProbability": req.predicted_probability,
        "actualOutcomeBinary": actual_binary,
        "brierScore": brier,
        "calibrationRating": rating,
        "metricVariances": req.metric_variances,
        "rootCauses": req.root_causes,
        "keyLessons": req.key_lessons,
        "suggestedAdjustments": adjustments,
        "retrospectiveSummary": req.retrospective_summary,
        "primaryLeader": leader["name"],
    }
    ledger.add_record(record)

    return {
        "record": record,
        "adjustments_applied": len(adjustments),
        "lessons_stored": len(lessons_stored),
        "durable": True,
        "ledger_path": str(ledger.storage_path),
        "overview": ledger.overview(),
    }


# --------------------------------------------------------------- state

@router.get("/genome-council/state")
def council_state() -> Dict[str, Any]:
    """Ledger overview plus every genome's current learned believability."""
    ledger = get_genome_ledger()
    canon = load_genomes()
    learned = {
        gid: ledger.current_believability(
            gid, float(canon[gid]["believabilityWeight"])
        )
        for gid in canon
    }
    return {
        **ledger.overview(),
        "learned_weights": learned,
    }


@router.get("/genome-council/lessons")
def council_lessons(limit: int = 20) -> Dict[str, Any]:
    """Recent lessons the council has learned."""
    ledger = get_genome_ledger()
    return {
        "lessons": ledger.recent_lessons(limit=limit),
        "total": len(ledger.all_lessons()),
    }
