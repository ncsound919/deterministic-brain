"""priority_engine.py

Lightweight Priority Engine that consolidates Policy gating, Bandit
preferences, and BM25 semantic ranking into a single scoring adapter.

This is intentionally conservative: it wraps existing systems and
provides a small API for `score_candidates()` and `choose()` so the
orchestrator can optionally call a single named component.
"""
from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Tuple

from reasoning.policy_engine import get_policy_engine
from reasoning.contextual_bandit import get_bandit
from reasoning.math_engine import BM25Ranker


class PriorityEngine:
    """Compose policy, bandit, and ranker signals into a priority score.

    Candidates format (recommended):
        {"id": "arm_or_skill_id", "text": "human readable","arm_id": "..."}

    Returns list of (candidate, score, gate_result) sorted by score desc.
    """

    def __init__(self, policy_engine=None, bandit=None, ranker=None):
        self.pe = policy_engine or get_policy_engine()
        self.bandit = bandit or get_bandit()
        self.ranker = ranker or BM25Ranker()

    def score_candidates(self, candidates: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Tuple[Dict, float, Any]]:
        if not candidates:
            return []

        # Prepare texts for BM25 if available
        texts = [c.get("text", c.get("description", str(c.get("id", "")))) for c in candidates]
        query = context.get("query") or context.get("raw", "")
        bm25_scores = []
        try:
            ranked = self.ranker.rank_texts(query, texts)
            # ranked returns list of (text, score) in same order as input mapping
            # convert to scores aligned with candidates order
            bm25_scores = [s for (_, s) in ranked]
            # If BM25 returned fewer entries, pad
            if len(bm25_scores) < len(candidates):
                bm25_scores = bm25_scores + [0.0] * (len(candidates) - len(bm25_scores))
        except Exception:
            bm25_scores = [0.0] * len(candidates)

        # Normalise BM25
        max_b = max(bm25_scores) if bm25_scores else 0.0
        bm25_norm = [(s / max_b) if max_b > 0 else 0.0 for s in bm25_scores]

        scored = []
        for i, c in enumerate(candidates):
            decision = {"arm_id": c.get("arm_id") or c.get("id"), "channel": c.get("channel")}
            gate = self.pe.gate(decision, context)
            allowed = 1 if gate.is_allowed else 0

            # Bandit signal
            arm_id = c.get("arm_id") or c.get("id")
            try:
                arm = self.bandit.get_arm(arm_id)
                bandit_q = arm.q_value if arm is not None else 0.5
            except Exception:
                bandit_q = 0.5

            bm = bm25_norm[i] if i < len(bm25_norm) else 0.0

            # Composite: prefer policy (block -> zero), then bandit + bm25 blend
            composite = float(allowed) * (0.6 * bandit_q + 0.4 * bm)

            scored.append((c, round(composite, 4), gate))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def choose(self, candidates: List[Dict[str, Any]], context: Dict[str, Any]) -> Optional[Tuple[Dict, float, Any]]:
        scored = self.score_candidates(candidates, context)
        return scored[0] if scored else None


__all__ = ["PriorityEngine"]
