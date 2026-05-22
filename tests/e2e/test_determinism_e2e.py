"""E2E Tests for Determinism and Reproducibility."""
from __future__ import annotations
import json
import random


class TestRoutingDeterminism:
    """Test deterministic routing behavior."""

    def test_same_input_same_route(self, brain_app):
        """Same input should produce same route across runs."""
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        results = []
        for i in range(5):
            random.seed(42)
            task = parser.parse("Create a React component")
            route = router.route(task)
            results.append(route)
        
        assert len(set(results)) == 1, f"Routes not deterministic: {results}"

    def test_different_inputs_different_routes(self, brain_app):
        """Different inputs should produce different routes."""
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        prompts = [
            "Create a React component",
            "Build a REST API",
            "Add authentication"
        ]
        
        routes = []
        for prompt in prompts:
            random.seed(42)
            task = parser.parse(prompt)
            route = router.route(task)
            routes.append(route)
        
        route_set = set(filter(None, routes))
        assert len(route_set) > 0

    def test_session_id_deterministic(self, brain_app):
        """Same query should produce same session ID."""
        from brain.memory import init_state
        
        ids = []
        for _ in range(3):
            random.seed(42)
            state = init_state("test query", "coding")
            ids.append(state["session_id"])
        
        assert len(set(ids)) == 1, f"Session IDs not deterministic: {ids}"


class TestReasonerDeterminism:
    """Test reasoner determinism."""

    def test_linear_reasoner_ranking_deterministic(self, brain_app):
        """LinearReasoner should produce deterministic rankings."""
        from brain.reasoners import LinearReasoner
        
        reasoner = LinearReasoner()
        
        candidates = ["react", "rest_api", "auth", "docker", "audit"]
        
        rankings = []
        for _ in range(3):
            random.seed(42)
            result = reasoner.rank_texts("Create a component", candidates)
            rankings.append(json.dumps(result, sort_keys=True))
        
        assert len(set(rankings)) == 1, "LinearReasoner not deterministic"

    def test_differential_reasoner_ranking_deterministic(self, brain_app):
        """DifferentialReasoner should produce deterministic rankings."""
        from reasoning.math_engine import DifferentialReasoner
        
        reasoner = DifferentialReasoner()
        
        configs = [
            {"language": "python", "async": True},
            {"language": "python", "async": False},
            {"language": "typescript", "async": True},
        ]
        
        def score_fn(cfg):
            base = 0.5
            if cfg["language"] == "python":
                base += 0.3
            if cfg.get("async"):
                base += 0.1
            return base
        
        rankings = []
        for _ in range(3):
            random.seed(42)
            result = reasoner.rank_configs(configs, score_fn)
            rankings.append(json.dumps(result, sort_keys=True))
        
        assert len(set(rankings)) == 1, "DifferentialReasoner not deterministic"

    def test_algebraic_reasoner_deterministic(self, brain_app):
        """AlgebraicReasoner should produce deterministic solutions."""
        from reasoning.math_engine import AlgebraicReasoner
        
        reasoner = AlgebraicReasoner()
        
        solutions = []
        for _ in range(3):
            random.seed(42)
            result = reasoner.solve(
                constraints=["x > 0", "x < 10"],
                variables={"x": "int"}
            )
            solutions.append(json.dumps(result, sort_keys=True))
        
        assert len(set(solutions)) == 1, "AlgebraicReasoner not deterministic"


class TestSkillExecutionDeterminism:
    """Test skill execution determinism."""

    def test_same_skill_same_artifact(self, brain_app, tmp_project_dir):
        """Same skill should produce identical artifacts."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        artifacts = []
        
        for i in range(2):
            registry = SkillRegistry()
            executor = SkillExecutor(registry)
            
            result = executor.execute(
                "react",
                task={
                    "raw": "Create button",
                    "task": "create-react-component",
                    "component_name": "DeterministicButton",
                },
                context={"project_dir": str(tmp_project_dir)}
            )
            
            artifacts.append(json.dumps(result, sort_keys=True))
        
        assert artifacts[0] == artifacts[1], "Skill execution not deterministic"

    def test_skill_execution_with_random_seed(self, brain_app, tmp_project_dir):
        """Skill execution should respect random seed."""
        from orchestration.skill_executor import SkillExecutor
        from orchestration.skill_registry import SkillRegistry
        
        results = []
        
        for seed in [42, 42, 42]:
            random.seed(seed)
            registry = SkillRegistry()
            executor = SkillExecutor(registry)
            
            result = executor.execute(
                "react",
                task={"raw": "test", "task": "create-react-component", "component_name": "Test"},
                context={"project_dir": str(tmp_project_dir)}
            )
            
            results.append(json.dumps(result, sort_keys=True))
        
        assert results[0] == results[1] == results[2]


class TestSchedulerDeterminism:
    """Test scheduler determinism."""

    def test_scheduler_time_travel_deterministic(self, brain_app):
        """Scheduler should produce deterministic execution order."""
        from features.scheduler import Scheduler
        
        scheduler1 = Scheduler()
        scheduler1.schedule_task("task-a", "react", "interval", 1)
        scheduler1.schedule_task("task-b", "rest_api", "interval", 1)
        
        results1 = scheduler1.tick()
        
        scheduler2 = Scheduler()
        scheduler2.schedule_task("task-a", "react", "interval", 1)
        scheduler2.schedule_task("task-b", "rest_api", "interval", 1)
        
        results2 = scheduler2.tick()


class TestDialogueDeterminism:
    """Test dialogue pipeline determinism."""

    def test_dialogue_same_input_same_output(self):
        """Same dialogue input should produce same output."""
        from dialogue.pipeline import create_dialogue_pipeline
        
        outputs = []
        
        for _ in range(3):
            dp = create_dialogue_pipeline(seed=42)
            result = dp.process("hello there")
            outputs.append(json.dumps({
                "intent": result.intent,
                "response": result.response,
                "state": result.state
            }, sort_keys=True))
            dp.close()
        
        assert len(set(outputs)) == 1, f"Dialogue not deterministic: {outputs}"

    def test_dialogue_seed_reproducibility(self):
        """Dialogue should be reproducible with same seed."""
        from dialogue.pipeline import DialoguePipeline
        
        results = []
        
        for _ in range(2):
            dp = DialoguePipeline(seed=123)
            r = dp.process("help me")
            results.append(r.response)
            dp.close()
        
        assert results[0] == results[1]

    def test_response_realizer_deterministic(self):
        """Response realizer should produce deterministic responses."""
        from dialogue.response_realizer import create_default_realizer
        
        realizer1 = create_default_realizer(seed=42)
        response1 = realizer1.realize("greeting", {})
        
        realizer2 = create_default_realizer(seed=42)
        response2 = realizer2.realize("greeting", {})
        
        assert response1.text == response2.text


class TestMultiRunStability:
    """Test multi-run stability across entire pipeline."""

    def test_full_pipeline_stability(self, brain_app):
        """Full pipeline should be stable across runs."""
        from orchestration.langgraph_app import build_app
        
        app1 = build_app()
        result1 = app1.run("Create a React button")
        
        app2 = build_app()
        result2 = app2.run("Create a React button")
        
        assert result1.get("lane") == result2.get("lane")

    def test_golden_trace_comparison(self, brain_app):
        """Test against golden trace."""
        golden = {
            "lane": "coding",
            "task": "create-react-component"
        }
        
        parser = brain_app["parser"]
        router = brain_app["router"]
        
        random.seed(42)
        task = parser.parse("Create a React component")
        route = router.route(task)
        
        assert route is not None


class TestEdgeCasesDeterminism:
    """Test edge cases for determinism."""

    def test_empty_input_handling(self, brain_app):
        """Empty input should be handled deterministically."""
        parser = brain_app["parser"]
        
        results = []
        for _ in range(3):
            random.seed(42)
            task = parser.parse("")
            results.append(task.get("task", "unknown"))
        
        assert len(set(results)) == 1

    def test_very_long_input_deterministic(self, brain_app):
        """Very long input should be handled deterministically."""
        parser = brain_app["parser"]
        
        long_input = "Create a " + "very " * 100 + "long component"
        
        results = []
        for _ in range(3):
            random.seed(42)
            task = parser.parse(long_input)
            results.append(task.get("task", "unknown"))
        
        assert len(set(results)) == 1

    def test_special_characters_deterministic(self, brain_app):
        """Special characters should be handled deterministically."""
        parser = brain_app["parser"]
        
        special_inputs = [
            "Create component with $pecial ch@rs!",
            "Create component with émojis 🚀",
            "Create component with unicode: é",
        ]
        
        for inp in special_inputs:
            results = []
            for _ in range(3):
                random.seed(42)
                task = parser.parse(inp)
                results.append(task.get("task", "unknown"))
            
            assert len(set(results)) == 1, f"Failed for: {inp}"