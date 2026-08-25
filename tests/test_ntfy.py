"""Tests for the deterministic brain's Open-Chat / ntfy reporting tools.

Covers the ntfy publisher that lets the brain report and communicate through
Draymond's Open-Chat connection (same ntfy topics Draymond uses). No network:
the module's urlopen is monkeypatched.

Run with:  pytest tests/test_ntfy.py -v
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools import ntfy  # noqa: E402


class FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return b"{}"


def _capture(monkeypatch, result_status=200):
    """Install a fake urlopen on tools.ntfy; returns the recorder dict."""
    captured = {}

    class FakeURLopener:
        def __call__(self, req, timeout=15):
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["body"] = json.loads(req.data.decode())
            return FakeResponse(result_status)

    monkeypatch.setattr(ntfy, "urlopen", FakeURLopener())
    return captured


class TestPublishNtfy:
    def test_publishes_full_payload(self, monkeypatch):
        captured = _capture(monkeypatch)

        result = ntfy.publish_ntfy(
            title="Brain · test", message="hello", tags=["report"], priority=5,
            topic="topic-x", click="https://draymond.overlay365.com",
        )
        assert result["ok"] is True
        assert captured["method"] == "POST"
        assert captured["body"]["topic"] == "topic-x"
        assert captured["body"]["title"] == "Brain · test"
        assert captured["body"]["message"] == "hello"
        assert captured["body"]["tags"] == ["report"]
        assert captured["body"]["priority"] == 5
        assert captured["body"]["click"] == "https://draymond.overlay365.com"

    def test_missing_topic_is_fail_soft(self):
        result = ntfy.publish_ntfy(title="t", message="m", topic="")
        assert result["ok"] is False
        assert "topic" in result["error"]

    def test_http_error_is_fail_soft(self, monkeypatch):
        from urllib.error import HTTPError

        def boom(req, timeout=15):
            raise HTTPError(req.full_url, 500, "err", {}, None)

        monkeypatch.setattr(ntfy, "urlopen", boom)
        result = ntfy.publish_ntfy(title="t", message="m", topic="topic-x")
        assert result["ok"] is False
        assert result["status"] == 500


class TestNotifyOpenChat:
    def test_defaults_to_results_topic_and_adds_report(self, monkeypatch):
        captured = _capture(monkeypatch)

        result = ntfy.notify_openchat("title", "message")
        assert result["ok"] is True
        assert captured["body"]["topic"] == "ov365-mucwehxf720s"  # NTFY_TOPIC_RESULTS
        assert "report" in captured["body"]["tags"]

    def test_speak_adds_call_tag(self, monkeypatch):
        captured = _capture(monkeypatch)

        ntfy.notify_openchat("title", "message", speak=True)
        assert "call" in captured["body"]["tags"]


class TestReportBrain:
    def test_level_tag_and_title(self, monkeypatch):
        captured = _capture(monkeypatch)

        result = ntfy.report_brain(task="NBA ingest", summary="computed 12 players", level="warning")
        assert result["ok"] is True
        assert captured["body"]["title"] == "Brain · NBA ingest"
        assert captured["body"]["message"] == "computed 12 players"
        assert "warning" in captured["body"]["tags"]
        assert "report" in captured["body"]["tags"]
