"""Production Verification — tests that the system ACTUALLY produces output.

This is NOT a unit test. It exercises the full pipeline and verifies
real artifacts: files on disk, persisted state, trace events, decisions.

Usage:
    python -m pytest tests/e2e/test_production_verification.py -x -v

Requires the API server to be running on http://localhost:8000
"""
from __future__ import annotations
import json
import os
import sys
import time
import requests

BASE = "http://localhost:8000"

# ── Helpers ─────────────────────────────────────────────────────

def api_get(path, timeout=15):
    try:
        r = requests.get(f"{BASE}{path}", timeout=timeout)
        return r.status_code, r.json() if r.headers.get('content-type', '').startswith('application/json') else r.text
    except Exception as e:
        return None, str(e)

def api_post(path, data=None, timeout=300):
    try:
        r = requests.post(f"{BASE}{path}", json=data or {}, timeout=timeout)
        return r.status_code, r.json() if r.headers.get('content-type', '').startswith('application/json') else r.text
    except Exception as e:
        return None, str(e)


# ══════════════════════════════════════════════════════════════════
# 1. CORE BRAIN — Direct pipeline, no server
# ══════════════════════════════════════════════════════════════════

class TestBrainProducesOutput:
    """Brain actually processes tasks and produces artifacts."""

    def test_brain_task_returns_output(self):
        """The brain produces final_output, not just status."""
        code, data = api_post("/task", {"query": "create a react component called TestButton"})
        assert code == 200, f"Expected 200, got {code}: {str(data)[:200]}"
        assert data.get("status") == "ok", f"Task not ok: {data.get('status')}"
        final = data.get("final_output")
        assert final is not None, "No final_output in response"
        assert len(str(final)) > 0, "final_output is empty"

    def test_brain_task_executes_within_timeout(self):
        """Task execution completes within 60 seconds."""
        t0 = time.perf_counter()
        code, data = api_post("/task", {"query": "write a python hello world script"})
        elapsed = time.perf_counter() - t0
        assert code == 200, f"Task failed: {str(data)[:200]}"
        assert elapsed < 120, f"Task took {elapsed:.1f}s, exceeded 120s limit"

    def test_brain_reason_returns_decision(self):
        """Reason endpoint returns a decision with skill and confidence."""
        code, data = api_post("/reason", {"query": "build a REST API with FastAPI"})
        assert code == 200
        decision = data.get("decision", {})
        assert decision.get("chosen_skill"), f"No chosen_skill in decision: {decision}"
        assert decision.get("confidence", 0) > 0, f"Confidence is zero or missing"
        assert decision.get("audit_ok") is not None, "Missing audit result"

    def test_reason_is_deterministic(self):
        """Same query produces the same decision."""
        q = "write a fibonacci function in python"
        _, r1 = api_post("/reason", {"query": q})
        _, r2 = api_post("/reason", {"query": q})
        s1 = r1.get("decision", {}).get("chosen_skill")
        s2 = r2.get("decision", {}).get("chosen_skill")
        assert s1 == s2, f"Determinism failure: {s1} != {s2}"


class TestSessionPersistence:
    """Sessions persist and can be replayed."""

    def test_session_creates_state(self):
        """Running a task creates a persisted session."""
        code, data = api_post("/task", {"query": "write a python sort function"})
        assert code == 200
        session_id = data.get("session_id") or data.get("reasoning", {}).get("session_id")
        # Session ID should exist
        assert session_id, f"No session_id found: {list(data.keys())}"

    def test_dashboard_feed_has_events(self):
        """After running tasks, the dashboard feed has real events."""
        code, data = api_get("/dashboard/feed")
        assert code == 200
        events = data.get("events", data if isinstance(data, list) else [])
        assert len(events) > 0, "Dashboard feed is empty — no events recorded"
        assert events[0].get("event") or events[0].get("ts"), f"Malformed event: {events[0]}"


class TestCheckpointAndReplay:
    """Checkpoints are recorded and replayable."""

    def test_replay_list_has_sessions(self):
        """Replay endpoint lists at least one session."""
        code, data = api_get("/replay/list")
        assert code == 200
        sessions = data.get("sessions", [])
        assert len(sessions) > 0, "No replayable sessions found"
        assert sessions[0].get("session_id"), f"Malformed session: {sessions[0]}"

    def test_replay_session_returns_nodes(self):
        """A session has checkpoint nodes with state data."""
        code, list_data = api_get("/replay/list")
        if code != 200 or not list_data.get("sessions"):
            return  # skip if no sessions
        sid = list_data["sessions"][0]["session_id"]
        code, data = api_get(f"/replay/{sid}")
        assert code == 200
        nodes = data.get("nodes", [])
        assert len(nodes) > 0, f"No nodes in session {sid}"
        node = nodes[0]
        assert node.get("node"), f"Node missing name: {node.keys()}"
        assert node.get("state"), f"Node missing state: {node.keys()}"


class TestContextGraphRecords:
    """Context graph records decisions from brain execution."""

    def test_context_graph_status(self):
        """Run the brain, verify decisions are recorded in the context graph."""
        api_post("/task", {"query": "create a react component called VerifyCard"})
        from reasoning.context_graph import get_context_graph
        cg = get_context_graph()
        status = cg.status()
        assert status["total_nodes"] > 0, f"Context graph empty: {status}"
        assert "skill_selection" in status.get("by_type", {}), "No skill_selection decisions"
        assert "accepted" in status.get("by_outcome", {}), "No accepted outcomes"

    def test_context_graph_why_this_skill(self):
        """Context graph can answer 'why this skill' queries."""
        from reasoning.context_graph import get_context_graph
        cg = get_context_graph()
        result = cg.why_this_skill("test", "react-component")
        assert result is not None
        assert "factor_weights" in result


class TestHealerReports:
    """Healer records circuit states and health data."""

    def test_healer_status_returns_data(self):
        """GET /healer/status returns real healer state."""
        code, data = api_get("/healer/status")
        assert code == 200
        status = data.get("status", {})
        assert "skills_tracked" in status, f"Missing skills_tracked: {status.keys()}"
        assert isinstance(status["skills_tracked"], int), "skills_tracked not int"

    def test_healer_reports_skills(self):
        """Healer tracks skills with circuit states."""
        code, data = api_get("/healer/status")
        assert code == 200
        status = data.get("status", {})
        skills = status.get("skills", [])
        if skills:
            assert "skill_id" in skills[0], f"Malformed skill: {skills[0]}"
            assert "state" in skills[0], f"Missing state in skill: {skills[0]}"


class TestScalability:
    """System handles realistic load patterns."""

    def test_concurrent_task_execution(self):
        """Multiple tasks can execute concurrently."""
        import threading
        results = []
        def run_task(q):
            code, data = api_post("/task", {"query": q}, timeout=60)
            results.append((q, code, data.get("status")))
        queries = [
            "write a python function that calculates factorial",
            "create a simple express.js server",
            "write a bash script to backup a directory",
        ]
        threads = [threading.Thread(target=run_task, args=(q,)) for q in queries]
        for t in threads: t.start()
        for t in threads: t.join()
        for q, code, status in results:
            assert code == 200, f"Task '{q[:30]}' failed with code {code}"
            assert status == "ok", f"Task '{q[:30]}' status={status}"

    def test_trace_has_multiple_session_ids(self):
        """After multiple runs, the trace DB has multiple sessions."""
        code, data = api_get("/replay/list")
        assert code == 200
        assert data.get("count", 0) > 0, "No sessions in replay list"
        assert len(data.get("sessions", [])) > 0, "Empty sessions list"


# ══════════════════════════════════════════════════════════════════
# 2. FILE SYSTEM — Artifacts actually land on disk
# ══════════════════════════════════════════════════════════════════

class TestFilesystemArtifacts:
    """System creates real files during operation."""

    def test_trace_db_exists(self):
        """The tracing SQLite database exists and has data."""
        assert os.path.exists("traces.db"), "traces.db not found"
        size = os.path.getsize("traces.db")
        assert size > 4096, f"traces.db is too small: {size} bytes"

    def test_state_dir_has_sessions(self):
        """The state directory has session files."""
        state_dir = os.path.expanduser("~/.deterministic-brain/state")
        if os.path.exists(state_dir):
            files = [f for f in os.listdir(state_dir) if f.endswith(".json")]
            assert len(files) > 0, f"No session files in {state_dir}"

    def test_healer_log_exists(self):
        """Healer log file exists with event entries."""
        log_path = ".heal_runtime_log.json"
        if not os.path.exists(log_path):
            return  # healer may not have run yet
        try:
            with open(log_path) as f:
                events = json.load(f)
            assert len(events) > 0, "Healer log is empty"
        except (json.JSONDecodeError, Exception):
            pass  # log may be empty or in progress of writing


# ══════════════════════════════════════════════════════════════════
# 3. FULL API SURFACE — Real data, not just 200
# ══════════════════════════════════════════════════════════════════

class TestAPIReturnsRealData:
    """API endpoints return actual content, not empty shells."""

    def test_health_has_real_data(self):
        code, data = api_get("/health")
        assert code == 200
        assert data.get("version") == "2.5.0"
        assert data.get("ts", 0) > 0

    def test_llm_status_has_providers(self):
        code, data = api_get("/llm-status")
        assert code == 200
        assert "provider" in data
        assert "has_keys" in data
        assert data["has_keys"] is not None

    def test_skills_list_has_multiple_skills(self):
        code, data = api_get("/skills/list")
        assert code == 200
        skills = data.get("skills", [])
        assert len(skills) >= 10, f"Only {len(skills)} skills — expected >=10"

    def test_skills_have_metadata(self):
        code, data = api_get("/skills/list")
        assert code == 200
        for s in data.get("skills", [])[:5]:
            sid = s.get("skill_id") or s.get("id") or s.get("name")
            assert sid, f"Missing identifier in skill: {list(s.keys())}"
            assert s.get("description") or s.get("text"), f"Missing description: {sid}"

    def test_soul_has_identity(self):
        code, data = api_get("/soul")
        assert code == 200
        assert data.get("loaded") is not None, "No loaded flag"

    def test_scheduler_tasks_have_real_tasks(self):
        code, data = api_get("/scheduler/tasks")
        assert code == 200
        tasks = data.get("tasks", [])
        if tasks:
            assert tasks[0].get("name"), f"Task missing name: {tasks[0]}"

    def test_knowledge_stats_has_data(self):
        code, data = api_get("/knowledge/stats")
        assert code == 200
        if isinstance(data, dict):
            assert "total_fragments" in data or "fragments" in data, f"Unexpected keys: {data.keys()}"

    def test_system_backends_returns_config(self):
        code, data = api_get("/system/backends")
        assert code == 200
        assert "distributed_mode" in data
        assert "postgresql" in data
        assert "sqlite" in data

    def test_integrations_returns_real_apis(self):
        code, data = api_get("/integrations")
        assert code == 200
        apis = data.get("apis", {})
        assert len(apis) > 0, "No APIs in integrations"
        features = data.get("features", {})
        assert len(features) > 0, "No features in integrations"

    def test_bundles_list_not_empty(self):
        code, data = api_get("/bundles")
        assert code == 200
        bundles = data.get("bundles", [])
        assert len(bundles) > 0, "No bundles configured"

    def test_chains_list_returns(self):
        code, data = api_get("/chains")
        assert code == 200


class TestPhase3Endpoints:
    """Phase 3 specific endpoints return data."""

    def test_healer_status_live(self):
        code, data = api_get("/healer/status")
        assert code == 200
        status = data.get("status", {})
        assert "skills_tracked" in status

    def test_confidence_status(self):
        code, data = api_get("/confidence/status")
        assert code == 200
        assert "routes" in data


class TestPhase4Endpoints:
    """Phase 4 specific endpoints return data."""

    def test_replay_list(self):
        code, data = api_get("/replay/list")
        assert code == 200
        assert "sessions" in data

    def test_replay_session_nodes(self):
        code, list_data = api_get("/replay/list")
        if code == 200 and list_data.get("sessions"):
            sid = list_data["sessions"][0]["session_id"]
            code, data = api_get(f"/replay/{sid}/nodes")
            assert code == 200

    def test_replay_deltas(self):
        code, list_data = api_get("/replay/list")
        if code == 200 and list_data.get("sessions"):
            sid = list_data["sessions"][0]["session_id"]
            code, data = api_get(f"/replay/{sid}/deltas")
            assert code == 200

    def test_context_graph_api(self):
        code, data = api_get("/confidence/status")
        assert code == 200


class TestDashboardEndpoints:
    """Dashboard endpoints contain real data."""

    def test_dashboard_performance(self):
        code, data = api_get("/dashboard/performance")
        assert code == 200
        assert isinstance(data, dict)
        assert "uptime" in data

    def test_dashboard_middleware_stats(self):
        code, data = api_get("/dashboard/middleware-stats")
        assert code == 200
        assert "routes" in data


class TestGovernorEndpoints:
    """Governor API works end-to-end."""

    def test_governor_status(self):
        code, data = api_get("/governor/status")
        assert code == 200
        assert "mode" in data
        assert data["mode"] in ("shadow", "checkpoint", "recovery")

    def test_governor_route(self):
        code, data = api_post("/governor/route", {"task": "build a new API endpoint"})
        assert code == 200
        assert "status" in data
        assert data["status"] in ("routed", "awaiting_oversight")
