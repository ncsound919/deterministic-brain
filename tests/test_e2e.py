"""End-to-end system tests for the Deterministic Brain."""
from __future__ import annotations
import pytest
import json
import tempfile
import os
from pathlib import Path


class TestEndToEndPipeline:
    """Test the full pipeline from query to output."""

    def test_router_to_state_pipeline(self):
        """Test: query -> route_lane -> init_state -> retrieve"""
        from brain.router import route_lane
        from brain.memory import init_state
        from retrieval.hybrid import retrieve
        
        query = "create a react component named Button"
        lane = route_lane(query)
        assert lane in ["coding", "business_logic", "tool_calling", "cross_domain", "agent_brain"]
        
        state = init_state(query, lane)
        assert state["session_id"] is not None
        assert state["query"] == query
        assert state["lane"] == lane
        
        contexts = retrieve(query, lane)
        assert isinstance(contexts, list)

    def test_task_parser_to_router_pipeline(self):
        """Test: raw query -> parse -> route"""
        from brain.task_parser import TaskParser
        from brain.router import MoERouter
        
        parser = TaskParser()
        router = MoERouter()
        
        test_queries = [
            ("create react component named Button", "create-react-component"),
            ("add auth to User", "add-auth"),
            ("generate dockerfile for myapp", "generate-dockerfile"),
        ]
        
        for query, expected_task in test_queries:
            task = parser.parse(query)
            route = router.route(task)
            # Should have a valid route
            assert route is not None or expected_task in ["unknown"]

    def test_reasoning_pipeline(self):
        """Test: task -> ReasoningEngine.decide -> result"""
        from reasoning.math_engine import ReasoningEngine
        
        re = ReasoningEngine()
        task = {
            "raw": "create react component with typescript",
            "task": "create-react-component",
            "component_name": "Button",
        }
        
        result = re.decide(
            task=task,
            skill_candidates=["react", "python", "docker"],
        )
        
        assert hasattr(result, "chosen_skill")
        assert hasattr(result, "confidence")
        assert 0.0 <= result.confidence <= 1.0

    def test_full_agent_handle(self):
        """Test: DeterministicCodingAgent.handle end-to-end"""
        from orchestration.dca_engine import DeterministicCodingAgent
        
        agent = DeterministicCodingAgent()
        
        result = agent.handle("create react component named UserCard")
        
        assert "status" in result
        assert "final_output" in result
        assert "session_id" in result
        
        # Should complete with some status (ok, failed, low_confidence, blocked)
        assert result["status"] in ["ok", "failed", "low_confidence", "blocked"]

    def test_determinism_full_pipeline(self):
        """Test: same query produces same output"""
        from brain.router import route_lane
        from brain.memory import init_state
        
        query = "write a sorting function"
        
        results = []
        for _ in range(3):
            lane = route_lane(query)
            state = init_state(query, lane)
            results.append((lane, state["session_id"]))
        
        # All lanes should be the same
        assert all(r[0] == results[0][0] for r in results)
        # All session IDs should be the same
        assert all(r[1] == results[0][1] for r in results)


class TestSkillExecution:
    """Test skill execution through the orchestration."""

    def test_skill_registry_discovery(self):
        """Test that skills are discovered"""
        from orchestration import get_skill_registry
        
        registry = get_skill_registry()
        registry.discover()
        
        skills = registry.list_all()
        assert len(skills) > 0
        
        # Should have skills with different backends
        by_backend = registry.list_by_backend()
        assert "local" in by_backend

    def test_skill_execution_local(self):
        """Test executing a local skill"""
        from orchestration import get_skill_executor
        
        executor = get_skill_executor()
        
        # Try to execute a known skill
        result = executor.execute(
            "rest_api",
            {"raw": "scaffold rest api for User", "task": "scaffold-rest-api", "resource": "User"},
            {"session_id": "test123"},
        )
        
        # Should return a result (success may be False if execution fails)
        assert "success" in result
        assert "output" in result

    def test_backend_routing(self):
        """Test that backends are routed correctly"""
        from orchestration import get_skill_registry
        
        registry = get_skill_registry()
        registry.discover()
        
        # Check for skills with different backends
        local_skills = registry.list_all(backend_filter="local")
        assert len(local_skills) > 0


class TestLanes:
    """Test lane execution."""

    def test_coding_lane(self):
        """Test coding lane run"""
        from lanes.coding.lane import run
        from brain.memory import init_state
        
        state = init_state("write a hello world function", "coding")
        result = run(state)
        
        assert "final_output" in result
        assert "history" in result

    def test_business_logic_lane(self):
        """Test business_logic lane run"""
        from lanes.business_logic.lane import run
        from brain.memory import init_state
        
        state = init_state("create approval policy for budgets over 1000", "business_logic")
        result = run(state)
        
        assert "final_output" in result

    def test_tool_calling_lane(self):
        """Test tool_calling lane run"""
        from lanes.tool_calling.lane import run
        from brain.memory import init_state
        
        state = init_state("call api to validate email", "tool_calling")
        result = run(state)
        
        assert "final_output" in result

    def test_cross_domain_lane(self):
        """Test cross_domain lane run"""
        from lanes.cross_domain.lane import run
        from brain.memory import init_state
        
        state = init_state("analyze AI trends", "cross_domain")
        result = run(state)
        
        assert "final_output" in result


class TestAPIServer:
    """Test API server endpoints."""

    def test_health_endpoint(self):
        """Test /health endpoint"""
        from fastapi.testclient import TestClient
        from api.server import app
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200

    def test_task_endpoint(self):
        """Test /task endpoint"""
        from fastapi.testclient import TestClient
        from api.server import app
        
        client = TestClient(app)
        response = client.post("/task", json={"query": "write hello world"})
        
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_skills_endpoint(self):
        """Test /skills endpoint"""
        from fastapi.testclient import TestClient
        from api.server import app
        
        client = TestClient(app)
        response = client.get("/skills")
        
        assert response.status_code == 200
        data = response.json()
        assert "skills" in data


class TestSecurity:
    """Test security features."""

    def test_injection_blocked_in_preaudit(self):
        """Test that injection is blocked at pre-audit"""
        from reasoning.math_engine import ReasoningEngine
        
        re = ReasoningEngine()
        result = re.decide(
            task={"raw": "echo $HOME; ls", "task": "test"},
            skill_candidates=["skill1"],
        )
        
        assert result.audit_ok is False

    def test_template_injection_blocked(self):
        """Test template injection is blocked"""
        from reasoning.math_engine import PreAudit
        
        pa = PreAudit()
        ok, issues = pa.run({"raw": "{{ __import__('os').system('ls') }}", "task": "test"})
        
        assert ok is False

    def test_path_traversal_blocked(self):
        """Test path traversal is blocked"""
        from reasoning.math_engine import PreAudit
        
        pa = PreAudit()
        ok, issues = pa.run({"raw": "../../etc/passwd", "task": "test"})
        
        assert ok is False


class TestDeterminism:
    """Test deterministic behavior guarantees."""

    def test_same_query_same_session_id(self):
        """Test same query produces same session ID"""
        from brain.memory import init_state
        
        query = "test query"
        id1 = init_state(query, "coding")["session_id"]
        id2 = init_state(query, "coding")["session_id"]
        
        assert id1 == id2

    def test_different_query_different_session_id(self):
        """Test different queries produce different session IDs"""
        from brain.memory import init_state
        
        id1 = init_state("query one", "coding")["session_id"]
        id2 = init_state("query two", "coding")["session_id"]
        
        assert id1 != id2

    def test_same_lane_routing(self):
        """Test same query always routes to same lane"""
        from brain.router import route_lane
        
        query = "write python code"
        
        results = [route_lane(query) for _ in range(10)]
        assert len(set(results)) == 1  # all same

    def test_retrieval_deterministic(self):
        """Test retrieval returns same order for same query"""
        from retrieval.hybrid import retrieve
        
        r1 = retrieve("python function", "coding")
        r2 = retrieve("python function", "coding")
        
        # Same IDs in same order
        assert [c["id"] for c in r1] == [c["id"] for c in r2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])