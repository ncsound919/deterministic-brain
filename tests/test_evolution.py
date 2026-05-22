"""Tests for evolution/ — skill evolver, weight store, nightly scorer."""
from pathlib import Path

import pytest

from evolution.weight_store import WeightStore
from evolution.skill_evolver import SkillEvolver
from evolution.nightly_scorer import NightlyScorer


class TestWeightStore:
    def test_get_default(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        assert ws.get("unknown") == 1.0
        assert ws.get("unknown", 0.5) == 0.5

    def test_set_and_get(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ws.set("skill_a", 0.85)
        assert ws.get("skill_a") == 0.85

    def test_history_tracks_versions(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ws.set("skill_a", 0.5)  # first set: no history (current_weight was None)
        ws.set("skill_a", 0.75)  # change → history[0]
        ws.set("skill_a", 1.0)  # change → history[1]
        hist = ws.history("skill_a")
        assert len(hist) == 2
        assert hist[0]["weight"] == 0.75
        assert hist[1]["weight"] == 1.0

    def test_history_empty_for_unknown(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        assert ws.history("nonexistent") == []

    def test_rollback(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ws.set("skill_a", 0.2)  # initial: None → 0.2, no history
        ws.set("skill_a", 0.5)  # change → history[0] = {v:1, weight:0.5}
        ws.set("skill_a", 0.8)  # change → history[1] = {v:2, weight:0.8}
        ws.set("skill_a", 1.0)  # change → history[2] = {v:3, weight:1.0}
        ws.rollback("skill_a", 1)
        assert ws.get("skill_a") == 0.5  # rolled back to history v1
        assert len(ws.history("skill_a")) == 3  # history is append-only

    def test_rollback_invalid_version(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        assert ws.rollback("unknown", 5) is False

    def test_all_weights(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ws.set("a", 0.5)
        ws.set("b", 1.5)
        all_w = ws.all_weights()
        assert all_w["a"] == 0.5
        assert all_w["b"] == 1.5

    def test_export_import(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ws.set("a", 0.5)
        exported = ws.export()
        ws2 = WeightStore(str(tmp_path / "weights2.json"))
        ws2.import_data(exported)
        assert ws2.get("a") == 0.5

    def test_history_prunes_old(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        for i in range(60):
            ws.set("a", 0.5 + i * 0.01)
        assert len(ws.history("a")) <= 50

    def test_same_weight_no_history(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ws.set("a", 0.5)  # first set, current_weight was None → no history
        ws.set("a", 0.5)  # same value
        assert len(ws.history("a")) == 0


class TestSkillEvolver:
    def test_track_new_skill(self, tmp_path):
        ev = SkillEvolver(str(tmp_path / "perf.json"),
                          WeightStore(str(tmp_path / "weights.json")))
        ev.track("skill_a", True, latency_ms=100, confidence=0.9)
        stats = ev.get_stats("skill_a")
        assert stats["runs"] == 1
        assert stats["success_rate"] == 1.0

    def test_evolve_below_min_samples(self, tmp_path):
        ev = SkillEvolver(str(tmp_path / "perf.json"),
                          WeightStore(str(tmp_path / "weights.json")))
        for _ in range(5):
            ev.track("skill_a", True)
        result = ev.evolve()
        assert len(result) == 0  # below min_samples (10)

    def test_evolve_adjusts_weights(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ev = SkillEvolver(str(tmp_path / "perf.json"), ws)
        for _ in range(10):
            ev.track("skill_a", True)  # 100% success
        result = ev.evolve()
        assert len(result) == 1
        assert result[0]["success_rate"] == 1.0
        # weight = 1.0 * 0.7 + 1.0 * 0.3 = 1.0
        assert result[0]["new_weight"] == pytest.approx(1.0, rel=0.01)

    def test_evolve_low_performer(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ev = SkillEvolver(str(tmp_path / "perf.json"), ws)
        for i in range(10):
            ev.track("skill_b", i < 3)  # 30% success
        result = ev.evolve()
        assert result[0]["success_rate"] == pytest.approx(0.3, rel=0.1)
        assert result[0]["new_weight"] < 1.0

    def test_weight_clamped(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ws.set("skill_c", 2.0)
        ev = SkillEvolver(str(tmp_path / "perf.json"), ws)
        for _ in range(10):
            ev.track("skill_c", False)  # 0% success
        ev.evolve()
        w = ws.get("skill_c")
        assert w >= 0.1  # min clamp

    def test_deprecate(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ev = SkillEvolver(str(tmp_path / "perf.json"), ws)
        ev.track("skill_d", True)
        ev.deprecate("skill_d")
        assert ws.get("skill_d") == 0.0
        assert ev.get_stats("skill_d")["deprecated"] is True

    def test_suggest_alternative(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ws.set("skill_x", 0.3)
        ws.set("skill_y", 1.5)
        ws.set("skill_z", 0.8)
        ev = SkillEvolver(str(tmp_path / "perf.json"), ws)
        alt = ev.suggest_alternative("skill_x")
        assert alt == "skill_y"  # highest weight

    def test_suggest_alternative_none(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ev = SkillEvolver(str(tmp_path / "perf.json"), ws)
        assert ev.suggest_alternative("only_skill") is None

    def test_all_stats_sorted(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ws.set("a", 1.5)
        ws.set("b", 0.5)
        ev = SkillEvolver(str(tmp_path / "perf.json"), ws)
        ev.track("a", True)
        ev.track("b", False)
        stats = ev.all_stats()
        assert stats[0]["skill_id"] == "a"  # highest weight first


class TestNightlyScorer:
    def test_run_daily_score(self, tmp_path):
        ws = WeightStore(str(tmp_path / "weights.json"))
        ev = SkillEvolver(str(tmp_path / "perf.json"), ws)
        for i in range(10):
            ev.track("skill_a", i >= 5)  # 50% success
        scorer = NightlyScorer(ev, str(tmp_path / "report.json"))
        report = scorer.run_daily_score()
        assert report["evolved_skills"] == 1
        assert report["all_skills"] == 1
        assert Path(tmp_path / "report.json").exists()

    def test_generate_report_no_file(self, tmp_path):
        scorer = NightlyScorer(report_path=str(tmp_path / "nonexistent.json"))
        assert scorer.generate_report()["status"] == "never_run"

    def test_weight_histogram(self, tmp_path):
        scorer = NightlyScorer()
        h = scorer._weight_histogram([
            {"weight": 0.3}, {"weight": 0.6}, {"weight": 1.0},
            {"weight": 1.5}, {"weight": 0.2},
        ])
        assert h["0.0-0.5"] == 2
        assert h["0.5-0.8"] == 1
        assert h["0.8-1.2"] == 1
        assert h["1.2-2.0"] == 1
