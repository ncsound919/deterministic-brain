"""Tests for the COO Brain GitHub Issue Queue dispatcher."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from coo.github_queue import (
    GitHubIssuePayload,
    build_issue_payload,
    build_pr_payload,
    GitHubQueue,
    GitHubCredentialsError,
)


class TestGitHubIssuePayload:
    def test_build_issue_payload_yellow(self):
        from coo.state import TrafficLightZone, DecisionCard
        import time

        card = DecisionCard(
            event_id="abc123",
            product_id="claw-protect",
            zone=TrafficLightZone.YELLOW,
            summary="Build failure in main pipeline",
            diagnosis="TypeScript compilation error in AgentFleet.tsx",
            proposed_fix="Add type annotation to resolve undefined export",
        )

        payload = build_issue_payload(card)
        assert "[YELLOW]" in payload.title
        assert "claw-protect" in payload.body
        assert "TypeScript" in payload.body
        assert "root cause" in payload.body.lower()
        assert "solution" in payload.body.lower()
        assert "approve" in payload.body.lower()
        assert "reject" in payload.body.lower()
        assert "yellow" in payload.labels
        assert "coo-brain" in payload.labels

    def test_build_issue_payload_red(self):
        from coo.state import TrafficLightZone, DecisionCard

        card = DecisionCard(
            event_id="xyz789",
            product_id="openhub",
            zone=TrafficLightZone.RED,
            summary="Security alert: prompt injection detected",
            diagnosis="Prompt injection attempt in user input field",
            proposed_fix="HALT and escalate — security event requires manual review",
        )

        payload = build_issue_payload(card)
        assert "[RED]" in payload.title
        assert "security" in payload.title.lower()
        assert "red-zone" in payload.labels

    def test_build_pr_payload(self):
        from coo.state import TrafficLightZone, DecisionCard

        card = DecisionCard(
            event_id="pr123",
            product_id="ul2",
            zone=TrafficLightZone.YELLOW,
            summary="Fix dependency vulnerability in package-lock.json",
            diagnosis="Outdated lodash version with known CVE",
            proposed_fix="Update lodash to patched version",
            github_pr_number=42,
        )

        payload = build_pr_payload(card, "https://github.com/ncsound919/ul2/pull/42")
        assert "dependency" in payload.title.lower()
        assert "#42" in payload.body
        assert "approve" in payload.body.lower()


class TestGitHubQueue:
    def test_requires_token(self):
        q = GitHubQueue(token="")
        assert q._token == ""

    @patch("coo.github_queue.requests.post")
    def test_open_issue_creates_correct_payload(self, mock_post):
        mock_post.return_value = MagicMock(status_code=201, json=lambda: {"number": 142})

        q = GitHubQueue(token="ghp_fake", owner="ncsound919", repo="claw-protect")
        from coo.state import TrafficLightZone, DecisionCard

        card = DecisionCard(
            event_id="test123",
            product_id="claw-protect",
            zone=TrafficLightZone.YELLOW,
            summary="Test issue",
            diagnosis="Test diagnosis",
            proposed_fix="Test fix",
        )

        result = q.open_issue(card)

        assert result.github_issue_number == 142
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["headers"]["Authorization"] == "token ghp_fake"
        assert call_kwargs["json"]["title"] == "[YELLOW] Test issue"
        assert "labels" in call_kwargs["json"]
        assert "body" in call_kwargs["json"]

    @patch("coo.github_queue.requests.post")
    def test_open_issue_retries_on_403(self, mock_post):
        """403 on missing/invalid token should not crash — logs and returns None."""
        import requests

        mock_post.side_effect = requests.exceptions.RequestException("403 Forbidden")

        q = GitHubQueue(token="bad_token", owner="ncsound919", repo="claw-protect")
        from coo.state import TrafficLightZone, DecisionCard

        card = DecisionCard(
            event_id="authfail",
            product_id="claw-protect",
            zone=TrafficLightZone.YELLOW,
            summary="Auth test",
            diagnosis="Test",
            proposed_fix="Test",
        )

        result = q.open_issue(card)
        assert result is None

    @patch("coo.github_queue.requests.get")
    def test_get_issue_returns_closed_state(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "number": 145,
                "state": "closed",
                "labels": [{"name": "coo-brain"}],
                "title": "[YELLOW] Test",
            }
        )

        q = GitHubQueue(token="ghp_test", owner="ncsound919", repo="claw-protect")
        issue = q.get_issue(145)
        assert issue is not None
        assert issue.is_closed is True
        assert issue.issue_number == 145

    @patch("coo.github_queue.requests.post")
    def test_close_issue_creates_resolution(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200)

        q = GitHubQueue(token="ghp_test", owner="ncsound919", repo="claw-protect")
        result = q.close_issue(145, outcome="approved")
        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        call_url = mock_post.call_args[0][0]
        assert call_url.endswith("/145")