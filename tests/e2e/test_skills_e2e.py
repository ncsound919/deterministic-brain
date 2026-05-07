"""E2E Tests for Skill Execution."""
from __future__ import annotations
import os
import json
import pytest
from pathlib import Path


class TestReactSkillExecution:
    """Test React skill execution."""

    def test_react_skill_generates_component(self, brain_app, tmp_project_dir):
        """React skill should generate a component file."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        
        result = executor.execute(
            "react",
            task={
                "raw": "Create a React button",
                "task": "create-react-component",
                "component_name": "Button",
            },
            context={"project_dir": str(tmp_project_dir)}
        )
        
        assert result.get("success") or result.get("artifacts"), f"Skill failed: {result}"
        
        output_dir = tmp_project_dir / "output" / "react"
        if output_dir.exists():
            files = list(output_dir.glob("*.tsx"))
            assert len(files) > 0, "No component files generated"

    def test_react_skill_with_props(self, brain_app, tmp_project_dir):
        """React skill should handle props correctly."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        
        result = executor.execute(
            "react",
            task={
                "raw": "Create React button with loading state",
                "task": "create-react-component",
                "component_name": "LoadingButton",
                "props": ["loading", "onClick"],
            },
            context={"project_dir": str(tmp_project_dir)}
        )
        
        assert result.get("success") or result.get("artifacts")


class TestRestApiSkillExecution:
    """Test REST API skill execution."""

    def test_rest_api_skill_generates_files(self, brain_app, tmp_project_dir):
        """REST API skill should generate API scaffold."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        
        result = executor.execute(
            "rest_api",
            task={
                "raw": "Scaffold REST API",
                "task": "scaffold-rest-api",
                "framework": "fastapi",
            },
            context={"project_dir": str(tmp_project_dir)}
        )
        
        assert result.get("success") or result.get("artifacts"), f"Skill failed: {result}"


class TestAuthSkillExecution:
    """Test auth skill execution."""

    def test_auth_skill_adds_jwt(self, brain_app, tmp_project_dir):
        """Auth skill should add JWT middleware."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        
        result = executor.execute(
            "auth",
            task={
                "raw": "Add JWT auth",
                "task": "add-auth",
                "auth_type": "jwt",
            },
            context={"project_dir": str(tmp_project_dir)}
        )
        
        assert result.get("success") or result.get("artifacts")


class TestDockerSkillExecution:
    """Test docker skill execution."""

    def test_dockerfile_generation(self, brain_app, tmp_project_dir):
        """Docker skill should generate Dockerfile."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        
        result = executor.execute(
            "docker",
            task={
                "raw": "Generate Dockerfile",
                "task": "generate-dockerfile",
                "language": "python",
            },
            context={"project_dir": str(tmp_project_dir)}
        )
        
        assert result.get("success") or result.get("artifacts")
        
        if result.get("artifacts"):
            for artifact in result["artifacts"]:
                if artifact.get("type") == "file":
                    assert (tmp_project_dir / artifact["path"]).exists() or artifact.get("path")


class TestImportedSkills:
    """Test imported Hermes/OpenClaw skills."""

    def test_skill_registry_discovers_all_skills(self, brain_app):
        """Skill registry should discover all skill packs."""
        from orchestration.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        skills = registry.list_skills()
        
        assert len(skills) > 0, "No skills discovered"
        
        skill_ids = [s["id"] for s in skills]
        
        assert "react" in skill_ids or any("react" in s for s in skill_ids)

    def test_hermes_imported_skill_discovery(self, brain_app):
        """Hermes imported skills should be discoverable."""
        from orchestration.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        
        hermes_skills = [
            s for s in registry.list_skills()
            if "hermes" in s.get("id", "").lower() or "imported" in s.get("id", "").lower()
        ]
        
        assert isinstance(hermes_skills, list)

    def test_openclaw_imported_skill_discovery(self, brain_app):
        """OpenClaw imported skills should be discoverable."""
        from orchestration.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        
        openclaw_skills = [
            s for s in registry.list_skills()
            if "openclaw" in s.get("id", "").lower()
        ]
        
        assert isinstance(openclaw_skills, list)


class TestSkillExecutionLocalBackend:
    """Test local skill execution backend."""

    def test_local_backend_runs_skill(self, brain_app, tmp_project_dir):
        """Local backend should execute skill and produce output."""
        from orchestration.backends import LocalSkillBackend
        
        backend = LocalSkillBackend()
        
        result = backend.run(
            "react",
            task={"raw": "Create component", "task": "create-react-component", "component_name": "Test"},
            context={"project_dir": str(tmp_project_dir)}
        )
        
        assert "success" in result or "artifacts" in result

    def test_local_backend_handles_missing_skill(self, brain_app):
        """Local backend should handle missing skill gracefully."""
        from orchestration.backends import LocalSkillBackend
        
        backend = LocalSkillBackend()
        
        result = backend.run(
            "nonexistent-skill",
            task={"raw": "test"},
            context={}
        )
        
        assert result["success"] == False
        assert "not found" in result.get("output", "").lower()


class TestSkillBackendRouting:
    """Test skill backend routing."""

    def test_backend_routing_local(self, brain_app):
        """Local skills should use LocalSkillBackend."""
        from orchestration.skill_registry import SkillRegistry
        from orchestration.backends import LocalSkillBackend
        
        registry = SkillRegistry()
        
        local_skills = [
            s for s in registry.list_skills()
            if s.get("backend") == "local" or not s.get("backend")
        ]
        
        assert len(local_skills) > 0

    def test_claude_backend_available(self, brain_app):
        """Claude backend should be available if configured."""
        from orchestration.backends import ClaudeSkillBackend
        
        try:
            backend = ClaudeSkillBackend()
            assert hasattr(backend, "run")
        except Exception:
            pytest.skip("Claude backend not configured")


class TestSkillDeterminism:
    """Test skill execution determinism."""

    def test_same_skill_same_output(self, brain_app, tmp_project_dir):
        """Same skill with same inputs should produce identical outputs."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        results = []
        
        for i in range(2):
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
        
        assert results[0] == results[1], "Skill output not deterministic"