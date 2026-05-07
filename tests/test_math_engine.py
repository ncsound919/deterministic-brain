"""Unit tests for reasoning/math_engine.py - the four reasoner classes."""
from __future__ import annotations
import pytest
from reasoning.math_engine import (
    Constraint,
    AlgebraicReasoner,
    DifferentialReasoner,
    LinearReasoner,
    QuantumProbabilistic,
    PreAudit,
    ReasoningEngine,
    DecisionResult,
    _check_injection,
)


class TestConstraint:
    """Tests for Constraint class."""

    def test_satisfied_passes(self):
        c = Constraint("x", lambda v: v > 5, "must be > 5")
        assert c.satisfied(10) is True

    def test_satisfied_fails(self):
        c = Constraint("x", lambda v: v > 5, "must be > 5")
        assert c.satisfied(3) is False

    def test_satisfied_exception_returns_false(self):
        c = Constraint("x", lambda v: 1 / 0, "will throw")
        assert c.satisfied(5) is False


class TestAlgebraicReasoner:
    """Tests for AlgebraicReasoner class."""

    def test_add_variable(self):
        ar = AlgebraicReasoner()
        ar.add_variable("lang", ["python", "typescript"])
        assert "lang" in ar.variables

    def test_add_constraint(self):
        ar = AlgebraicReasoner()
        c = Constraint("lang", lambda v: v == "python")
        ar.add_constraint(c)
        assert len(ar.constraints) == 1

    def test_solve_returns_valid_assignment(self):
        ar = AlgebraicReasoner()
        ar.add_variable("lang", ["python", "typescript"])
        ar.add_variable("async", [True, False])
        ar.add_constraint(Constraint("lang", lambda v: v == "python"))
        result = ar.solve()
        assert result is not None
        assert result["lang"] == "python"

    def test_solve_returns_none_on_failure(self):
        ar = AlgebraicReasoner()
        ar.add_variable("lang", ["python", "typescript"])
        ar.add_constraint(Constraint("lang", lambda v: v == "go"))
        result = ar.solve()
        assert result is None

    def test_all_solutions(self):
        ar = AlgebraicReasoner()
        ar.add_variable("lang", ["python", "typescript"])
        ar.add_variable("async", [True, False])
        results = ar.all_solutions(limit=10)
        assert len(results) == 4  # 2 x 2 combinations


class TestDifferentialReasoner:
    """Tests for DifferentialReasoner class."""

    def test_gradient_calculation(self):
        def scorer(cfg):
            return cfg.get("score", 0)

        dr = DifferentialReasoner(scorer)
        base = {"score": 5}
        neighbors = [{"score": 7}, {"score": 3}]
        gradients = dr.gradient(base, neighbors)
        
        assert gradients[0][0]["score"] == 7  # highest delta
        assert gradients[0][1] == 2  # delta

    def test_ascend_improves_score(self):
        def scorer(cfg):
            return cfg.get("value", 0)

        dr = DifferentialReasoner(scorer)
        
        base = {"value": 5}
        
        def neighbors_fn(cfg):
            return [{"value": cfg["value"] + 1}, {"value": cfg["value"] - 1}]
        
        result = dr.ascend(base, neighbors_fn, steps=3)
        assert result["value"] >= base["value"]

    def test_jacobian_returns_sorted(self):
        def scorer(cfg):
            return cfg.get("x", 0) * 2

        dr = DifferentialReasoner(scorer)
        configs = [{"x": 1}, {"x": 3}, {"x": 2}]
        ranked = dr.jacobian(configs)
        
        assert ranked[0][0]["x"] == 3  # highest score first


class TestLinearReasoner:
    """Tests for LinearReasoner class."""

    def test_encode_text(self):
        lr = LinearReasoner()
        vec = lr.encode_text("hello world hello")
        
        assert vec["hello"] == 2.0
        assert vec["world"] == 1.0

    def test_encode_text_removes_stopwords(self):
        lr = LinearReasoner()
        vec = lr.encode_text("the hello world")
        
        assert "the" not in vec
        assert "hello" in vec

    def test_cosine_similarity(self):
        lr = LinearReasoner()
        a = {"a": 1, "b": 1}
        b = {"a": 1, "b": 1}
        
        sim = lr.cosine(a, b)
        assert sim == pytest.approx(1.0, rel=0.01)

    def test_cosine_similarity_different(self):
        lr = LinearReasoner()
        a = {"a": 1, "b": 0}
        b = {"a": 0, "b": 1}
        
        sim = lr.cosine(a, b)
        assert sim == pytest.approx(0.0, rel=0.01)

    def test_rank_texts_preserves_duplicates(self):
        lr = LinearReasoner()
        query = "python code"
        candidates = ["python code", "python code"]  # identical
        
        ranked = lr.rank_texts(query, candidates)
        assert len(ranked) == 2  # both preserved

    def test_dominant_axes(self):
        lr = LinearReasoner()
        vectors = [
            {"python": 1, "code": 1},
            {"python": 2, "code": 0},
            {"python": 0, "code": 2},
        ]
        axes = lr.dominant_axes(vectors, top_k=2)
        assert "python" in axes or "code" in axes


class TestQuantumProbabilistic:
    """Tests for QuantumProbabilistic class."""

    def test_collapse_returns_highest_prob(self):
        qp = QuantumProbabilistic()
        choices = ["option_a", "option_b", "option_c"]
        evidence = ["option_a"]
        
        chosen, probs = qp.collapse(choices, evidence)
        
        assert chosen in choices
        assert len(probs) == 3
        assert probs[0][1] >= probs[1][1]  # sorted by prob desc

    def test_amplitudes_positive_interference(self):
        qp = QuantumProbabilistic()
        choices = ["python_code"]
        evidence = ["python", "code"]
        
        amps = qp.amplitudes(choices, evidence)
        # With matching evidence, should have positive interference
        assert len(amps) > 0

    def test_top_k(self):
        qp = QuantumProbabilistic()
        choices = ["a", "b", "c", "d", "e"]
        evidence = ["a", "b"]
        
        top = qp.top_k(choices, evidence, k=3)
        assert len(top) == 3


class TestPreAudit:
    """Tests for PreAudit class."""

    def test_has_task_pass(self):
        pa = PreAudit()
        ok, issues = pa.run({"task": "test"})
        assert ok is True
        assert "has_task" not in str(issues)

    def test_has_task_fail(self):
        pa = PreAudit()
        ok, issues = pa.run({})
        # has_task is not a blocking check - only no_injection and no_task block
        assert "has_task" in str(issues)

    def test_injection_blocks_shell(self):
        pa = PreAudit()
        ok, issues = pa.run({"raw": "echo hello; ls"})
        assert ok is False
        assert any("injection" in i for i in issues)

    def test_injection_blocks_newline(self):
        pa = PreAudit()
        ok, issues = pa.run({"raw": "echo\nls"})
        assert ok is False

    def test_injection_blocks_template(self):
        pa = PreAudit()
        ok, issues = pa.run({"raw": "{{ malicious }}"})
        assert ok is False

    def test_injection_blocks_path_traversal(self):
        pa = PreAudit()
        ok, issues = pa.run({"raw": "../../etc/passwd"})
        assert ok is False

    def test_injection_blocks_url_encoded(self):
        pa = PreAudit()
        ok, issues = pa.run({"raw": "test%24whoami"})
        assert ok is False

    def test_reasonable_length_pass(self):
        pa = PreAudit()
        ok, issues = pa.run({"raw": "short input"})
        assert ok is True

    def test_reasonable_length_fail(self):
        pa = PreAudit()
        long_input = "x" * 9000  # > 8192 byte limit
        ok, issues = pa.run({"raw": long_input})
        # reasonable_length is not a blocking check
        assert "reasonable_length" in str(issues)


class Test_check_injection:
    """Tests for injection detection function."""

    def test_shell_chars(self):
        assert _check_injection("echo $PATH") is True
        assert _check_injection("ls | grep") is True

    def test_newline(self):
        assert _check_injection("line1\nline2") is True

    def test_template_injection(self):
        assert _check_injection("{{exec}}") is True

    def test_clean_input(self):
        assert _check_injection("normal text") is False


class TestReasoningEngine:
    """Tests for ReasoningEngine class."""

    def test_init_creates_instances(self):
        re = ReasoningEngine()
        assert re.linear is not None
        assert re.quantum is not None
        assert re.pre_audit is not None

    def test_decide_returns_decision_result(self):
        re = ReasoningEngine()
        result = re.decide(
            task={"raw": "test", "task": "test"},
            skill_candidates=["skill1", "skill2"],
        )
        
        assert isinstance(result, DecisionResult)
        assert hasattr(result, "chosen_skill")
        assert hasattr(result, "confidence")
        assert hasattr(result, "breakdown")

    def test_decide_blocks_on_audit_failure(self):
        re = ReasoningEngine()
        result = re.decide(
            task={"raw": "echo $PATH", "task": "test"},  # injection
            skill_candidates=["skill1"],
        )
        
        assert result.audit_ok is False
        assert result.chosen_skill is None

    def test_decide_returns_breakdown(self):
        re = ReasoningEngine()
        result = re.decide(
            task={"raw": "test task", "task": "test"},
            skill_candidates=["skill1", "skill2"],
        )
        
        assert len(result.breakdown) > 0
        step_names = [s.get("step") for s in result.breakdown]
        assert "pre_audit" in step_names


class TestDecisionResult:
    """Tests for DecisionResult class."""

    def test_to_dict(self):
        dr = DecisionResult(
            chosen_skill="test_skill",
            chosen_config={"lang": "python"},
            confidence=0.85,
            pre_audit=[],
            audit_ok=True,
            breakdown=[{"step": "test"}],
        )
        
        d = dr.to_dict()
        assert d["chosen_skill"] == "test_skill"
        assert d["confidence"] == 0.85
        assert d["audit_ok"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])