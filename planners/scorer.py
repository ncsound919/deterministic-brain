"""DeterministicScorer — replaces math-x as a lean Python scoring tool."""
from __future__ import annotations
import json
import subprocess
from typing import Dict


class DeterministicScorer:
    """
    Scores an execution result across 4 dimensions:
      audit_pass   — did all audit commands pass?       weight 50
      complexity   — cyclomatic complexity via radon    weight 20
      coverage     — pytest-cov % from JSON report      weight 20
      line_count   — penalise bloat (>200 lines)        weight 10

    Returns a 0–100 float. Higher = better.
    """

    WEIGHTS = {"audit_pass": 50, "complexity": 20, "coverage": 20, "line_count": 10}

    def score(self, result: Dict) -> float:
        b = {
            "audit_pass": float(bool(result.get("success"))),
            "complexity": self._complexity(result.get("output", "")),
            "coverage":   self._coverage(),
            "line_count": self._line_count(result.get("output", "")),
        }
        total = sum(b[k] * self.WEIGHTS[k] for k in self.WEIGHTS)
        return round(total, 2)

    # ------------------------------------------------------------------ #

    def _complexity(self, file_path: str) -> float:
        if not file_path:
            return 0.5
        try:
            r = subprocess.run(
                ["radon", "cc", file_path, "--json"],
                capture_output=True, text=True, timeout=10,
            )
            data = json.loads(r.stdout or "{}")
            scores = [b["complexity"] for blocks in data.values() for b in blocks]
            avg = sum(scores) / len(scores) if scores else 1
            return max(0.0, 1.0 - (avg - 1) / 20)
        except Exception:
            return 0.5

    def _coverage(self) -> float:
        try:
            with open(".coverage_report.json") as f:
                return json.load(f).get("totals", {}).get("percent_covered", 0) / 100
        except Exception:
            return 0.0

    def _line_count(self, file_path: str) -> float:
        try:
            with open(file_path) as f:
                n = sum(1 for _ in f)
            return max(0.0, 1.0 - max(0, n - 200) / 300)
        except Exception:
            return 0.5
