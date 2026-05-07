"""Skill evolver — tracks performance and adjusts routing weights automatically.

Reads autodream corrections, execution results, and success/failure events
to evolve skill weights over time. Higher-performing skills get higher weights.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from .weight_store import WeightStore


class SkillEvolver:
    """Tracks per-skill performance and adjusts weights based on success rate."""

    def __init__(self, perf_path: str = ".skill_performance.json",
                 weight_store: Optional[WeightStore] = None):
        self.path = Path(perf_path)
        self.weights = weight_store or WeightStore()
        self._data: Dict = self._load()
        self.min_samples = 10  # minimum runs before evolving

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, default=str))

    def track(self, skill_id: str, success: bool, latency_ms: float = 0.0,
              confidence: float = 0.0) -> None:
        entry = self._data.setdefault(skill_id, {
            "runs": 0, "successes": 0, "total_latency": 0.0,
            "total_confidence": 0.0, "weight": self.weights.get(skill_id),
            "last_evolved_ts": 0, "last_run_ts": time.time(),
        })
        entry["runs"] += 1
        if success:
            entry["successes"] += 1
        entry["total_latency"] += latency_ms
        entry["total_confidence"] += confidence
        entry["last_run_ts"] = time.time()
        self._save()

    def evolve(self) -> List[Dict]:
        """Adjust weights for all skills with >= min_samples."""
        results = []
        for skill_id, entry in self._data.items():
            if entry["runs"] < self.min_samples:
                continue
            old_weight = self.weights.get(skill_id)
            success_rate = entry["successes"] / max(entry["runs"], 1)
            # Blend: 70% old weight, 30% success rate
            new_weight = round(old_weight * 0.7 + success_rate * 0.3, 4)
            # Clamp to [0.1, 2.0]
            new_weight = max(0.1, min(2.0, new_weight))
            self.weights.set(skill_id, new_weight)
            entry["weight"] = new_weight
            entry["last_evolved_ts"] = time.time()
            results.append({
                "skill_id": skill_id,
                "old_weight": old_weight,
                "new_weight": new_weight,
                "success_rate": round(success_rate, 4),
                "runs": entry["runs"],
            })
        self._save()
        return results

    def deprecate(self, skill_id: str) -> None:
        """Mark a skill as deprecated (weight → 0)."""
        self.weights.set(skill_id, 0.0)
        if skill_id in self._data:
            self._data[skill_id]["weight"] = 0.0
            self._data[skill_id]["deprecated"] = True
        self._save()

    def suggest_alternative(self, skill_id: str) -> Optional[str]:
        """Suggest highest-weight alternative for a failing skill."""
        weights = self.weights.all_weights()
        if skill_id in weights:
            del weights[skill_id]
        if not weights:
            return None
        return max(weights, key=weights.get)

    def get_stats(self, skill_id: str) -> Optional[Dict]:
        entry = self._data.get(skill_id)
        if not entry:
            return None
        runs = max(entry.get("runs", 1), 1)
        return {
            "skill_id": skill_id,
            "runs": runs,
            "success_rate": round(entry.get("successes", 0) / runs, 4),
            "avg_latency_ms": round(entry.get("total_latency", 0) / runs, 1),
            "avg_confidence": round(entry.get("total_confidence", 0) / runs, 4),
            "weight": self.weights.get(skill_id),
            "deprecated": entry.get("deprecated", False),
            "last_run_ts": entry.get("last_run_ts", 0),
        }

    def all_stats(self) -> List[Dict]:
        result = []
        for skill_id in self._data:
            stats = self.get_stats(skill_id)
            if stats:
                result.append(stats)
        return sorted(result, key=lambda s: s["weight"], reverse=True)
