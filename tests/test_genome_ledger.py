"""Tests for the durable genome-council compounding ledger.

Every test writes to a tmp_path ledger file — never the repo's real
data/genome_ledger.json — so the suite leaves no trace on disk.
"""
import copy

import pytest

from reasoning.dev_brain import DeterministicReasoningEngine, load_genomes
from reasoning.genome_ledger import (
    WEIGHT_MAX,
    WEIGHT_MIN,
    GenomeLedger,
    build_council_engine,
    run_council,
)


@pytest.fixture()
def ledger(tmp_path):
    return GenomeLedger(storage_path=tmp_path / "ledger.json")


@pytest.fixture(scope="module")
def genomes():
    canon = load_genomes()
    assert len(canon) == 100
    return canon


class TestDurability:
    def test_file_created_on_write(self, ledger):
        assert not ledger.storage_path.exists()
        ledger.apply_adjustment("andrej-karpathy", 0.97, "success", "r", "rid")
        assert ledger.storage_path.exists()

    def test_roundtrip_after_reload(self, ledger):
        ledger.apply_adjustment("andrej-karpathy", 0.97, "failure", "r", "rid", "dev")
        ledger.add_lessons(["lesson one"], "failure", leader_id="andrej-karpathy")
        reloaded = GenomeLedger(storage_path=ledger.storage_path)
        assert reloaded.overlays()["andrej-karpathy"] == pytest.approx(0.95)
        assert reloaded.all_lessons()[0]["text"] == "lesson one"

    def test_corrupt_file_falls_back_to_empty(self, tmp_path):
        p = tmp_path / "ledger.json"
        p.write_text("{ not json", encoding="utf-8")
        l = GenomeLedger(storage_path=p)
        assert l.overlays() == {}


class TestWeightSemantics:
    def test_deltas(self, ledger):
        assert ledger.apply_adjustment("g", 0.8, "success", "r", "rid") == pytest.approx(0.81)
        assert ledger.apply_adjustment("g", 0.8, "failure", "r", "rid") == pytest.approx(0.78)
        assert ledger.apply_adjustment("g", 0.8, "partial", "r", "rid") == pytest.approx(0.8)

    def test_clamped_to_ceiling(self, ledger):
        assert ledger.apply_adjustment("g", WEIGHT_MAX, "success", "r", "rid") == WEIGHT_MAX

    def test_clamped_to_floor(self, ledger):
        assert ledger.apply_adjustment("g", WEIGHT_MIN, "failure", "r", "rid") == WEIGHT_MIN

    def test_overlay_last_adjustment_wins(self, ledger):
        ledger.apply_adjustment("g", 0.8, "success", "r1", "rid")
        ledger.apply_adjustment("g", 0.81, "failure", "r2", "rid")
        assert ledger.overlays()["g"] == pytest.approx(0.79)


class TestCouncilWiring:
    def test_build_council_applies_overlay_without_mutating_canon(
        self, ledger, genomes
    ):
        before = genomes["andrej-karpathy"]["believabilityWeight"]
        ledger.apply_adjustment(
            "andrej-karpathy", before, "failure", "bad call", "rid"
        )
        engine = build_council_engine(ledger=ledger, genomes=copy.deepcopy(genomes))
        learned = ledger.overlays()["andrej-karpathy"]
        assert engine.genomes["andrej-karpathy"]["believabilityWeight"] == learned
        assert learned < before
        # canon dict we passed in is untouched
        assert genomes["andrej-karpathy"]["believabilityWeight"] == before

    def test_run_council_uses_learned_weights(self, ledger, genomes):
        keys = list(genomes)[:5]
        baseline = genomes["andrej-karpathy"]["believabilityWeight"]
        ledger.apply_adjustment(
            "andrej-karpathy", baseline, "failure", "overconfident", "rid"
        )
        result = run_council(
            "PyTorch training loop", keys, ledger=ledger
        )
        assert result["belief_source"] == "ledger"
        assert result["belief"]["andrej-karpathy"] == pytest.approx(
            ledger.overlays()["andrej-karpathy"]
        )
        assert result["belief"]["andrej-karpathy"] < baseline
        assert [s["phase"] for s in result["states"]] == [
            "PERCEIVE", "ROUTE", "SYNTHESIZE",
        ]
        assert isinstance(result["lessonsApplied"], list)

    def test_relevant_lessons_prioritize_failure_for_selected(self, ledger):
        ledger.add_lessons(
            ["stop trusting that training loop pattern"], "failure",
            leader_id="andrej-karpathy", decision_title="a",
        )
        ledger.add_lessons(
            ["this crossover was great"], "success",
            leader_id="soumith-chintala", decision_title="b",
        )
        picked = ledger.relevant_lessons(
            "training loop", selected_genomes=["andrej-karpathy"]
        )
        assert picked and picked[0]["verdict"] == "failure"
