"""Hybrid Confidence Stacking — multi-layer ensemble scorer with adaptive weights.

Layer 1 (Deterministic): Rule-based/Z3-verified logic (default weight 0.6)
Layer 2 (Semantic): Knowledge bank fragment similarity (default weight 0.25)
Layer 3 (Evidence): Session history success rate (default weight 0.15)

Adaptive weights: if fallback is triggered frequently for a route, L1 weight
decreases and L2/L3 weights increase, biasing toward more evidence.
"""
from __future__ import annotations
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from pydantic import BaseModel


class ConfidenceResult(BaseModel):
    data: Any
    confidence: float
    fallback_triggered: bool = False
    error: Optional[str] = None
    layer_scores: Optional[Dict[str, float]] = None
    weights_used: Optional[Dict[str, float]] = None


@dataclass
class RouteStats:
    name: str
    total_calls: int = 0
    fallback_count: int = 0
    last_fallback_ts: float = 0.0
    layer1_weight: float = 0.6
    layer2_weight: float = 0.25
    layer3_weight: float = 0.15


class MultiLayerConfidenceRouter:
    """Multi-layer confidence router with adaptive weights.

    Routes:
      run query → primary_fn → (result, L1_score) → if L1 >= threshold → return
      L2_score = semantic_similarity (from knowledge bank)
      L3_score = historical_success_rate (from state_manager)
      final = w1*L1 + w2*L2 + w3*L3
      if final >= threshold → return primary result
      else → trigger fallback
    """

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold
        self.routes: Dict[str, Dict] = {}
        self._stats: Dict[str, RouteStats] = {}
        self._default_weights = {"layer1": 0.6, "layer2": 0.25, "layer3": 0.15}
        self._lock = threading.Lock()

    def register_route(
        self,
        name: str,
        primary_fn: Callable[[Any], Tuple[Any, float]],
        fallback_fn: Callable[[Any], Any],
        semantic_fn: Optional[Callable[[Any], float]] = None,
        evidence_fn: Optional[Callable[[Any], float]] = None,
    ):
        with self._lock:
            self.routes[name] = {
                "primary": primary_fn,
                "fallback": fallback_fn,
                "semantic": semantic_fn or (lambda x: 0.5),
                "evidence": evidence_fn or (lambda x: 0.5),
            }
            if name not in self._stats:
                self._stats[name] = RouteStats(name=name)

    def _get_weights(self, route_name: str) -> Dict[str, float]:
        stats = self._stats.get(route_name)
        if not stats:
            return dict(self._default_weights)
        return {
            "layer1": stats.layer1_weight,
            "layer2": stats.layer2_weight,
            "layer3": stats.layer3_weight,
        }

    def _adapt_weights(self, route_name: str) -> None:
        """Decrease L1 weight if fallback triggered frequently."""
        with self._lock:
            stats = self._stats.get(route_name)
            if not stats or stats.total_calls < 5:
                return
            fallback_rate = stats.fallback_count / stats.total_calls
            if fallback_rate > 0.3:
                stats.layer1_weight = max(0.3, stats.layer1_weight - 0.05)
                stats.layer2_weight = min(0.4, stats.layer2_weight + 0.03)
                stats.layer3_weight = min(0.3, stats.layer3_weight + 0.02)
            elif fallback_rate < 0.05:
                stats.layer1_weight = min(0.8, stats.layer1_weight + 0.02)
                stats.layer2_weight = max(0.15, stats.layer2_weight - 0.01)
                stats.layer3_weight = max(0.05, stats.layer3_weight - 0.01)

    def execute(
        self,
        route_name: str,
        input_data: Any,
        semantic_score: Optional[float] = None,
        evidence_score: Optional[float] = None,
    ) -> ConfidenceResult:
        with self._lock:
            if route_name not in self.routes:
                raise ValueError(f"Route {route_name} not found.")
            route = dict(self.routes[route_name])
            weights = self._get_weights(route_name)

        # Layer 1: Deterministic primary
        try:
            result_data, l1_score = route["primary"](input_data)
        except Exception:
            result_data = None
            l1_score = 0.0

        # Layer 2: Semantic (from knowledge bank)
        l2_score = semantic_score if semantic_score is not None else route["semantic"](input_data)

        # Layer 3: Evidence (from session history)
        l3_score = evidence_score if evidence_score is not None else route["evidence"](input_data)

        final = weights["layer1"] * l1_score + weights["layer2"] * l2_score + weights["layer3"] * l3_score

        layer_scores = {"layer1": round(l1_score, 4), "layer2": round(l2_score, 4),
                        "layer3": round(l3_score, 4), "final": round(final, 4)}

        with self._lock:
            stats = self._stats.setdefault(route_name, RouteStats(name=route_name))
            stats.total_calls += 1

            if final >= self.threshold and result_data is not None:
                return ConfidenceResult(
                    data=result_data,
                    confidence=final,
                    layer_scores=layer_scores,
                    weights_used=weights,
                )

            stats.fallback_count += 1
            stats.last_fallback_ts = time.time()

        self._adapt_weights(route_name)

        try:
            fallback_data = route["fallback"](input_data)
            return ConfidenceResult(
                data=fallback_data,
                confidence=final,
                fallback_triggered=True,
                layer_scores=layer_scores,
                weights_used=weights,
            )
        except Exception as e:
            return ConfidenceResult(
                data=None,
                confidence=0.0,
                fallback_triggered=True,
                error=str(e),
                layer_scores=layer_scores,
                weights_used=weights,
            )

    def route_stats(self) -> List[Dict]:
        with self._lock:
            return [
                {
                    "name": s.name,
                    "total_calls": s.total_calls,
                    "fallback_count": s.fallback_count,
                    "fallback_rate": round(s.fallback_count / max(s.total_calls, 1), 4),
                    "weights": {
                        "layer1": round(s.layer1_weight, 3),
                        "layer2": round(s.layer2_weight, 3),
                        "layer3": round(s.layer3_weight, 3),
                    },
                }
                for s in self._stats.values()
            ]

    def status_summary(self) -> Dict:
        with self._lock:
            return {
                "threshold": self.threshold,
                "default_weights": self._default_weights,
                "routes": [
                    {
                        "name": s.name,
                        "total_calls": s.total_calls,
                        "fallback_count": s.fallback_count,
                        "fallback_rate": round(s.fallback_count / max(s.total_calls, 1), 4),
                        "weights": {
                            "layer1": round(s.layer1_weight, 3),
                            "layer2": round(s.layer2_weight, 3),
                            "layer3": round(s.layer3_weight, 3),
                        },
                    }
                    for s in self._stats.values()
                ],
                "total_routes": len(self.routes),
            }


# Backward-compatible alias
ConfidenceRouter = MultiLayerConfidenceRouter
