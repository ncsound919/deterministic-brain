"""Tests for the Dev Brain port (genome council, post-mortem, red team,
guardrails). Deterministic: same inputs -> same outputs."""

import pytest

from reasoning.dev_brain import (
    DeterministicReasoningEngine,
    load_genomes,
)
from reasoning.dev_brain_guardrails import GuardrailEngine, evaluate_condition
from reasoning.post_mortem import PostMortemCalibrationEngine
from reasoning.red_team import AdversarialRedTeamEngine


@pytest.fixture(scope="module")
def engine():
    return DeterministicReasoningEngine()


@pytest.fixture(scope="module")
def genome_keys():
    keys = list(load_genomes())
    assert len(keys) == 100
    return keys


class TestGenomeCouncil:
    def test_reason_returns_full_fsm(self, engine, genome_keys):
        result = engine.reason_about_problem(
            "Optimize memory usage of a PyTorch training loop on 24GB VRAM",
            genome_keys[:5],
        )
        phases = [s["phase"] for s in result["states"]]
        assert phases == ["PERCEIVE", "ROUTE", "SYNTHESIZE"]
        assert result["output"]["primaryPattern"]
        assert result["audit_trail"]["fully_traceable"] is True
        assert len(result["audit_trail"]["source_attribution"]) == 5

    def test_sector_detection(self, engine):
        assert (
            engine.detect_sector("CAR-T design for solid tumor", []) 
            == "science_biotech"
        )
        assert engine.detect_sector("DCF valuation model", []) == "financial"
        assert engine.detect_sector("anything", ["dev", "business"]) == "cross_domain"
        assert engine.detect_sector("refactor this module", []) == "dev"

    def test_constraints(self, engine):
        c = engine.identify_constraints("low latency inference under tight budget")
        assert "latency_critical" in c and "capital_and_budget_constrained" in c
        assert engine.identify_constraints("hello world") == [
            "standard_operating_envelope"
        ]

    def test_ranking_is_deterministic_and_sorted(self, engine, genome_keys):
        r1 = engine.rank_genomes_by_relevance("PyTorch CUDA training", genome_keys[:10])
        r2 = engine.rank_genomes_by_relevance("PyTorch CUDA training", genome_keys[:10])
        assert r1 == r2
        scores = [g["relevanceScore"] for g in r1]
        assert scores == sorted(scores, reverse=True)

    def test_unknown_genome_gets_neutral_score(self, engine):
        ranked = engine.rank_genomes_by_relevance("anything", ["nope"])
        assert ranked[0]["relevanceScore"] == 0.5

    def test_confidence_levels(self, engine, genome_keys):
        conf = engine.calculate_confidence(
            engine.rank_genomes_by_relevance("system design", genome_keys[:4])
        )
        assert conf["level"] in ("HIGH", "MEDIUM", "LOW")
        assert 0 <= conf["score"] <= 1


class TestPostMortem:
    def test_brier_score(self):
        pm = PostMortemCalibrationEngine()
        assert pm.calculate_brier_score(0.88, 1.0) == 0.0144
        assert pm.calculate_brier_score(0.75, 0.5) == 0.0625

    def test_calibration_rating(self):
        pm = PostMortemCalibrationEngine()
        assert pm.get_calibration_rating(0.01, 0.9, 1.0) == "EXCELLENT"
        assert pm.get_calibration_rating(0.08, 0.7, 1.0) == "GOOD"
        assert pm.get_calibration_rating(0.6, 0.9, 0.0) == "OVERCONFIDENT"
        assert pm.get_calibration_rating(0.6, 0.2, 1.0) == "UNDERCONFIDENT"

    def test_overview_grades(self):
        records = [
            {"status": "success", "brierScore": 0.02,
             "actualOutcomeBinary": 1.0, "sector": "dev"},
            {"status": "partial", "brierScore": 0.05,
             "actualOutcomeBinary": 0.5, "sector": "business"},
        ]
        overview = PostMortemCalibrationEngine(records=records).compute_overview()
        assert overview["calibrationGrade"] == "A"
        assert overview["accuracyRate"] == 50.0

    def test_create_and_apply_adjustments(self, engine, genome_keys):
        pm = PostMortemCalibrationEngine(genomes=engine.genomes)
        leader = engine.genomes[genome_keys[0]]
        original = leader["believabilityWeight"]
        record = pm.create_new_post_mortem(
            decision_title="Test decision",
            sector=leader["sector"],
            chosen_option="Option A",
            predicted_probability=0.8,
            actual_outcome="success",
            metric_variances=[],
            root_causes=["rc"],
            key_lessons=["lesson"],
            retrospective_summary="ok",
            leaders=[leader],
        )
        assert record["brierScore"] == 0.04
        assert record["suggestedAdjustments"][0]["delta"] == 0.01
        applied = pm.apply_adjustments(record["id"])
        assert applied == 1
        assert leader["believabilityWeight"] == round(min(1.0, original + 0.01), 2)


class TestRedTeam:
    def test_simulation_shape_and_grade(self):
        rt = AdversarialRedTeamEngine().run_simulation(
            "Migrate to cloud infra",
            "Kafka event mesh",
            seed=42,
        )
        assert len(rt["scenarios"]) == 4
        types = {s["type"] for s in rt["scenarios"]}
        assert types == {
            "adversary_counter", "black_swan", "cascade_friction",
            "regulatory_shock",
        }
        assert 15 <= rt["resilienceScore"] <= 95
        assert rt["robustnessGrade"] in (
            "FRAGILE", "VULNERABLE", "RESILIENT", "FORTIFIED",
        )

    def test_sector_aware_adversary(self):
        bio = AdversarialRedTeamEngine().run_simulation(
            "CAR-T clinical trial", "dual antigen", seed=1
        )
        assert bio["scenarios"][0]["threatLevel"] == "CRITICAL"

    def test_deterministic_with_seed(self):
        a = AdversarialRedTeamEngine().run_simulation("x", "y", seed=7)
        b = AdversarialRedTeamEngine().run_simulation("x", "y", seed=7)
        assert a == b


class TestGuardrails:
    def test_evaluate_condition(self):
        assert evaluate_condition(10, "gt", 5)
        assert evaluate_condition("x", "contains", "x")
        assert not evaluate_condition("abc", "gt", 5)

    def test_rule_violations(self):
        rules = [{
            "id": "r1", "name": "spend cap", "severity": "BLOCKING",
            "enabled": True,
            "evaluator": {"field": "amount_usd", "operator": "gt",
                          "thresholdValue": 500},
            "remediationAdvice": "split payment",
        }]
        payload = {"parameters": {"amount_usd": 900}}
        res = GuardrailEngine.evaluate_guardrails(payload, rules)
        assert res["hasBlockingViolations"] is True
        assert res["violatedRules"][0]["ruleId"] == "r1"
        # disabled rule never fires
        rules[0]["enabled"] = False
        res = GuardrailEngine.evaluate_guardrails(payload, rules)
        assert res["hasBlockingViolations"] is False

    def test_blast_radius_tiers(self):
        cat = GuardrailEngine.calculate_blast_radius({
            "parameters": {"has_destructive_syntax": True}
        })
        assert cat["riskTier"] == "CATASTROPHIC" and cat["isIrreversible"]
        low = GuardrailEngine.calculate_blast_radius({"parameters": {}})
        assert low["riskTier"] == "LOW"

    def test_circuit_breakers(self):
        breakers = [
            {"id": "cb_global_kill", "status": "NORMAL"},
            {"id": "cb_email", "domain": "send_email", "status": "TRIPPED"},
        ]
        tripped = GuardrailEngine.check_circuit_breakers(
            {"actionType": "send_email"}, breakers
        )
        assert tripped["isTripped"] and tripped["status"] == "TRIPPED_DOMAIN"
        clear = GuardrailEngine.check_circuit_breakers(
            {"actionType": "other"}, breakers
        )
        assert clear["isTripped"] is False
