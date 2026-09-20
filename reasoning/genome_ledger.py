"""Genome council durable compounding ledger.

The genome council (`reasoning/dev_brain.py`) ranks genomes by a static
`believabilityWeight` baked into `data/dev_brain_genomes.json`. Post-mortem
outcomes (`reasoning/post_mortem.py`) compute believability adjustments but
mutate only an in-memory dict, so the council never actually compounds across
restarts: a hard-won lesson about a leader's pattern was forgotten on reboot.

This module makes that loop real and durable:

  * A `GenomeLedger` persists three things to `data/genome_ledger.json`:
      - `adjustments`  — every believability weight change with a reason,
                         reasoning_id and timestamp (fully traceable).
      - `records`      — the post-mortem outcome records that drove them.
      - `lessons`      — the key lessons learned, each tagged with the
                         leader/verdict it came from.
  * `overlays()` returns genome_id -> current learned believability (the last
    adjustment wins). `build_council_engine()` returns a council whose genomes
    carry the overlay, so every decide sees the compounded weights.
  * `apply_outcome()` turns a single post-mortem outcome into a guarded,
    persisted believability adjustment AND stores its lessons, so they feed
    forward into the next council.

Honesty contract (same ethos as `post_mortem.py`):
  * Deterministic and LLM-free: same outcome + same current weight => same
    new weight, same audit entry. No randomness, no calibrated guesswork.
  * Every write is clamped to [WEIGHT_MIN, WEIGHT_MAX] and logged before it
    happens. Nothing silently mutates canon; adjustments live in the ledger and
    *overlay* canon only at decision time.
  * Weight deltas are the fixed outcome step (success +DELTA_SUCCESS, failure
    -DELTA_FAILURE, partial 0.0) already defined by `post_mortem.py` — reused,
    not re-invented.
"""

from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from reasoning.dev_brain import DeterministicReasoningEngine, load_genomes

# Mirrors the clamp + step semantics in reasoning/post_mortem.py
WEIGHT_MIN = 0.5
WEIGHT_MAX = 1.0
DELTA_SUCCESS = 0.01
DELTA_FAILURE = 0.02
DELTA_PARTIAL = 0.0

_LEDGER_PATH = Path(__file__).resolve().parents[1] / "data" / "genome_ledger.json"

_MAX_RECORDS = 500
_MAX_LESSONS = 500
_MAX_ADJUSTMENTS = 5000


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _clamp(weight: float) -> float:
    return round(min(WEIGHT_MAX, max(WEIGHT_MIN, weight)), 4)


def _delta_for(actual_outcome: str) -> float:
    return (
        DELTA_SUCCESS
        if actual_outcome == "success"
        else -DELTA_FAILURE
        if actual_outcome == "failure"
        else DELTA_PARTIAL
    )


class GenomeLedger:
    """Durable store of genome-council compounding (belieavability + lessons)."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = Path(storage_path or _LEDGER_PATH)
        self.adjustments: List[Dict[str, Any]] = []
        self.records: List[Dict[str, Any]] = []
        self.lessons: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._load()

    # ------------------------------------------------------------ persistence

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            return
        self.adjustments = list(raw.get("adjustments", []) or [])
        self.records = list(raw.get("records", []) or [])
        self.lessons = list(raw.get("lessons", []) or [])

    def _save(self) -> None:
        with self._lock:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "adjustments": self.adjustments,
                "records": self.records,
                "lessons": self.lessons,
                "saved_ts": time.time(),
            }
            tmp = self.storage_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.storage_path)

    # -------------------------------------------------------------- read

    def overlays(self) -> Dict[str, float]:
        """genome_id -> current learned believability (last adjustment wins)."""
        out: Dict[str, float] = {}
        # adjustments is newest-first; iterate oldest->newest so the most recent
        # adjustment is applied last and therefore wins.
        for adj in reversed(self.adjustments):
            out[adj["genome_id"]] = float(adj["to_weight"])
        return out

    def current_believability(self, genome_id: str, fallback: float) -> float:
        return self.overlays().get(genome_id, float(fallback))

    def all_records(self) -> List[Dict[str, Any]]:
        return list(self.records)

    def all_lessons(self) -> List[Dict[str, Any]]:
        return list(self.lessons)

    def recent_lessons(self, limit: int = 20) -> List[Dict[str, Any]]:
        return list(self.lessons[:max(1, limit)])

    def relevant_lessons(
        self,
        problem: str,
        selected_genomes: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Deterministic keyword-priority pick of lessons that bear on `problem`.

        Cautionary (failure) lessons for a genome that is itself being
        consulted rank first, then failure lessons for any selected genome,
        then the most recent lessons. Pure + reproducible."""
        selected = set(selected_genomes or [])
        p_lower = problem.lower()

        def score(lesson: Dict[str, Any]) -> float:
            s = 0.0
            gid = lesson.get("leader_id")
            if lesson.get("verdict") == "failure":
                s += 3.0
            if gid and gid in selected:
                s += 2.0
            text = " ".join(
                str(lesson.get(k, "")) for k in ("text", "decision_title")
            ).lower()
            if text and any(tok in p_lower for tok in (gid or "").lower().split("-")
                            if len(tok) > 2):
                s += 1.0
            return s

        ranked = sorted(
            (l for l in self.lessons if score(l) > 0),
            key=score,
            reverse=True,
        )
        return ranked[: max(1, limit)]

    # -------------------------------------------------------------- write

    def apply_adjustment(
        self,
        genome_id: str,
        current_weight: float,
        actual_outcome: str,
        reason: str,
        reasoning_id: str,
        sector: str = "dev",
    ) -> float:
        """Persist one guarded believability step and return the new weight."""
        delta = _delta_for(actual_outcome)
        to_weight = _clamp(current_weight + delta)
        self.adjustments.insert(0, {
            "genome_id": genome_id,
            "from_weight": round(float(current_weight), 4),
            "to_weight": to_weight,
            "delta": delta,
            "actual_outcome": actual_outcome,
            "reason": reason,
            "reasoning_id": reasoning_id,
            "sector": sector,
            "timestamp": _now(),
        })
        if len(self.adjustments) > _MAX_ADJUSTMENTS:
            self.adjustments = self.adjustments[:_MAX_ADJUSTMENTS]
        self._save()
        return to_weight

    def add_record(self, record: Dict[str, Any]) -> None:
        self.records.insert(0, record)
        if len(self.records) > _MAX_RECORDS:
            self.records = self.records[:_MAX_RECORDS]
        self._save()

    def add_lessons(
        self,
        key_lessons: List[str],
        actual_outcome: str,
        leader_id: str = "",
        sector: str = "dev",
        decision_title: str = "",
    ) -> List[Dict[str, Any]]:
        added: List[Dict[str, Any]] = []
        ts = _now()
        for text in key_lessons:
            lesson = {
                "id": f"lesson-{format(int(time.time() * 1000), 'x')}-{len(added)}",
                "text": text,
                "verdict": actual_outcome,
                "leader_id": leader_id,
                "sector": sector,
                "decision_title": decision_title,
                "timestamp": ts,
            }
            self.lessons.insert(0, lesson)
            added.append(lesson)
        if len(self.lessons) > _MAX_LESSONS:
            self.lessons = self.lessons[:_MAX_LESSONS]
        self._save()
        return added

    # ---------------------------------------------------------- overview

    def overview(self) -> Dict[str, Any]:
        applied = self.adjustments
        completed = [r for r in self.records if r.get("status") != "pending"]
        if completed:
            mean_brier = sum(float(r["brierScore"]) for r in completed) / len(completed)
            success = len(
                [r for r in completed if float(r.get("actualOutcomeBinary", 0)) >= 0.8]
            )
            accuracy = round(success / len(completed) * 100, 1)
        else:
            mean_brier, accuracy = 0.0, 0.0
        return {
            "ledger_path": str(self.storage_path),
            "adjustments_applied": len(applied),
            "genomes_with_learned_weight": len(self.overlays()),
            "records_logged": len(self.records),
            "lessons_learned": len(self.lessons),
            "mean_brier": round(mean_brier, 4),
            "accuracy_rate": accuracy,
        }


def build_council_engine(
    ledger: Optional[GenomeLedger] = None,
    genomes: Optional[Dict[str, Dict[str, Any]]] = None,
) -> DeterministicReasoningEngine:
    """Return a council whose genomes carry the ledger's compounded weights.

    Canon is never mutated: we deep-copy the loaded genomes and apply the
    overlay over `believabilityWeight` so `rank_genomes_by_relevance` weighs
    what the brain has actually learned, not the static baseline."""
    ledger = ledger or get_genome_ledger()
    base = genomes if genomes is not None else load_genomes()
    merged: Dict[str, Dict[str, Any]] = {}
    for key, genome in base.items():
        g = copy.deepcopy(genome)
        learned = ledger.overlays().get(key)
        if learned is not None:
            g["believabilityWeight"] = learned
        merged[key] = g
    return DeterministicReasoningEngine(genomes=merged)


def run_council(
    problem: str,
    selected_genomes: List[str],
    active_sectors: Optional[List[str]] = None,
    ledger: Optional[GenomeLedger] = None,
) -> Dict[str, Any]:
    """Run one deterministical council over the *learned* genome weights.

    Output is the usual traceable FSM result plus:
      - `belief`: the current durable believability per consulted genome
        (source = ledger, never the static baseline).
      - `lessonsApplied`: the recent/ relevant lessons that informed context,
        so a decision transparently shows what the brain has learned."""
    ledger = ledger or get_genome_ledger()
    engine = build_council_engine(ledger=ledger)
    result = engine.reason_about_problem(problem, selected_genomes, active_sectors)
    belief = {
        gid: float(engine.genomes[gid]["believabilityWeight"])
        for gid in selected_genomes
        if gid in engine.genomes
    }
    result["belief_source"] = "ledger"
    result["belief"] = belief
    result["lessonsApplied"] = ledger.relevant_lessons(
        problem, selected_genomes=selected_genomes, limit=5
    )
    return result


_ledger_singleton: Optional[GenomeLedger] = None
_ledger_lock = threading.Lock()


def get_genome_ledger() -> GenomeLedger:
    """Module-level singleton bound to the repo's durable ledger file."""
    global _ledger_singleton
    if _ledger_singleton is None:
        with _ledger_lock:
            if _ledger_singleton is None:
                _ledger_singleton = GenomeLedger()
    return _ledger_singleton
