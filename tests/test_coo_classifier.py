"""Tests for the COO Brain classifier."""
from __future__ import annotations

import pytest
from coo.classifier import EventClassifier, ClassificationResult, get_classifier


class TestEventClassifierZoneClassification:
    def test_red_zone_from_event_type(self):
        c = EventClassifier()
        result = c.classify({"event_type": "security_alert", "product_id": "claw-protect"})
        assert result.zone.value == "red"
        assert result.autoaction is False

    def test_red_zone_from_severity(self):
        c = EventClassifier()
        result = c.classify({"event_type": "exception", "severity": 0.9, "product_id": "openhub"})
        assert result.zone.value == "red"
        assert result.autoaction is False

    def test_yellow_zone_build_failure(self):
        c = EventClassifier()
        result = c.classify({"event_type": "build_failure", "product_id": "ul2"})
        assert result.zone.value == "yellow"
        assert result.autoaction is False

    def test_yellow_zone_from_severity(self):
        c = EventClassifier()
        result = c.classify({"event_type": "exception", "severity": 0.3, "product_id": "bbtech"})
        assert result.zone.value == "yellow"

    def test_green_zone_cache_clear(self):
        c = EventClassifier()
        result = c.classify({"event_type": "cache_clear", "product_id": "claw-protect"})
        assert result.zone.value == "green"
        assert result.autoaction is True

    def test_green_zone_dependency_update(self):
        c = EventClassifier()
        result = c.classify({"event_type": "dependency_update", "product_id": "openhub"})
        assert result.zone.value == "green"


class TestEventClassifierPriorityScoring:
    def test_priority_from_zone(self):
        c = EventClassifier()
        r = c.classify({"event_type": "security_alert", "product_id": "claw-protect"})
        assert r.priority_score >= 0.8

        r2 = c.classify({"event_type": "build_failure", "product_id": "openhub"})
        assert r2.priority_score >= 0.3
        assert r2.priority_score < 0.8

        r3 = c.classify({"event_type": "cache_clear", "product_id": "ul2"})
        assert r3.priority_score < 0.3

    def test_priority_from_tier(self):
        c = EventClassifier()
        # Tier 1 products get priority boost
        r_tier1 = c.classify(
            {"event_type": "build_failure", "product_id": "claw-protect", "tier": 1}
        )
        # Tier 3 products get lower priority
        r_tier3 = c.classify(
            {"event_type": "build_failure", "product_id": "aetherdesk", "tier": 3}
        )
        assert r_tier1.priority_score > r_tier3.priority_score


class TestEventClassifierDiagnosis:
    def test_diagnosis_for_build_failure(self):
        c = EventClassifier()
        result = c.classify(
            {
                "event_type": "build_failure",
                "product_id": "openhub",
                "error_message": "TypeScript error in AgentFleet.tsx",
            }
        )
        assert "build" in result.diagnosis.lower() or "ts" in result.diagnosis.lower() or "error" in result.diagnosis.lower()
        assert result.proposed_fix is not None
        assert len(result.proposed_fix) > 10

    def test_diagnosis_for_exception(self):
        c = EventClassifier()
        result = c.classify(
            {
                "event_type": "exception",
                "product_id": "claw-protect",
                "error_message": "ConnectionError in dashboard.py",
            }
        )
        assert result.diagnosis is not None
        assert result.zone.value == "yellow"

    def test_diagnosis_for_security_alert(self):
        c = EventClassifier()
        result = c.classify(
            {
                "event_type": "security_alert",
                "product_id": "claw-protect",
                "error_message": "Prompt injection detected in user input",
            }
        )
        assert result.zone.value == "red"
        assert "security" in result.diagnosis.lower() or "injection" in result.diagnosis.lower()


class TestClassifierSingleton:
    def test_get_classifier_returns_same_instance(self):
        c1 = get_classifier()
        c2 = get_classifier()
        assert c1 is c2

    def test_classifier_is_event_classifier(self):
        c = get_classifier()
        assert isinstance(c, EventClassifier)