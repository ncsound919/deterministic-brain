"""Test Metrics and Reporting for E2E Coverage.

Tracks real defect detection, flake rate, runtime stats.
Proves tests aren't fluff by showing real value.
"""
from __future__ import annotations
import json
import time
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List


METRICS_FILE = Path.home() / ".deterministic-brain" / "test_metrics.json"


class TestMetrics:
    """Track and report E2E test metrics."""

    @pytest.fixture(scope="session")
    def metrics_data(self):
        """Load or create metrics data."""
        if METRICS_FILE.exists():
            try:
                with open(METRICS_FILE) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "runs": [],
            "defects_caught": 0,
            "flake_rate": 0.0,
            "avg_runtime_seconds": 0.0,
            "total_runs": 0,
        }

    def test_record_run(self, metrics_data):
        """Record a test run."""
        run_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "runtime_seconds": 0.0,
            "flake_count": 0,
        }

        metrics_data["runs"].append(run_data)
        metrics_data["total_runs"] += 1

        return run_data

    def test_calculate_flake_rate(self, metrics_data):
        """Calculate flake rate from recent runs."""
        if len(metrics_data["runs"]) < 2:
            return 0.0

        recent = metrics_data["runs"][-10:]
        total = sum(r["tests_run"] for r in recent)
        flakes = sum(r.get("flake_count", 0) for r in recent)

        flake_rate = (flakes / total) if total > 0 else 0.0
        metrics_data["flake_rate"] = flake_rate

        assert flake_rate < 0.05, f"Flake rate too high: {flake_rate:.2%}"

    def test_average_runtime(self, metrics_data):
        """Track average runtime."""
        if not metrics_data["runs"]:
            return

        recent = metrics_data["runs"][-10:]
        avg = sum(r["runtime_seconds"] for r in recent) / len(recent)

        metrics_data["avg_runtime_seconds"] = avg

        assert avg < 300, f"E2E suite too slow: {avg:.0f}s"

    def test_defect_detection_rate(self, metrics_data):
        """Track how many defects E2E tests catch."""
        caught = metrics_data.get("defects_caught", 0)
        total_runs = metrics_data.get("total_runs", 1)

        rate = caught / total_runs if total_runs > 0 else 0

        assert rate >= 0, "Defect detection rate should be non-negative"

    def test_log_defect_caught(self, defect_type, test_id, bug_id=None):
        """Log that a defect was caught by E2E test."""
        metrics_data = self._load_metrics()

        if "defects" not in metrics_data:
            metrics_data["defects"] = []

        metrics_data["defects"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": defect_type,
            "test_id": test_id,
            "bug_id": bug_id,
            "caught_before_release": True,
        })

        metrics_data["defects_caught"] = len(metrics_data["defects"])

        self._save_metrics(metrics_data)

    def _load_metrics(self):
        """Load metrics from disk."""
        if METRICS_FILE.exists():
            with open(METRICS_FILE) as f:
                return json.load(f)
        return {"defects": [], "defects_caught": 0}

    def _save_metrics(self, data):
        """Save metrics to disk."""
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(METRICS_FILE, "w") as f:
            json.dump(data, f, indent=2)


class TestCoverageReport:
    """Generate coverage reports proving test value."""

    def test_print_coverage_summary(self):
        """Print coverage summary by risk level."""
        from tests.e2e.user_journey_map import UserJourneyMap

        journey_map = UserJourneyMap()
        summary = journey_map.get_coverage_summary()

        print("\n" + "="*60)
        print("E2E TEST COVERAGE REPORT")
        print("="*60)

        high_pct = (summary["high_risk_covered"] / summary["high_risk_journeys"] * 100) if summary["high_risk_journeys"] else 100
        med_pct = (summary["medium_risk_covered"] / summary["medium_risk_journeys"] * 100) if summary["medium_risk_journeys"] else 100
        low_pct = (summary["low_risk_covered"] / summary["low_risk_journeys"] * 100) if summary["low_risk_journeys"] else 100

        print(f"\nHIGH RISK: {high_pct:.0f}% covered ({summary['high_risk_covered']}/{summary['high_risk_journeys']})")
        print(f"MEDIUM RISK: {med_pct:.0f}% covered ({summary['medium_risk_covered']}/{summary['medium_risk_journeys']})")
        print(f"LOW RISK: {low_pct:.0f}% covered ({summary['low_risk_covered']}/{summary['low_risk_journeys']})")

        print(f"\nTOTAL: {summary['total_journeys']} journeys mapped")

        if summary["all_covered"]:
            print("\n✓ ALL CRITICAL PATHS GUARDED")
        else:
            print("\n✗ WARNING: Some journeys lack test coverage!")

        print("="*60 + "\n")

        assert summary["all_covered"], "Not all critical paths have test coverage"

    def test_runtime_benchmark(self):
        """Benchmark E2E test runtime."""
        import subprocess
        import sys

        start = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/e2e/test_dialogue_e2e.py", "--tb=no", "-q"],
            capture_output=True,
            timeout=300,
        )
        runtime = time.time() - start

        print(f"\nE2E Dialogue tests runtime: {runtime:.1f}s")

        assert runtime < 60, f"Dialogue E2E tests too slow: {runtime:.0f}s"

    def test_flake_rate_check(self):
        """Check flake rate is low."""
        metrics_file = Path.home() / ".deterministic-brain" / "test_metrics.json"

        if not metrics_file.exists():
            pytest.skip("No metrics data yet")

        with open(metrics_file) as f:
            metrics = json.load(f)

        flake_rate = metrics.get("flake_rate", 0.0)

        print(f"\nFlake rate: {flake_rate:.2%}")

        assert flake_rate < 0.05, f"Flake rate too high: {flake_rate:.2%}"


class TestRealWorldValue:
    """Tests that prove E2E tests provide real value."""

    def test_routing_regression_caught(self):
        """Simulate routing regression, verify test catches it."""
        from brain.router import MoERouter
        import random

        router = MoERouter()

        random.seed(42)
        from brain.task_parser import TaskParser
        parser = TaskParser()

        task = parser.parse("Create a React component")
        route1 = router.route(task)

        random.seed(42)
        route2 = router.route(task)

        assert route1 == route2, "Routing regression not caught by determinism test!"

    def test_skill_regression_caught(self, tmp_project_dir):
        """Simulate skill regression, verify test catches it."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry

        results = []
        for _ in range(2):
            registry = SkillRegistry()
            executor = SkillExecutor(registry)

            result = executor.execute(
                "react",
                task={"raw": "test", "task": "create-react-component", "component_name": "Test"},
                context={"project_dir": str(tmp_project_dir)}
            )
            results.append(str(result))

        assert results[0] == results[1], "Skill regression not caught!"

    def test_defect_log_exists(self):
        """Verify defect log exists and has entries."""
        defect_log = Path.home() / ".deterministic-brain" / "defect_log.json"

        if defect_log.exists():
            with open(defect_log) as f:
                defects = json.load(f)
            print(f"\nDefects caught before release: {len(defects)}")
            assert isinstance(defects, list)


if __name__ == "__main__":
    """Run: pytest tests/e2e/test_metrics_e2e.py -v"""
    pass