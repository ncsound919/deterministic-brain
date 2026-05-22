"""Determinism Smoke Test for CI.

Runs the same deterministic E2E tests twice in the same job.
Fails the CI if any diff appears in outputs or logs.
"""
from __future__ import annotations
import json
import pytest
from pathlib import Path


class TestDeterminismSmoke:
    """Smoke test: run same tests twice, compare outputs."""

    @pytest.fixture(scope="session")
    def golden_outputs(self, tmp_path_factory):
        """Run once, capture golden outputs."""
        return tmp_path_factory.mktemp("golden")

    @pytest.fixture(scope="session")
    def second_run_outputs(self, tmp_path_factory):
        """Run twice, capture new outputs."""
        return tmp_path_factory.mktemp("second")

    def test_deterministic_routing_smoke(self, golden_outputs, second_run_outputs):
        """Same seed → same routing decision."""
        from brain.task_parser import TaskParser
        from brain.router import MoERouter
        import random

        prompts = [
            "Create a React component",
            "Scaffold a REST API",
            "Add JWT auth",
            "Generate Dockerfile",
            "Audit this repo",
        ]

        for prompt in prompts:
            random.seed(42)
            parser = TaskParser()
            router = MoERouter()

            task1 = parser.parse(prompt)
            route1 = router.route(task1)

            random.seed(42)
            parser2 = TaskParser()
            router2 = MoERouter()

            task2 = parser2.parse(prompt)
            route2 = router2.route(task2)

            assert route1 == route2, (
                f"Routing not deterministic for '{prompt[:30]}': "
                f"first={route1}, second={route2}"
            )

    def test_deterministic_dialogue_smoke(self):
        """Same seed → same dialogue outputs."""
        from dialogue.pipeline import create_dialogue_pipeline

        outputs = []
        for _ in range(3):
            dp = create_dialogue_pipeline(seed=42)
            result = dp.process("hello there")
            outputs.append({
                "intent": result.intent,
                "response": result.response,
                "state": result.state,
            })
            dp.close()

        assert outputs[0] == outputs[1] == outputs[2], (
            f"Dialogue not deterministic: {outputs}"
        )

    def test_deterministic_skill_execution_smoke(self, tmp_project_dir):
        """Same skill + same input → same artifacts."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        import random

        results = []
        for i in range(2):
            random.seed(42)
            registry = SkillRegistry()
            executor = SkillExecutor(registry)

            result = executor.execute(
                "react",
                task={
                    "raw": "Create button",
                    "task": "create-react-component",
                    "component_name": "TestButton",
                },
                context={"project_dir": str(tmp_project_dir)}
            )
            results.append(json.dumps(result, sort_keys=True))

        assert results[0] == results[1], "Skill execution not deterministic"

    def test_determinism_across_processes(self):
        """Run same test in separate invocations - verify seed holds."""
        import subprocess
        import sys

        test_code = """
import random
random.seed(42)
from dialogue.pipeline import create_dialogue_pipeline
dp = create_dialogue_pipeline(seed=42)
result = dp.process("hello")
print(result.response)
dp.close()
"""

        results = []
        for _ in range(2):
            r = subprocess.run(
                [sys.executable, "-c", test_code],
                capture_output=True, text=True, timeout=30
            )
            results.append(r.stdout.strip())

        assert results[0] == results[1], (
            f"Cross-process determinism failed: {results}"
        )


class TestDefectDetectionLog:
    """Track real defects caught by E2E tests."""

    DEFECT_LOG = Path.home() / ".deterministic-brain" / "defect_log.json"

    def log_defect_caught(self, defect_type, test_id, bug_id=None):
        """Log that a defect was caught by E2E test."""
        self.DEFECT_LOG.parent.mkdir(parents=True, exist_ok=True)

        defects = []
        if self.DEFECT_LOG.exists():
            try:
                with open(self.DEFECT_LOG) as f:
                    defects = json.load(f)
            except Exception:
                pass

        defects.append({
            "timestamp": str(__import__("datetime").datetime.utcnow()),
            "defect_type": defect_type,
            "test_id": test_id,
            "bug_id": bug_id,
            "caught_before_release": True,
        })

        with open(self.DEFECT_LOG, "w") as f:
            json.dump(defects, f, indent=2)

    def get_defect_stats(self):
        """Get statistics on defects caught."""
        if not self.DEFECT_LOG.exists():
            return {"total_caught": 0, "recent_caught": 0}

        with open(self.DEFECT_LOG) as f:
            defects = json.load(f)

        return {
            "total_caught": len(defects),
            "recent_caught": len([d for d in defects 
                                  if "week" not in d.get("timestamp", "")]),
        }



class TestProductionReadiness:
    """Production-readiness smoke tests for the hardened deterministic brain."""

    def test_z3_constraint_verification(self):
        """Z3 verification passes for valid candidates, fails for invalid ones."""
        from reasoning.z3_constraints import verify_candidate

        # Valid coding candidate — has def, tests, no eval, no shell
        valid = {
            "content": "def add(a, b): return a + b",
            "tests": [{"input": (1, 2), "expected": 3}],
        }
        verdict = verify_candidate("coding", valid)
        assert verdict["passed"], f"Valid coding candidate should pass: {verdict['reason']}"

        # Invalid coding candidate — uses eval
        invalid = {
            "content": "eval('print(1)')",
            "tests": [],
        }
        verdict = verify_candidate("coding", invalid)
        assert not verdict["passed"], "Invalid coding candidate (eval) should fail"

        # Valid business logic candidate
        valid_bl = {
            "rule_results": [{"fired": True, "rule": "r1"}],
            "conflicts": [],
        }
        verdict = verify_candidate("business_logic", valid_bl)
        assert verdict["passed"], f"Valid business logic should pass: {verdict['reason']}"

    def test_graceful_shutdown_flag(self):
        """Shutdown flag rejects new work, allows existing to complete."""
        from orchestration.dca_engine import DeterministicCodingAgent

        agent = DeterministicCodingAgent()
        shutdown_called = []

        def mock_shutdown_check():
            return len(shutdown_called) > 0

        agent.register_shutdown_check(mock_shutdown_check)
        result = agent.handle("test query")
        assert result["status"] != "shutdown", "First call should proceed"

        # Now simulate shutdown
        shutdown_called.append(True)
        result = agent.handle("test query after shutdown")
        assert result["status"] == "shutdown", "Should reject work after shutdown"

    def test_constraints_and_domains_produce_valid_output(self):
        """_build_constraints and _variable_domains return proper structures."""
        from orchestration.dca_engine import DeterministicCodingAgent
        from reasoning.math_engine import Constraint

        agent = DeterministicCodingAgent()

        # Test with security task
        security_task = {"task": "security-audit", "raw": "audit the repo", "requires_auth": True}
        constraints = agent._build_constraints(security_task)
        domains = agent._variable_domains(security_task)

        assert len(constraints) > 0, "Should produce constraints"
        assert all(isinstance(c, Constraint) for c in constraints)
        assert "use_ssl" in domains, "Should include use_ssl domain"
        assert "auth_enabled" in domains, "Should include auth_enabled domain"
        assert False in domains["auth_enabled"], "Auth should be toggleable"

        # Verify constraint predicate works
        eval_constraint = [c for c in constraints if c.var == "allow_eval"][0]
        assert eval_constraint.satisfied(False), "allow_eval=False should satisfy"
        assert not eval_constraint.satisfied(True), "allow_eval=True should not satisfy"

    def test_dca_engine_imports_no_errors(self):
        """DCA engine imports cleanly with mandatory deps."""
        from orchestration.dca_engine import DeterministicCodingAgent
        # Instantiation should not raise ImportError for z3/langgraph/pyreason
        agent = DeterministicCodingAgent()
        assert agent is not None


if __name__ == "__main__":
    """Run as: pytest tests/e2e/test_determinism_smoke.py -v"""
    pass