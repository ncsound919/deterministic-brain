"""policy_engine.py

Deterministic guardrail gating for every decision the brain makes.

Uses algebraic constraint solving (reusing AlgebraicReasoner) to enforce:
  - Brand safety rules        (no restricted offers to flagged segments)
  - Frequency caps            (max N messages per channel per time window)
  - Channel eligibility       (consent, opt-in status, channel availability)
  - Budget constraints        (remaining budget, CPA / ROAS targets)
  - Compliance rules          (GDPR region blocks, CAN-SPAM unsubscribe windows)
  - Time-of-day / cadence     (quiet hours, max messages per day)

Every decision flows through:  Decision → PolicyEngine.gate(decision, context) → ALLOW | BLOCK

Blocked decisions carry an explainable reason, which can be surfaced in the
operating dashboard or audit trail — no black box, every block is traceable.

Integrates with:
  - PreAudit (math_engine.py)      — static pre-execution checks
  - ContextualBandit.decide()      — bandit arm selection is gated
  - SkillEvolver                   — blocked decisions count as failures

Zero external dependencies — all constraints are pure Python predicates.
"""

from __future__ import annotations
import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from reasoning.math_engine import Constraint, AlgebraicReasoner


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PolicyCategory(str, Enum):
    BRAND_SAFETY = "brand_safety"
    FREQUENCY_CAP = "frequency_cap"
    CHANNEL = "channel_eligibility"
    BUDGET = "budget"
    COMPLIANCE = "compliance"
    CADENCE = "cadence"
    CUSTOM = "custom"


class GateVerdict(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    WARN = "warn"            # allow but log / flag for review


# ---------------------------------------------------------------------------
# Gate Result
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    verdict: GateVerdict
    blocked_by: List[str] = field(default_factory=list)     # policy names that blocked
    warnings: List[str] = field(default_factory=list)
    allowed_by: List[str] = field(default_factory=list)
    gate_duration_ms: float = 0.0
    context_snapshot: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_allowed(self) -> bool:
        return self.verdict != GateVerdict.BLOCK

    def to_dict(self) -> Dict:
        return {
            "verdict": self.verdict.value,
            "blocked_by": self.blocked_by,
            "warnings": self.warnings,
            "allowed_by": self.allowed_by,
            "gate_duration_ms": round(self.gate_duration_ms, 2),
            "context_snapshot": self.context_snapshot,
        }


# ---------------------------------------------------------------------------
# Individual Policy
# ---------------------------------------------------------------------------

@dataclass
class Policy:
    """A single guardrail policy.

    check_fn receives (decision_dict, context_dict) and returns (pass_bool, reason_str).
    """
    name: str
    category: PolicyCategory
    description: str
    check_fn: Callable[[Dict, Dict], Tuple[bool, str]]
    priority: int = 50               # lower = runs first (0 = must run first)
    blocking: bool = True            # False = warn only, don't block

    def evaluate(self, decision: Dict, context: Dict) -> Tuple[bool, str]:
        try:
            return self.check_fn(decision, context)
        except Exception as e:
            return (False, f"{self.name} errored: {e}")


# ---------------------------------------------------------------------------
# Built-in policy constructors
# ---------------------------------------------------------------------------

def _parse_frequency_window(window: str) -> float:
    """Parse '1h', '24h', '7d', '30d' into seconds."""
    import re
    m = re.match(r"(\d+)\s*(h|d|m)", window.strip())
    if not m:
        return 86400  # default 1 day
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "m":
        return n * 60
    if unit == "h":
        return n * 3600
    return n * 86400


def frequency_cap_policy(policy_name: str, channel: str, max_count: int,
                         window: str = "24h") -> Policy:
    """Block if the user has received > max_count messages on `channel` in `window`.

    Requires the context to carry a `recent_sends` dict:
        {channel: [ts1, ts2, ...]}
    """
    window_s = _parse_frequency_window(window)

    def _check(decision: Dict, context: Dict) -> Tuple[bool, str]:
        recent = context.get("recent_sends", {}).get(channel, [])
        cutoff = time.time() - window_s
        count = sum(1 for t in recent if t > cutoff)
        if count >= max_count:
            return (False, f"Frequency cap: {count}/{max_count} {channel} messages in {window}")
        return (True, "")

    return Policy(
        name=policy_name,
        category=PolicyCategory.FREQUENCY_CAP,
        description=f"Max {max_count} {channel} messages per {window}",
        check_fn=_check,
        priority=20,
    )


def brand_safety_policy(policy_name: str, blocked_offers: List[str],
                        blocked_segments: List[str] = None) -> Policy:
    """Block specific offers for specific segments (or globally)."""
    blocked_segments = blocked_segments or []

    def _check(decision: Dict, context: Dict) -> Tuple[bool, str]:
        offer = str(decision.get("offer_id", decision.get("action", ""))).lower()
        segment = str(context.get("segment", "")).lower()

        if blocked_segments and segment not in blocked_segments:
            return (True, "")

        for blocked in blocked_offers:
            if blocked.lower() in offer:
                return (False, f"Brand safety: offer '{offer}' blocked for segment '{segment}'")
        return (True, "")

    return Policy(
        name=policy_name,
        category=PolicyCategory.BRAND_SAFETY,
        description=f"Block offers {blocked_offers} for segments {blocked_segments}",
        check_fn=_check,
        priority=10,
    )


def channel_eligibility_policy(channel: str,
                               consent_required: bool = True) -> Policy:
    """Block if the user hasn't opted into `channel`.

    Requires context["consent"] = {"email": True, "sms": False, ...}
    """
    def _check(decision: Dict, context: Dict) -> Tuple[bool, str]:
        if not consent_required:
            return (True, "")
        consents = context.get("consent", {})
        if not consents.get(channel, False):
            return (False, f"Channel eligibility: no consent for {channel}")
        return (True, "")

    return Policy(
        name=f"channel_consent_{channel}",
        category=PolicyCategory.CHANNEL,
        description=f"Require opt-in consent for {channel}",
        check_fn=_check,
        priority=10,
    )


def budget_policy(policy_name: str, max_spend: float,
                  current_spend_fn: Callable[[], float]) -> Policy:
    """Block if remaining budget is exhausted.

    current_spend_fn is called at gate time (e.g. DB query).
    """
    def _check(decision: Dict, context: Dict) -> Tuple[bool, str]:
        spent = current_spend_fn()
        remaining = max_spend - spent
        if remaining <= 0:
            return (False, f"Budget exhausted: ${spent:.2f} / ${max_spend:.2f}")
        return (True, "")

    return Policy(
        name=policy_name,
        category=PolicyCategory.BUDGET,
        description=f"Max spend ${max_spend}, currently ${current_spend_fn():.2f}",
        check_fn=_check,
        priority=30,
    )


def compliance_gdpr_policy() -> Policy:
    """Block marketing to users in GDPR regions without explicit consent."""
    GDPR_REGIONS = {"eu", "europe", "de", "fr", "es", "it", "nl", "be", "at", "pl",
                    "se", "dk", "fi", "pt", "ie", "gr", "cz", "ro", "hu", "sk", "bg",
                    "hr", "lt", "si", "lv", "ee", "cy", "lu", "mt"}

    def _check(decision: Dict, context: Dict) -> Tuple[bool, str]:
        region = str(context.get("region", context.get("country", ""))).lower()
        if region in GDPR_REGIONS:
            has_explicit = context.get("gdpr_consent", False)
            if not has_explicit:
                return (False, f"GDPR block: no explicit marketing consent for region '{region}'")
        return (True, "")

    return Policy(
        name="gdpr_compliance",
        category=PolicyCategory.COMPLIANCE,
        description="Block marketing in GDPR regions without explicit consent",
        check_fn=_check,
        priority=5,
    )


def quiet_hours_policy(policy_name: str = "quiet_hours",
                       start_hour: int = 22, end_hour: int = 7,
                       tz_offset: int = 0) -> Policy:
    """Block during quiet hours (e.g. 10PM–7AM local time)."""
    def _check(decision: Dict, context: Dict) -> Tuple[bool, str]:
        now = time.time() + tz_offset * 3600
        hour = time.gmtime(now).tm_hour
        if start_hour > end_hour:
            if hour >= start_hour or hour < end_hour:
                return (False, f"Quiet hours: {hour}:00 (blocked {start_hour}-{end_hour})")
        else:
            if start_hour <= hour < end_hour:
                return (False, f"Quiet hours: {hour}:00 (blocked {start_hour}-{end_hour})")
        return (True, "")

    return Policy(
        name=policy_name,
        category=PolicyCategory.CADENCE,
        description=f"No messages between {start_hour}:00 and {end_hour}:00",
        check_fn=_check,
        priority=25,
    )


# ---------------------------------------------------------------------------
# Policy Engine
# ---------------------------------------------------------------------------

class PolicyEngine:
    """Gate every decision through a stack of ordered, explainable policies.

    Usage:
        pe = PolicyEngine()
        pe.register(frequency_cap_policy("email_cap", "email", max_count=5, window="24h"))
        pe.register(compliance_gdpr_policy())
        pe.register(channel_eligibility_policy("email"))

        context = {"consent": {"email": True}, "recent_sends": {"email": [time.time()-10]}}
        decision = {"arm_id": "email_offer", "channel": "email"}

        result = pe.gate(decision, context)
        if result.is_allowed:
            execute(decision)
        else:
            log(f"Blocked: {result.blocked_by}")
    """

    def __init__(self, policies_path: Optional[str] = None):
        self._policies: Dict[str, Policy] = {}       # name → Policy
        self._execution_log: List[Dict] = []
        self._stats: Dict[str, Dict] = defaultdict(lambda: {
            "passed": 0, "blocked": 0, "warned": 0})

        if policies_path:
            self._load_policies_file(policies_path)

    # ── Policy management ─────────────────────────────────────────

    def register(self, policy: Policy) -> None:
        self._policies[policy.name] = policy

    def unregister(self, policy_name: str) -> bool:
        return self._policies.pop(policy_name, None) is not None

    def get(self, policy_name: str) -> Optional[Policy]:
        return self._policies.get(policy_name)

    def list_policies(self) -> List[Dict]:
        return [{
            "name": p.name,
            "category": p.category.value,
            "description": p.description,
            "priority": p.priority,
            "blocking": p.blocking,
        } for p in sorted(self._policies.values(), key=lambda x: x.priority)]

    # ── Gating ────────────────────────────────────────────────────

    def gate(self, decision: Dict, context: Dict) -> GateResult:
        """Run all registered policies in priority order against a decision."""
        t0 = time.perf_counter()
        result = GateResult(verdict=GateVerdict.ALLOW)

        policies = sorted(self._policies.values(), key=lambda p: p.priority)

        for policy in policies:
            passed, reason = policy.evaluate(decision, context)

            if passed:
                result.allowed_by.append(policy.name)
                self._stats[policy.name]["passed"] += 1
            else:
                if policy.blocking:
                    result.verdict = GateVerdict.BLOCK
                    result.blocked_by.append(f"{policy.name}: {reason}")
                    self._stats[policy.name]["blocked"] += 1
                else:
                    result.warnings.append(f"{policy.name}: {reason}")
                    self._stats[policy.name]["warned"] += 1

        result.gate_duration_ms = (time.perf_counter() - t0) * 1000
        result.context_snapshot = {
            "segment": context.get("segment"),
            "channel": context.get("channel", decision.get("channel")),
            "offer": str(decision.get("offer_id", decision.get("action", ""))),
        }

        self._execution_log.append(result.to_dict())
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-500:]

        return result

    def gate_with_algebraic(self, decision: Dict, context: Dict,
                            variables: Dict[str, List],
                            constraints: List[Constraint]) -> GateResult:
        """Gate using both policies AND algebraic constraint solving.

        The algebraic solver handles variable-domain constraints (e.g.
        channel ∈ {email, sms, push}), while policies handle binary checks.
        """
        result = self.gate(decision, context)
        if not result.is_allowed:
            return result

        ar = AlgebraicReasoner()
        for var, domain in variables.items():
            ar.add_variable(var, domain)
        for c in constraints:
            ar.add_constraint(c)

        solution = ar.solve()
        if solution is None:
            result.verdict = GateVerdict.BLOCK
            result.blocked_by.append("algebraic: no consistent assignment found")
            # List which constraints are unsatisfiable
            detail = []
            for c in constraints:
                val = decision.get(c.var)
                if val is not None and not c.satisfied(val):
                    detail.append(c.description or f"{c.var} unsatisfied")
            if detail:
                result.blocked_by[-1] += f" ({'; '.join(detail)})"

        return result

    # ── Stats ─────────────────────────────────────────────────────

    def stats(self) -> Dict:
        return {
            "total_policies": len(self._policies),
            "policy_stats": dict(self._stats),
            "recent_gates": self._execution_log[-20:],
            "block_rate": round(
                sum(1 for g in self._execution_log
                    if g["verdict"] == "block") / max(len(self._execution_log), 1), 4
            ),
        }

    def reset_stats(self) -> None:
        self._stats.clear()
        self._execution_log.clear()

    # ── Persistence ──────────────────────────────────────────────

    def _load_policies_file(self, path: str) -> None:
        """Load pre-defined policies from a JSON config file.

        Example JSON:
        {
          "policies": [
            {
              "type": "frequency_cap",
              "name": "email_24h_cap",
              "channel": "email",
              "max_count": 5,
              "window": "24h"
            }
          ]
        }
        """
        config_path = Path(path)
        if not config_path.exists():
            return
        try:
            data = json.loads(config_path.read_text())
            for pdef in data.get("policies", []):
                ptype = pdef.get("type", "")
                if ptype == "frequency_cap":
                    self.register(frequency_cap_policy(
                        pdef.get("name", "fc"), pdef["channel"],
                        pdef["max_count"], pdef.get("window", "24h")))
                elif ptype == "brand_safety":
                    self.register(brand_safety_policy(
                        pdef.get("name", "bs"), pdef["blocked_offers"],
                        pdef.get("blocked_segments")))
                elif ptype == "channel":
                    self.register(channel_eligibility_policy(
                        pdef["channel"], pdef.get("consent_required", True)))
                elif ptype == "gdpr":
                    self.register(compliance_gdpr_policy())
                elif ptype == "quiet_hours":
                    self.register(quiet_hours_policy(
                        pdef.get("name", "qh"),
                        pdef.get("start_hour", 22),
                        pdef.get("end_hour", 7)))
        except (json.JSONDecodeError, IOError):
            pass


# ---------------------------------------------------------------------------
# Standard policy stack (one-call setup)
# ---------------------------------------------------------------------------

def create_default_policy_engine() -> PolicyEngine:
    """Return a PolicyEngine pre-loaded with sensible defaults.

    These are starting-guardrail defaults. Production deployments should
    customize: add brand-specific blocked offers, real budget tracking,
    and compliance rules tailored to the operating jurisdictions.
    """
    pe = PolicyEngine()

    pe.register(compliance_gdpr_policy())
    pe.register(channel_eligibility_policy("email"))
    pe.register(channel_eligibility_policy("sms"))
    pe.register(channel_eligibility_policy("push"))
    pe.register(frequency_cap_policy("email_24h_cap", "email", max_count=5, window="24h"))
    pe.register(frequency_cap_policy("sms_24h_cap", "sms", max_count=3, window="24h"))
    pe.register(frequency_cap_policy("push_24h_cap", "push", max_count=8, window="24h"))
    # pe.register(quiet_hours_policy())

    return pe


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    global _engine
    if _engine is None:
        _engine = create_default_policy_engine()
    return _engine


def reset_policy_engine() -> PolicyEngine:
    global _engine
    _engine = create_default_policy_engine()
    return _engine
