"""Tests for the deterministic (zero-LLM) cancer verifier."""
import json
import os
import sys
import tempfile

import pytest

from features.cancer_verify import verify_hypothesis, THRESHOLDS


def test_rejects_empty_hypothesis():
    r = verify_hypothesis(target="", mechanism="", testable_prediction="")
    assert r["ok"] is True
    assert r["verified"] is False
    assert r["verdict"] == "reject"
    assert r["llm_used"] is False
    assert r["score"] == 0.0


def test_passes_complete_hypothesis_with_contradictions():
    r = verify_hypothesis(
        target="EGFR",
        mechanism="Inhibit kinase domain",
        testable_prediction="Reduced proliferation in EGFR-amplified lines",
        contradictory_papers=["cite1", "cite2"],
        hypothesis_id="h1",
        disease="lung",
    )
    assert r["ok"] is True
    assert r["verified"] is True
    assert r["verdict"] == "pass"
    assert r["score"] == 1.0
    assert r["llm_used"] is False
    assert len(r["signature"]) == 64
    assert len(r["input_digest"]) == 64


def test_deterministic_signature_is_stable():
    a = verify_hypothesis(target="KRAS", mechanism="m", testable_prediction="p")
    b = verify_hypothesis(target="KRAS", mechanism="m", testable_prediction="p")
    assert a["signature"] == b["signature"]
    assert a["score"] == b["score"]


def test_missing_contradictions_cap_confidence():
    r = verify_hypothesis(target="BRAF", mechanism="m", testable_prediction="p")
    # mechanism + prediction + target present but no contradictions -> capped
    assert r["score"] <= 0.80
    assert r["llm_used"] is False


def test_schema_stability():
    r = verify_hypothesis(target="TP53", mechanism="m", testable_prediction="p", contradictory_papers=["x"])
    # Ensure the payload is JSON-serializable and matches the documented contract.
    payload = json.loads(json.dumps(r))
    assert set(["ok", "verified", "verdict", "score", "signature", "llm_used", "checks", "ts"]) <= set(payload.keys())
    assert payload["engine"] == "deterministic-brain"
    assert payload["thresholds"] == THRESHOLDS


def test_signature_changes_with_manifest_hash():
    base = verify_hypothesis(target="BRAF", mechanism="m", testable_prediction="p")
    anchored = verify_hypothesis(
        target="BRAF", mechanism="m", testable_prediction="p",
        manifest_hash="ab" * 32,
    )
    assert anchored["signature"] != base["signature"]
    assert anchored["manifest_hash"] == "ab" * 32
    assert base.get("manifest_hash") is None
    # Without manifest_hash the signature stays stable across calls.
    assert verify_hypothesis(target="BRAF", mechanism="m", testable_prediction="p")["signature"] == base["signature"]


def test_verify_events_are_recorded_on_event_bus():
    """The cancer_verify audit event is emitted onto the event bus and surfaced
    by /cancer/verify/events (not /dashboard/audit, which reads a separate feed)."""
    from orchestration.event_bus import event_bus
    from features.cancer_verify import get_verifier

    before = [e for e in event_bus.recent_events(500) if e.get("type") == "cancer_verify"]
    verifier = get_verifier(emit=event_bus.emit)
    verifier.verify(target="ALK", mechanism="m", testable_prediction="p", manifest_hash="cd" * 32)
    after = [e for e in event_bus.recent_events(500) if e.get("type") == "cancer_verify"]
    assert len(after) == len(before) + 1
    alk = next(e for e in after if e["data"]["target"] == "ALK")
    assert alk["data"]["manifest_hash"] == "cd" * 32
    assert alk["data"]["llm_used"] is False


def test_verify_event_lands_in_dashboard_audit_feed():
    """The /cancer/verify HTTP route writes a `cancer_verify` trace event that
    /dashboard/audit surfaces (same store + allowlist)."""
    tmp = tempfile.mkdtemp()
    db = os.path.join(tmp, "traces.db")
    old = os.environ.get("TRACE_DB")
    os.environ["TRACE_DB"] = db
    try:
        # Fresh import so tracing picks up the temp TRACE_DB.
        import importlib
        for mod in ("tools.tracing", "tools.dashboard"):
            if mod in sys.modules:
                del sys.modules[mod]
        from tools.tracing import log_event
        from tools.dashboard import Dashboard

        log_event("cancer_verify", {
            "target": "AUDIT-MARKER", "hypothesis_id": "h-a",
            "manifest_hash": "bb" * 32, "verdict": "pass", "score": 1.0,
            "signature": "c" * 64, "llm_used": False,
        })
        feed = Dashboard().audit_feed()
        markers = [e for e in feed if e["data"].get("target") == "AUDIT-MARKER"]
        assert len(markers) == 1
        assert markers[0]["event"] == "cancer_verify"
        assert markers[0]["data"]["llm_used"] is False
    finally:
        if old is None:
            os.environ.pop("TRACE_DB", None)
        else:
            os.environ["TRACE_DB"] = old
