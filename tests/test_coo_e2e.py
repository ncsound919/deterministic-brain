"""E2E tests for the full COO Brain pipeline: webhook → classify → issue → resolve."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from coo.state import (
    PortfolioState,
    ProductConfig,
    TrafficLightZone,
)
from coo.classifier import EventClassifier
from coo.github_queue import GitHubQueue
from coo.orchestrator import COOOrchestrator


@pytest.fixture
def orchestrator():
    """Create a test orchestrator with mocked GitHub queue."""
    portfolio = PortfolioState()
    portfolio.register_product(
        ProductConfig(product_id="claw-protect", tier=1, name="Claw Protect")
    )
    portfolio.register_product(
        ProductConfig(product_id="openhub", tier=1, name="OpenHub")
    )
    portfolio.register_product(
        ProductConfig(product_id="ul2", tier=2, name="Uplift Lab")
    )

    classifier = EventClassifier()
    github_queue = GitHubQueue(token="ghp_test", owner="ncsound919", repo="claw-protect")

    return COOOrchestrator(
        portfolio=portfolio,
        classifier=classifier,
        github_queue=github_queue,
    )


class TestE2EFullPipeline:
    """End-to-end tests for the complete COO Brain pipeline."""

    @patch("coo.github_queue.requests.post")
    def test_green_event_auto_executes(self, mock_post, orchestrator):
        """Green events should auto-execute without creating GitHub issues."""
        mock_post.return_value = MagicMock(status_code=201, json=lambda: {"number": 100})

        card = orchestrator.process_event({
            "event_type": "cache_clear",
            "product_id": "claw-protect",
            "severity": 0.0,
            "summary": "Cache bloat detected — clearing",
        })

        assert card is not None
        assert card.zone == TrafficLightZone.GREEN
        assert card.outcome == "auto_executed"
        assert card.resolved is True
        # Green events should NOT open GitHub issues
        mock_post.assert_not_called()

    @patch("coo.github_queue.requests.post")
    def test_yellow_event_opens_github_issue(self, mock_post, orchestrator):
        """Yellow events should open a GitHub Issue and wait for approval."""
        mock_post.return_value = MagicMock(status_code=201, json=lambda: {"number": 142})

        card = orchestrator.process_event({
            "event_type": "build_failure",
            "product_id": "openhub",
            "severity": 0.3,
            "error_message": "TypeScript error in AgentFleet.tsx",
            "summary": "Build failure in main pipeline",
        })

        assert card is not None
        assert card.zone == TrafficLightZone.YELLOW
        assert card.outcome == "pending_review"
        assert card.resolved is False
        assert card.github_issue_number == 142
        mock_post.assert_called_once()

    @patch("coo.github_queue.requests.post")
    def test_red_event_escapes_immediately(self, mock_post, orchestrator):
        """Red events should escalate immediately with RED tag."""
        mock_post.return_value = MagicMock(status_code=201, json=lambda: {"number": 200})

        card = orchestrator.process_event({
            "event_type": "security_alert",
            "product_id": "claw-protect",
            "severity": 0.9,
            "error_message": "Prompt injection detected in user input",
            "summary": "Security alert: prompt injection",
        })

        assert card is not None
        assert card.zone == TrafficLightZone.RED
        assert card.outcome == "escalated"
        assert card.resolved is False
        assert card.github_issue_number == 200
        mock_post.assert_called_once()

    @patch("coo.github_queue.requests.post")
    def test_issue_close_resolves_yellow_card(self, mock_post, orchestrator):
        """Closing a GitHub Issue should resolve the corresponding decision card."""
        mock_post.return_value = MagicMock(status_code=201, json=lambda: {"number": 145})

        # Step 1: Yellow event creates issue
        card = orchestrator.process_event({
            "event_type": "build_failure",
            "product_id": "claw-protect",
            "severity": 0.3,
            "error_message": "ImportError in server.py",
            "summary": "Build failure",
        })

        assert card.github_issue_number == 145
        assert card.resolved is False

        # Step 2: Close the issue (human approval)
        resolved = orchestrator.handle_issue_closed(145, outcome="approved")
        assert resolved is True
        assert card.resolved is True
        assert card.outcome == "approved"

    @patch("coo.github_queue.requests.post")
    def test_unknown_product_is_skipped(self, mock_post, orchestrator):
        """Events for unregistered products should be skipped."""
        card = orchestrator.process_event({
            "event_type": "exception",
            "product_id": "nonexistent-product",
            "severity": 0.5,
        })

        assert card is None
        mock_post.assert_not_called()

    @patch("coo.github_queue.requests.post")
    def test_pending_decisions_returns_unresolved_only(self, mock_post, orchestrator):
        """get_pending_decisions should only return unresolved cards."""
        mock_post.return_value = MagicMock(status_code=201, json=lambda: {"number": 150})

        # Create a yellow event
        orchestrator.process_event({
            "event_type": "build_failure",
            "product_id": "openhub",
            "severity": 0.3,
            "summary": "Build failure",
        })

        # Create a green event (auto-resolved)
        orchestrator.process_event({
            "event_type": "cache_clear",
            "product_id": "claw-protect",
            "severity": 0.0,
            "summary": "Cache clear",
        })

        pending = orchestrator.get_pending_decisions()
        assert len(pending) == 1
        assert pending[0].zone == TrafficLightZone.YELLOW
        assert pending[0].resolved is False

    @patch("coo.github_queue.requests.post")
    def test_full_pipeline_green_yellow_red(self, mock_post, orchestrator):
        """Test all three zones in sequence."""
        mock_post.return_value = MagicMock(status_code=201, json=lambda: {"number": 999})

        # Green
        g = orchestrator.process_event({
            "event_type": "dependency_update",
            "product_id": "claw-protect",
            "severity": 0.0,
            "summary": "Update packages",
        })
        assert g.zone == TrafficLightZone.GREEN
        assert g.resolved is True

        # Yellow
        y = orchestrator.process_event({
            "event_type": "build_failure",
            "product_id": "openhub",
            "severity": 0.3,
            "summary": "CI failed",
        })
        assert y.zone == TrafficLightZone.YELLOW
        assert y.resolved is False

        # Red
        r = orchestrator.process_event({
            "event_type": "security_alert",
            "product_id": "claw-protect",
            "severity": 0.9,
            "error_message": "Data exfiltration pattern detected",
            "summary": "Security alert",
        })
        assert r.zone == TrafficLightZone.RED
        assert r.resolved is False

        # Decision log should have 3 entries
        log = orchestrator.get_decision_log()
        assert len(log) == 3

        # Pending should have 2 (yellow + red)
        pending = orchestrator.get_pending_decisions()
        assert len(pending) == 2

    @patch("coo.github_queue.requests.post")
    def test_tier_affects_priority_score(self, mock_post, orchestrator):
        """Tier 1 products should have higher priority than Tier 3 for same event."""
        # Tier 1 product
        c1 = orchestrator.classifier.classify({
            "event_type": "build_failure",
            "product_id": "claw-protect",
            "tier": 1,
        })
        # Tier 3 product
        c3 = orchestrator.classifier.classify({
            "event_type": "build_failure",
            "product_id": "aetherdesk",
            "tier": 3,
        })
        assert c1.priority_score > c3.priority_score
