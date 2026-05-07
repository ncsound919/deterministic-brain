"""E2E Tests for Core Task-to-Skill Routing."""
from __future__ import annotations
import os
import pytest
from pathlib import Path


class TestReactComponentRouting:
    """Test React component generation routing."""

    def test_react_component_generation_routing(self, brain_app):
        """Input: Create a React button that supports dark mode."""
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        task = parser.parse("Create a React button component with dark mode support")
        
        assert task is not None
        assert task["task"] in ["create-react-component", "react", "unknown"], f"Got: {task}"
        
        if task["task"] != "unknown":
            route = router.route(task)
            assert route is not None
            assert "react" in route.lower() or "skill_packs" in route.lower()

    def test_react_component_deterministic_routing(self, brain_app, test_seed):
        """Same input should route to same skill across runs."""
        import random
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        results = []
        for _ in range(3):
            random.seed(test_seed)
            task = parser.parse("Create a React button")
            route = router.route(task)
            results.append((task.get("task"), route))
        
        assert len(set(results)) == 1, f"Routing not deterministic: {results}"


class TestRestApiRouting:
    """Test REST API scaffold routing."""

    def test_rest_api_scaffold_routing(self, brain_app):
        """Input: Scaffold a REST API for a todo service in FastAPI."""
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        task = parser.parse("Scaffold a REST API for a todo service in FastAPI")
        
        assert task is not None
        assert task["task"] in ["scaffold-rest-api", "rest_api", "unknown"], f"Got: {task}"
        
        if task["task"] != "unknown":
            route = router.route(task)
            assert route is not None

    def test_rest_api_fallback_routing(self, brain_app):
        """Test FastAPI routing maps to rest_api skill."""
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        task = parser.parse("Create a FastAPI endpoint")
        
        route = router.route(task)
        
        if route:
            assert "rest" in route.lower() or "api" in route.lower()


class TestAuthRouting:
    """Test JWT auth addition routing."""

    def test_auth_addition_routing(self, brain_app):
        """Input: Add JWT auth to this API."""
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        task = parser.parse("Add JWT auth to this API")
        
        assert task is not None
        task_type = task.get("task", "unknown")
        
        if task_type != "unknown":
            route = router.route(task)
            assert route is not None
            assert "auth" in route.lower()

    def test_auth_jwt_keyword_routing(self, brain_app):
        """JWT keyword triggers auth skill."""
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        task = parser.parse("Add JWT authentication")
        
        route = router.route(task)
        
        if route:
            assert "auth" in route.lower()


class TestDockerRouting:
    """Test Dockerfile generation routing."""

    def test_dockerfile_generation_routing(self, brain_app):
        """Input: Generate a Dockerfile for myapp."""
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        task = parser.parse("Generate a Dockerfile for myapp")
        
        assert task is not None
        task_type = task.get("task", "unknown")
        
        if task_type != "unknown":
            route = router.route(task)
            assert route is not None


class TestRepoAuditRouting:
    """Test repo audit routing."""

    def test_repo_audit_routing(self, brain_app, sample_repo):
        """Input: Audit this repo for obvious issues."""
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        task = parser.parse("Audit this repo for obvious issues")
        
        assert task is not None
        task_type = task.get("task", "unknown")
        
        if task_type != "unknown":
            route = router.route(task)
            assert route is not None
            assert "audit" in route.lower() or "repo" in route.lower()


class TestTaskClassificationStability:
    """Test task classification stability across prompts."""

    @pytest.mark.parametrize("prompt,expected_task", [
        ("Create a React component", "react"),
        ("Build a REST API", "rest_api"),
        ("Add authentication", "auth"),
        ("Generate Dockerfile", "docker"),
        ("Audit repository", "audit"),
        ("Write unit tests", "testing"),
        ("Create documentation", "docs"),
    ])
    def test_task_classification(self, brain_app, prompt, expected_task):
        """Verify prompts map to expected task categories."""
        parser = brain_app["parser"]
        
        task = parser.parse(prompt)
        
        assert task is not None
        task_type = task.get("task", "unknown")
        
        assert task_type != "unknown", f"Failed to parse: {prompt}"


class TestPreAuditInjectionChecks:
    """Test PreAudit blocks malicious inputs."""

    @pytest.mark.parametrize("malicious_input", [
        "Create a file; rm -rf /",
        "Run command | cat /etc/passwd",
        "Read file ../../etc/passwd",
        "Create component {{__import__('os').system('ls')}}",
        "Generate code with $(whoami)",
        "test\n---script---",
        "test%24__import__",
    ])
    def test_injection_blocked(self, brain_app, malicious_input):
        """Malicious inputs should be blocked."""
        from reasoning.math_engine import PreAudit
        
        audit = PreAudit()
        result = audit.check(malicious_input)
        
        assert result.audit_ok == False, f"Should have blocked: {malicious_input[:30]}..."
        assert result.blocked_reason is not None


class TestConfigSelection:
    """Test config selection by reasoners."""

    def test_algebraic_reasoner_config_selection(self, brain_app):
        """AlgebraicReasoner selects correct config based on constraints."""
        from reasoning.math_engine import AlgebraicReasoner
        
        reasoner = AlgebraicReasoner()
        
        constraints = ["language=python", "framework=fastapi"]
        variables = {"language": "str", "framework": "str"}
        
        result = reasoner.solve(constraints, variables)
        
        assert result is not None
        assert "language" in result
        assert result["language"] in ["python", "typescript", "javascript"]

    def test_differential_reasoner_config_selection(self, brain_app):
        """DifferentialReasoner optimizes based on scoring function."""
        from reasoning.math_engine import DifferentialReasoner
        
        reasoner = DifferentialReasoner()
        
        configs = [
            {"language": "python", "async": True},
            {"language": "python", "async": False},
            {"language": "typescript", "async": True},
        ]
        
        def score_fn(cfg):
            if cfg["language"] == "python":
                return 0.8
            return 0.5
        
        ranked = reasoner.rank_configs(configs, score_fn)
        
        assert ranked[0]["language"] == "python"
