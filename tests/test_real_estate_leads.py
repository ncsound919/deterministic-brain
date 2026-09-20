"""Tests for the real_estate_leads lane (House Flip Studio MCP bridge).

The lane's only network call is `_post_json`, so every test injects a canned
JSON-RPC envelope there. Nothing here touches the live House Flip server.
"""
import pytest

from lanes.real_estate_leads import lane


def _envelope(structured=None, is_error=False, text=None):
    content_text = text if text is not None else "{}"
    return {
        "ok": True,
        "status": 200,
        "data": {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": content_text}],
                "structuredContent": structured,
                "isError": is_error,
            },
        },
    }


HUNT_DATA = {
    "scanned": 120,
    "newLeads": 7,
    "duplicates": 30,
    "filtered": 83,
    "filterReasons": {"distress": 40, "affordability": 43},
    "warnings": ["Wake feed slow"],
    "summary": [{"county": "Wake", "houses": 80}, {"county": "Pitt", "houses": 40}],
    "tiers": {"hot": 3, "warm": 2, "cold": 2},
}


def test_call_tool_returns_structured_content(monkeypatch):
    monkeypatch.setattr(lane, "_post_json", lambda *a, **k: _envelope(HUNT_DATA))
    res = lane.call_tool("hunt_leads", {"org_id": "o1"}, "http://localhost:3000", "")
    assert res["ok"] is True
    assert res["data"]["newLeads"] == 7


def test_call_tool_reports_isError(monkeypatch):
    monkeypatch.setattr(
        lane,
        "_post_json",
        lambda *a, **k: _envelope(structured={"error": "Invalid arguments"}, is_error=True),
    )
    res = lane.call_tool("hunt_leads", {}, "http://localhost:3000", "")
    assert res["ok"] is False
    assert "Invalid arguments" in res["error"]


def test_call_tool_reports_unreachable(monkeypatch):
    monkeypatch.setattr(lane, "_post_json", lambda *a, **k: {"ok": False, "error": "unreachable: refused"})
    res = lane.call_tool("hunt_leads", {"org_id": "o1"}, "http://localhost:3000", "")
    assert res["ok"] is False
    assert "unreachable" in res["error"]


def test_hunt_success_folds_into_state(monkeypatch):
    monkeypatch.setattr(lane, "_post_json", lambda *a, **k: _envelope(HUNT_DATA))
    state = {"task": {"action": "hunt", "org_id": "o1", "require_distress": True}, "query": "hunt deals"}
    out = lane.run(state)
    assert out["verification_results"][0]["passed"] is True
    assert out["confidence"] == pytest.approx(0.9)
    assert "New leads: 7" in out["final_output"]
    assert "hot=3" in out["final_output"]
    assert "Wake feed slow" in out["final_output"]
    assert out["candidate_artifacts"][0]["data"]["newLeads"] == 7


def test_hunt_no_new_leads_is_honest_low_confidence(monkeypatch):
    data = dict(HUNT_DATA, newLeads=0)
    monkeypatch.setattr(lane, "_post_json", lambda *a, **k: _envelope(data))
    out = lane.run({"task": {"action": "hunt", "org_id": "o1"}})
    assert out["verification_results"][0]["passed"] is True
    assert out["confidence"] == pytest.approx(0.55)
    assert "New leads: 0" in out["final_output"]


def test_missing_org_id_fails_without_calling(monkeypatch):
    calls = {"n": 0}

    def _boom(*a, **k):
        calls["n"] += 1
        return _envelope(HUNT_DATA)

    monkeypatch.setattr(lane, "_post_json", _boom)
    monkeypatch.delenv("HOUSE_FLIP_ORG_ID", raising=False)
    out = lane.run({"task": {"action": "hunt"}})
    assert calls["n"] == 0
    assert out["verification_results"][0]["passed"] is False
    assert out["confidence"] == pytest.approx(0.1)


def test_list_action_formats_leads(monkeypatch):
    data = {
        "count": 2,
        "leads": [
            {"tier": "hot", "address": "1 A St", "attentionScore": 82, "rating": "high"},
            {"tier": "cold", "address": "2 B St", "attentionScore": 30, "rating": "low"},
        ],
    }
    monkeypatch.setattr(lane, "_post_json", lambda *a, **k: _envelope(data))
    out = lane.run({"task": {"action": "list", "org_id": "o1", "tier": "hot"}})
    assert out["verification_results"][0]["passed"] is True
    assert "[HOT] 1 A St" in out["final_output"]
    assert out["confidence"] == pytest.approx(0.85)


def test_dossier_action_needs_no_org(monkeypatch):
    data = {"dealId": "", "sources": [{"source": "county_tax", "status": "ok"}], "compiledAt": "2026-01-01"}
    monkeypatch.setattr(lane, "_post_json", lambda *a, **k: _envelope(data))
    out = lane.run({"task": {"action": "dossier", "address": "1 A St"}})
    assert out["verification_results"][0]["passed"] is True
    assert "county_tax: ok" in out["final_output"]


def test_build_arguments_omits_absent_keys():
    args = lane._build_arguments("hunt", {"org_id": "o1", "statewide": False, "max_total": 25})
    assert args == {"org_id": "o1", "statewide": False, "max_total": 25}
    assert "counties" not in args
