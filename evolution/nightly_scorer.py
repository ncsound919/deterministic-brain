"""Nightly scoring — daily skill performance audit and evolution trigger.

Designed to run as a scheduled task (cron: 0 2 * * *) via features/scheduler.py.
Calls SkillEvolver.evolve() and writes a report.
"""

from __future__ import annotations
import json
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict

from .skill_evolver import SkillEvolver


class NightlyScorer:
    """Daily scoring: analyses performance, evolves weights, writes report."""

    def __init__(self, evolver: SkillEvolver = None,
                 report_path: str = ".nightly_score_report.json"):
        self.evolver = evolver or SkillEvolver()
        self.report_path = Path(report_path)

    def run_daily_score(self) -> Dict:
        """Score all skills, evolve weights, and return report."""
        now = datetime.now(UTC).isoformat()

        # Evolve weights based on accumulated performance data
        evolved = self.evolver.evolve()

        # Get full stats post-evolution
        all_stats = self.evolver.all_stats()

        # Build report
        report = {
            "timestamp": now,
            "evolved_skills": len(evolved),
            "evolved_details": evolved,
            "all_skills": len(all_stats),
            "top_performers": [s for s in all_stats if s.get("success_rate", 0) > 0.8][:5],
            "low_performers": [s for s in all_stats if s.get("success_rate", 0) < 0.5][:5],
            "deprecated": [s for s in all_stats if s.get("deprecated", False)],
            "weight_distribution": self._weight_histogram(all_stats),
        }

        # Persist report
        self.report_path.write_text(json.dumps(report, indent=2, default=str))
        return report

    def generate_report(self) -> Dict:
        """Return the last nightly report (does not re-run scoring)."""
        if self.report_path.exists():
            try:
                return json.loads(self.report_path.read_text())
            except (json.JSONDecodeError, IOError):
                pass
        return {"status": "never_run"}

    @staticmethod
    def _weight_histogram(stats: list) -> Dict:
        buckets = {"0.0-0.5": 0, "0.5-0.8": 0, "0.8-1.2": 0, "1.2-2.0": 0}
        for s in stats:
            w = s.get("weight", 1.0)
            if w < 0.5:
                buckets["0.0-0.5"] += 1
            elif w < 0.8:
                buckets["0.5-0.8"] += 1
            elif w <= 1.2:
                buckets["0.8-1.2"] += 1
            else:
                buckets["1.2-2.0"] += 1
        return buckets
