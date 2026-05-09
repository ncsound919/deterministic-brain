"""reward_tracker.py

Multi-step delayed reward attribution for the learning pipeline.

Connects action (impression/send) → engagement (open/click) → conversion
(purchase/signup) chains back to the decision that triggered them.

Uses time-decayed attribution:
  - Linear:   reward decays evenly over the attribution window
  - First-touch: full credit to the first action in the chain
  - Last-touch:  full credit to the last action before conversion
  - Position:   U-shaped — 40% first, 40% last, 20% middle spread

Feeds delayed rewards into:
  1. ContextualBandit.observe()       — per-arm Q-value updates
  2. SkillEvolver.track()             — per-skill success/latency tracking
  3. Evolution weight store           — long-running performance data

Zero external dependencies — pure Python, deterministic attribution math.
"""

from __future__ import annotations
import json
import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class ActionRecord:
    action_id: str
    session_id: str
    arm_id: str                 # bandit arm / skill that executed
    action_type: str            # impression, send_email, send_sms, ...
    context: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    reward_attributed: float = 0.0  # total reward credited here so far

    def to_dict(self) -> Dict:
        return {
            "action_id": self.action_id,
            "session_id": self.session_id,
            "arm_id": self.arm_id,
            "action_type": self.action_type,
            "context": self.context,
            "ts": self.ts,
            "reward_attributed": self.reward_attributed,
        }

    @staticmethod
    def from_dict(d: Dict) -> "ActionRecord":
        return ActionRecord(
            action_id=d["action_id"],
            session_id=d["session_id"],
            arm_id=d["arm_id"],
            action_type=d["action_type"],
            context=d.get("context", {}),
            ts=d.get("ts", 0.0),
            reward_attributed=d.get("reward_attributed", 0.0),
        )


@dataclass
class ConversionEvent:
    event_id: str
    session_id: str
    event_type: str             # purchase, signup, click, open, unsubscribe
    value: float                # revenue or score (negative for unsubscribe)
    ts: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "value": self.value,
            "ts": self.ts,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Attribution models
# ---------------------------------------------------------------------------

class AttributionModel:
    """Base class for reward distribution over a chain of actions.

    Each model receives a list of (ActionRecord, time_delta_days)
    and returns a list of floats allocating the conversion value.
    """

    def distribute(self, actions: List[Tuple[ActionRecord, float]],
                   total_value: float) -> List[float]:
        raise NotImplementedError


class LinearAttribution(AttributionModel):
    """Equal credit to every action in the attribution window."""

    def distribute(self, actions: List[Tuple[ActionRecord, float]],
                   total_value: float) -> List[float]:
        n = max(len(actions), 1)
        return [total_value / n] * n


class TimeDecayAttribution(AttributionModel):
    """Exponential decay: recency-weighted (most recent gets most)."""

    def __init__(self, half_life_days: float = 7.0):
        self.half_life = half_life_days

    def distribute(self, actions: List[Tuple[ActionRecord, float]],
                   total_value: float) -> List[float]:
        if not actions:
            return []
        weights = []
        for _, delta_days in actions:
            w = math.exp(-delta_days / self.half_life * 0.693)
            weights.append(w)
        total_w = sum(weights) or 1.0
        return [total_value * (w / total_w) for w in weights]


class FirstTouchAttribution(AttributionModel):
    """Full credit to the first action."""

    def distribute(self, actions: List[Tuple[ActionRecord, float]],
                   total_value: float) -> List[float]:
        if not actions:
            return []
        result = [0.0] * len(actions)
        result[0] = total_value
        return result


class LastTouchAttribution(AttributionModel):
    """Full credit to the last action."""

    def distribute(self, actions: List[Tuple[ActionRecord, float]],
                   total_value: float) -> List[float]:
        if not actions:
            return []
        result = [0.0] * len(actions)
        result[-1] = total_value
        return result


class UShapedAttribution(AttributionModel):
    """40% first touch, 40% last touch, 20% split across middle."""

    def distribute(self, actions: List[Tuple[ActionRecord, float]],
                   total_value: float) -> List[float]:
        n = len(actions)
        if n == 0:
            return []
        if n == 1:
            return [total_value]
        if n == 2:
            return [total_value * 0.5, total_value * 0.5]
        first = total_value * 0.4
        last  = total_value * 0.4
        middle_per = (total_value * 0.2) / max(n - 2, 1)
        result = [first] + [middle_per] * (n - 2) + [last]
        return result


# ---------------------------------------------------------------------------
# Reward Tracker
# ---------------------------------------------------------------------------

class RewardTracker:
    """Tracks action → conversion chains with delayed reward attribution.

    Usage:
        rt = RewardTracker()
        rt.record_action("a1", session_id="s1", arm_id="email_offer", action_type="send_email")
        # ... time passes ...
        rt.record_conversion("c1", session_id="s1", event_type="purchase", value=49.99)
        # Attributions flushed automatically; pull to bandit/evolver:
        all_attributions = rt.flush_attributions()
        for arm_id, reward in all_attributions:
            bandit.observe(arm_id, reward)
    """

    ATTRIBUTION_WINDOW_DAYS: float = 30.0
    MAX_ACTIONS_PER_SESSION: int = 200

    def __init__(self, storage_path: str = ".reward_tracker_state.json",
                 attribution_model: Optional[AttributionModel] = None):
        self.storage_path = Path(storage_path)
        self.model = attribution_model or TimeDecayAttribution(half_life_days=7.0)
        self._actions: Dict[str, Dict[str, ActionRecord]] = defaultdict(dict)  # session → action_id → record
        self._conversions: List[ConversionEvent] = []
        self._attributions: Dict[str, float] = defaultdict(float)               # arm_id → accumulated reward
        self._load()

    # ── Recording ─────────────────────────────────────────────────

    def record_action(self, action_id: str, session_id: str, arm_id: str,
                      action_type: str = "send",
                      context: Optional[Dict] = None) -> ActionRecord:
        session = self._actions[session_id]
        if len(session) >= self.MAX_ACTIONS_PER_SESSION:
            oldest = min(session.keys(), key=lambda k: session[k].ts)
            del session[oldest]
        rec = ActionRecord(
            action_id=action_id, session_id=session_id,
            arm_id=arm_id, action_type=action_type,
            context=context or {},
        )
        session[action_id] = rec
        self._save()
        return rec

    def record_conversion(self, event_id: str, session_id: str,
                          event_type: str, value: float,
                          metadata: Optional[Dict] = None) -> ConversionEvent:
        ev = ConversionEvent(
            event_id=event_id, session_id=session_id,
            event_type=event_type, value=value,
            metadata=metadata or {},
        )
        self._conversions.append(ev)

        self._attribute(ev)
        self._save()
        return ev

    # ── Attribution engine ────────────────────────────────────────

    def _attribute(self, conversion: ConversionEvent) -> None:
        """Distribute conversion value across eligible actions in its session."""
        session_actions = self._actions.get(conversion.session_id)
        if not session_actions:
            return

        eligible: List[Tuple[ActionRecord, float]] = []
        for rec in session_actions.values():
            delta_sec = conversion.ts - rec.ts
            if delta_sec < 0:
                continue
            delta_days = delta_sec / 86400.0
            if delta_days > self.ATTRIBUTION_WINDOW_DAYS:
                continue
            eligible.append((rec, delta_days))

        if not eligible:
            return

        eligible.sort(key=lambda x: x[0].ts)
        shares = self.model.distribute(eligible, conversion.value)

        for (rec, _), share in zip(eligible, shares):
            rec.reward_attributed += share
            self._attributions[rec.arm_id] += share

    def manual_attribute(self, arm_id: str, reward: float) -> None:
        """Directly credit a reward to an arm (for manual overrides)."""
        self._attributions[arm_id] += reward

    def _replay_all(self) -> None:
        """Re-attribute all conversions (e.g. after model change)."""
        self._attributions.clear()
        for a_records in self._actions.values():
            for rec in a_records.values():
                rec.reward_attributed = 0.0
        for conv in self._conversions:
            self._attribute(conv)

    # ── Flush to learning systems ─────────────────────────────────

    def flush_attributions(self) -> List[Tuple[str, float]]:
        """Return and clear pending attributions."""
        result = list(self._attributions.items())
        self._attributions.clear()
        self._save()
        return result

    def feed_bandit(self, bandit) -> int:
        """Push all pending attributions into a ContextualBandit instance."""
        pending = self.flush_attributions()
        for arm_id, reward in pending:
            bandit.observe(arm_id, reward)
        return len(pending)

    def feed_evolver(self, evolver) -> int:
        """Push all pending attributions into a SkillEvolver instance."""
        pending = self.flush_attributions()
        for arm_id, reward in pending:
            success = reward > 1.0           # conversions with revenue > $1
            evolver.track(arm_id, success=success, confidence=min(reward / 10.0, 1.0))
        return len(pending)

    def feed_weight_store(self, weight_store) -> int:
        """Push pending attributions into a WeightStore (updates routing weights)."""
        pending = self.flush_attributions()
        for arm_id, reward in pending:
            old_w = weight_store.get(arm_id, 1.0)
            new_w = old_w * 0.7 + max(0.1, min(reward, 2.0)) * 0.3
            weight_store.set(arm_id, round(new_w, 4))
        return len(pending)

    # ── Stats and pruning ─────────────────────────────────────────

    def get_session_summary(self, session_id: str) -> Dict:
        actions = self._actions.get(session_id, {})
        relevant_convs = [c for c in self._conversions if c.session_id == session_id]
        return {
            "session_id": session_id,
            "actions_count": len(actions),
            "conversion_count": len(relevant_convs),
            "total_revenue": sum(c.value for c in relevant_convs
                                 if c.event_type == "purchase" and c.value > 0),
            "arms_used": list({a.arm_id for a in actions.values()}),
            "attributed_reward": sum(a.reward_attributed for a in actions.values()),
        }

    def get_arm_summary(self, arm_id: str) -> Dict:
        actions = []
        for session in self._actions.values():
            for act in session.values():
                if act.arm_id == arm_id:
                    actions.append(act)
        return {
            "arm_id": arm_id,
            "total_actions": len(actions),
            "total_attributed_reward": sum(a.reward_attributed for a in actions),
            "avg_reward_per_action": round(
                sum(a.reward_attributed for a in actions) / max(len(actions), 1), 4
            ),
        }

    def prune_sessions(self, max_age_days: float = 30.0) -> int:
        cutoff = time.time() - max_age_days * 86400
        to_delete = []
        for sid, actions in self._actions.items():
            newest = max((a.ts for a in actions.values()), default=0)
            if newest < cutoff:
                to_delete.append(sid)
        for sid in to_delete:
            del self._actions[sid]
        # Also prune old conversions
        self._conversions = [c for c in self._conversions if c.ts >= cutoff]
        self._save()
        return len(to_delete)

    def stats(self) -> Dict:
        total_actions = sum(len(s) for s in self._actions.values())
        total_convs = len(self._conversions)
        total_revenue = sum(c.value for c in self._conversions if c.value > 0)
        return {
            "active_sessions": len(self._actions),
            "total_actions_recorded": total_actions,
            "total_conversions": total_convs,
            "total_revenue": round(total_revenue, 2),
            "pending_attributions": len(self._attributions),
            "arms_with_pending": list(self._attributions.keys()),
        }

    # ── Persistence ──────────────────────────────────────────────

    def _save(self) -> None:
        data = {
            "actions": {
                sid: {aid: a.to_dict() for aid, a in acts.items()}
                for sid, acts in self._actions.items()
            },
            "conversions": [c.to_dict() for c in self._conversions[-500:]],
            "attributions": dict(self._attributions),
            "saved_ts": time.time(),
        }
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text())
            for sid, acts in data.get("actions", {}).items():
                for aid, ad in acts.items():
                    self._actions[sid][aid] = ActionRecord.from_dict(ad)
            self._conversions = [ConversionEvent(
                event_id=c["event_id"], session_id=c["session_id"],
                event_type=c["event_type"], value=c["value"],
                ts=c.get("ts", 0.0), metadata=c.get("metadata", {}),
            ) for c in data.get("conversions", [])]
            self._attributions = defaultdict(float, data.get("attributions", {}))
        except (json.JSONDecodeError, IOError):
            pass

    def export(self) -> Dict:
        return {
            "actions": {
                sid: {aid: a.to_dict() for aid, a in acts.items()}
                for sid, acts in self._actions.items()
            },
            "conversions": [c.to_dict() for c in self._conversions],
            "attributions": dict(self._attributions),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_tracker: Optional[RewardTracker] = None


def get_reward_tracker() -> RewardTracker:
    global _tracker
    if _tracker is None:
        _tracker = RewardTracker()
    return _tracker


# ---------------------------------------------------------------------------
# Event-bus integration
# ---------------------------------------------------------------------------

def connect_tracker_listeners(tracker: Optional[RewardTracker] = None) -> None:
    """Wire the reward tracker to the event bus for automatic attribution."""
    rt = tracker or get_reward_tracker()
    try:
        from orchestration.event_bus import event_bus

        event_bus.subscribe("action_recorded",
            lambda **kw: rt.record_action(
                kw.get("action_id", ""), kw.get("session_id", ""),
                kw.get("arm_id", "unknown"), kw.get("action_type", "send"),
                kw.get("context")))

        event_bus.subscribe("conversion_event",
            lambda **kw: rt.record_conversion(
                kw.get("event_id", ""), kw.get("session_id", ""),
                kw.get("event_type", "conversion"),
                float(kw.get("value", 0.0)),
                kw.get("metadata")))

        # Auto-feed evolver on autodream
        def _on_autodream(**kw):
            try:
                from evolution.skill_evolver import SkillEvolver
                evolver = SkillEvolver()
                rt.feed_evolver(evolver)
            except Exception:
                pass
        event_bus.subscribe("autodream_run", _on_autodream)

        # Auto-feed bandit on autodream
        def _on_autodream_bandit(**kw):
            try:
                from reasoning.contextual_bandit import get_bandit
                rt.feed_bandit(get_bandit())
            except Exception:
                pass
        event_bus.subscribe("autodream_run", _on_autodream_bandit)

    except ImportError:
        pass
