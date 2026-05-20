"""Event Classifier — maps raw telemetry to Traffic Light zones and priority scores."""
from __future__ import annotations

import re
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

from coo.state import TrafficLightZone, Constitution

_TIER_PRIORITY_BOOST = {1: 1.2, 2: 1.0, 3: 0.8}

_REPO_TS_ERROR_PATTERNS = [
    (re.compile(r"ts\d+", re.IGNORECASE), "TypeScript compilation error"),
    (re.compile(r"SyntaxError|IndentationError|NameError|TypeError|ReferenceError"), "Python runtime error"),
    (re.compile(r"ConnectionError|Timeout|ECONNREFUSED|ETIMEDOUT"), "Network/connection failure"),
    (re.compile(r"Permission Denied|403|401|Unauthorized"), "Authentication/permission error"),
    (re.compile(r"null|NaN|undefined|Cannot read|is not a function"), "Null/undefined error"),
    (re.compile(r"OutOfMemory|OOM|heap|memory"), "Memory exhaustion"),
    (re.compile(r"Database|postgres|mysql|sqlite|query"), "Database error"),
]


def _diagnose_from_message(message: str) -> str:
    if not message:
        return "Unknown issue — additional telemetry required"
    msg_lower = message.lower()
    for pattern, label in _REPO_TS_ERROR_PATTERNS:
        if pattern.search(msg_lower):
            return label
    # Fallback: take first 100 chars of error
    return message[:120].strip()


@dataclass
class ClassificationResult:
    zone: TrafficLightZone
    priority_score: float
    diagnosis: str
    proposed_fix: str
    zone_reason: str
    autoaction: bool = field(init=False)

    def __post_init__(self):
        self.autoaction = self.zone.autoaction


class EventClassifier:
    """Classifies raw webhook events into Traffic Light zones with priority and diagnosis."""

    def __init__(self, constitution: Optional[Constitution] = None):
        self._constitution = constitution or Constitution()

    def classify(self, raw_event: Dict[str, Any]) -> ClassificationResult:
        event_type = raw_event.get("event_type", "").lower()
        severity = float(raw_event.get("severity", 0.0))
        product_id = raw_event.get("product_id", "unknown")
        tier = int(raw_event.get("tier", 2))
        error_msg = raw_event.get("error_message", raw_event.get("message", ""))
        details = raw_event.get("details", {})

        zone = TrafficLightZone.from_event(event_type, severity)

        base_priority = _TIER_PRIORITY_BOOST.get(tier, 1.0)

        if zone == TrafficLightZone.RED:
            priority = 0.90 * base_priority
            reason = f"Red-zone event: {event_type}"
            fix = self._fix_for_red(event_type, details)
        elif zone == TrafficLightZone.YELLOW:
            priority = 0.50 * base_priority
            reason = f"Yellow-zone event: {event_type}"
            fix = self._fix_for_yellow(event_type, error_msg)
        else:
            priority = 0.10 * base_priority
            reason = f"Green-zone event: {event_type} — auto-executable"
            fix = self._fix_for_green(event_type)

        diagnosis = _diagnose_from_message(error_msg)

        return ClassificationResult(
            zone=zone,
            priority_score=round(min(priority, 1.0), 4),
            diagnosis=diagnosis,
            proposed_fix=fix,
            zone_reason=reason,
        )

    def _fix_for_red(self, event_type: str, details: Dict) -> str:
        if event_type == "security_alert":
            return (
                "HALT and escalate to principal. "
                "Security event detected — do not auto-remediate. "
                "Isolate affected service and await manual review."
            )
        if event_type == "data_exfiltration":
            return (
                "IMMEDIATE REVOCATION: Rotate all API keys on affected service. "
                "Revoke suspicious sessions. Notify security team. "
                "Do not proceed until principal approves."
            )
        return f"Red-zone event '{event_type}' requires immediate human intervention. Do not act autonomously."

    def _fix_for_yellow(self, event_type: str, error_msg: str) -> str:
        if event_type == "build_failure":
            diag = _diagnose_from_message(error_msg)
            return (
                f"DIAGNOSIS: {diag}\n"
                "PROPOSED: Review failing CI step. Identify root file(s). "
                "Apply minimal patch. Open GitHub Issue with PR preview. "
                "Await issue close to auto-merge."
            )
        if event_type == "exception":
            return (
                f"DIAGNOSIS: {error_msg[:80]}\n"
                "PROPOSED: Identify affected endpoint/function. "
                "Add error boundary or try-except fallback. "
                "Draft patch. Open GitHub Issue. Await approval."
            )
        return (
            f"Yellow-zone event: {event_type}\n"
            "PROPOSED: Analyze telemetry. Identify root cause. "
            "Draft minimal fix. Open GitHub Issue for human review."
        )

    def _fix_for_green(self, event_type: str) -> str:
        if event_type == "cache_clear":
            return "EXECUTE: Clear application cache. Re-verify service health. Log result."
        if event_type == "dependency_update":
            return "EXECUTE: Update dependency lockfile. Run tests. Verify build. Commit if green."
        if event_type == "server_restart":
            return "EXECUTE: Restart staging service. Wait for health check. Confirm uptime."
        return f"AUTO-EXECUTE: {event_type} is classified green. Apply fix directly and log."


_classifier_instance: Optional[EventClassifier] = None


def get_classifier() -> EventClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = EventClassifier()
    return _classifier_instance