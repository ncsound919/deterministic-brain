"""Tests for the /genome-council route handlers.

Handlers call the module-level `get_genome_ledger()` singleton, so we patch it
to a tmp_path ledger. Canon genomes are read-only (never written)."""
import pytest

import api.routes.genome as gm
from api.routes.genome import (
    DecideRequest,
    PostMortemRequest,
    council_decide,
    council_post_mortem,
    council_state,
)
from reasoning.dev_brain import load_genomes
from reasoning.genome_ledger import GenomeLedger


@pytest.fixture(scope="module")
def canon():
    return load_genomes()


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    l = GenomeLedger(storage_path=tmp_path / "route-ledger.json")
    monkeypatch.setattr(gm, "get_genome_ledger", lambda: l)
    return l


def test_decide_returns_fsm_and_durable_belief(canon, ledger):
    keys = list(canon)[:5]
    res = council_decide(DecideRequest(problem="PyTorch training loop on 24GB VRAM",
                                       selected_genomes=keys))
    assert [s["phase"] for s in res["states"]] == ["PERCEIVE", "ROUTE", "SYNTHESIZE"]
    assert res["belief_source"] == "ledger"
    assert set(res["belief"].keys()) == set(keys)
    assert res["audit_trail"]["fully_traceable"] is True


def test_post_mortem_persists_weight_and_lessons(canon, ledger):
    leader = "andrej-karpathy"
    baseline = canon[leader]["believabilityWeight"]
    res = council_post_mortem(PostMortemRequest(
        decision_title="bet on the training loop",
        sector="dev",
        chosen_option="use pattern",
        predicted_probability=0.8,
        actual_outcome="failure",
        leader_ids=[leader],
        root_causes=["overfit"],
        key_lessons=["do not trust the warm-start pattern blindly"],
        retrospective_summary="it regressed",
    ))
    assert res["durable"] is True
    assert res["adjustments_applied"] == 1
    assert res["record"]["brierScore"] == pytest.approx(0.64)
    assert res["record"]["calibrationRating"] == "OVERCONFIDENT"
    assert res["overview"]["lessons_learned"] >= 1
    # the leader's learned weight dropped from baseline
    st = council_state()
    assert st["learned_weights"][leader] < baseline
    assert st["learned_weights"][leader] == pytest.approx(
        round(min(1.0, max(0.5, baseline - 0.02)), 4)
    )


def test_post_mortem_then_decide_shows_compounded_weight(canon, ledger):
    leader = "andrej-karpathy"
    council_post_mortem(PostMortemRequest(
        decision_title="x", sector="dev",
        predicted_probability=0.6, actual_outcome="failure",
        leader_ids=[leader], key_lessons=["regressed"],
    ))
    res = council_decide(DecideRequest(
        problem="optimize a training loop", selected_genomes=[leader, "soumith-chintala"]
    ))
    assert res["belief"][leader] == pytest.approx(
        ledger.overlays()[leader]
    )


def test_unknown_genome_rejected(canon, ledger):
    with pytest.raises(Exception) as ei:
        council_decide(DecideRequest(problem="x", selected_genomes=["does-not-exist"]))
    assert ei.type.__name__ == "HTTPException"


def test_empty_selection_defaults_to_all(canon, ledger):
    res = council_decide(DecideRequest(problem="a general strategy question"))
    assert len(res["belief"]) == len(canon)
