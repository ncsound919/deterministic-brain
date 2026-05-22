"""Causal context graph — records decisions for attribution queries.

Provides why_this_skill() and failure_attribution() for understanding
what factors influenced the brain's decisions. Persisted to JSONL.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import json
import time
import os
import threading
from collections import defaultdict


@dataclass
class DecisionNode:
    session_id: str
    timestamp: float
    decision_type: str
    factors: Dict[str, float]
    outcome: str
    chosen: str
    confidence: float


class ContextGraph:
    def __init__(self, path: str = ".context_graph.jsonl", max_nodes: int = 10000):
        self._path = path
        self._max_nodes = max_nodes
        self._nodes: List[DecisionNode] = []
        self._lock = threading.Lock()
        self._load()

    def record_decision(
        self,
        session_id: str,
        decision_type: str,
        factors: Dict[str, float],
        outcome: str,
        chosen: str,
        confidence: float,
    ) -> None:
        node = DecisionNode(
            session_id=session_id,
            timestamp=time.time(),
            decision_type=decision_type,
            factors=dict(factors),
            outcome=outcome,
            chosen=chosen,
            confidence=confidence,
        )
        with self._lock:
            self._nodes.append(node)
            self._prune()
        self._append_to_file(node)

    def why_this_skill(self, query: str, skill_id: str) -> Dict:
        with self._lock:
            matching = [
                n for n in self._nodes
                if n.decision_type == "skill_selection"
                and n.chosen == skill_id
                and n.outcome == "accepted"
            ]
        if not matching:
            return {"skill_id": skill_id, "factor_weights": {}, "sample_count": 0}
        agg: Dict[str, float] = {}
        for node in matching:
            for k, v in node.factors.items():
                agg[k] = agg.get(k, 0.0) + v
        n = len(matching)
        return {
            "skill_id": skill_id,
            "factor_weights": {k: round(v / n, 4) for k, v in agg.items()},
            "sample_count": n,
        }

    def failure_attribution(self, session_id: str) -> List[Dict]:
        with self._lock:
            session_nodes = [
                n for n in self._nodes
                if n.session_id == session_id
                and n.outcome in ("rejected", "fallback")
            ]
        if not session_nodes:
            return []
        by_type: Dict[str, List[DecisionNode]] = defaultdict(list)
        for n in session_nodes:
            by_type[n.decision_type].append(n)
        result = []
        for d_type, nodes in by_type.items():
            agg: Dict[str, float] = {}
            for node in nodes:
                for k, v in node.factors.items():
                    agg[k] = agg.get(k, 0.0) + v
            n = len(nodes)
            result.append({
                "decision_type": d_type,
                "count": n,
                "avg_confidence": round(sum(nc.confidence for nc in nodes) / n, 4),
                "factor_weights": {k: round(v / n, 4) for k, v in agg.items()},
            })
        return result

    def prune(self) -> int:
        with self._lock:
            return self._prune_unlocked()

    def _prune_unlocked(self) -> int:
        before = len(self._nodes)
        if before > self._max_nodes:
            self._nodes = self._nodes[-self._max_nodes:]
        return before - len(self._nodes)

    def status(self) -> Dict:
        with self._lock:
            types: Dict[str, int] = {}
            outcomes: Dict[str, int] = {}
            for n in self._nodes:
                types[n.decision_type] = types.get(n.decision_type, 0) + 1
                outcomes[n.outcome] = outcomes.get(n.outcome, 0) + 1
            return {
                "total_nodes": len(self._nodes),
                "max_nodes": self._max_nodes,
                "by_type": types,
                "by_outcome": outcomes,
                "path": self._path,
            }

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    self._nodes.append(DecisionNode(**d))
                except (json.JSONDecodeError, TypeError):
                    continue
        self._prune_unlocked()

    def _append_to_file(self, node: DecisionNode) -> None:
        with open(self._path, "a") as f:
            f.write(json.dumps({
                "session_id": node.session_id,
                "timestamp": node.timestamp,
                "decision_type": node.decision_type,
                "factors": node.factors,
                "outcome": node.outcome,
                "chosen": node.chosen,
                "confidence": node.confidence,
            }) + "\n")

    def _prune(self) -> None:
        if len(self._nodes) > self._max_nodes:
            self._nodes = self._nodes[-self._max_nodes:]


_context_graph: Optional[ContextGraph] = None
_context_graph_lock = threading.Lock()


def get_context_graph(path: str = ".context_graph.jsonl") -> ContextGraph:
    global _context_graph
    if _context_graph is None:
        with _context_graph_lock:
            if _context_graph is None:
                _context_graph = ContextGraph(path)
    return _context_graph
