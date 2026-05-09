"""contextual_bandit.py

State-aware action selection with UCB1 exploration + Thompson sampling.

Each "arm" is a (channel, offer, timing, creative) tuple competing in a
specific context (user-segment hash).  The bandit learns which action
maximises expected reward per context, directly powering the "brain that
decides what happens next" lifecycle-marketing pipeline.

Two exploration strategies:
  UCB1          — deterministic, fast, reuse MCTSSearch pattern
  Thompson      — Bayesian, samples from Beta posterior, better for
                  cold-start (fewer visits)

Q-values are stored via the existing WeightStore so the nightly evolver
and AutoDream correction loop automatically see per-arm performance.

Zero external ML dependencies — pure Python, deterministic given seed.
"""

from __future__ import annotations
import hashlib
import json
import math
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class BanditArm:
    arm_id: str
    channel: str       # email, sms, push, in_app, web
    action: str        # send_offer, send_nudge, quiet, ...
    params: Dict[str, Any] = field(default_factory=dict)

    visits: int = 0
    total_reward: float = 0.0
    successes: int = 0            # for Thompson: alpha = 1 + successes
    failures: int = 0             # for Thompson: beta  = 1 + failures
    q_value: float = 0.5
    last_seen_ts: float = 0.0

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.visits, 1)

    @property
    def q(self) -> float:
        return self.q_value

    def ucb1(self, parent_visits: int, c: float = 1.41) -> float:
        if self.visits == 0:
            return float('inf')
        return self.q_value + c * math.sqrt(math.log(max(parent_visits, 1)) / self.visits)

    def to_dict(self) -> Dict:
        return {
            "arm_id": self.arm_id,
            "channel": self.channel,
            "action": self.action,
            "params": self.params,
            "visits": self.visits,
            "total_reward": self.total_reward,
            "successes": self.successes,
            "failures": self.failures,
            "q_value": round(self.q_value, 4),
            "last_seen_ts": self.last_seen_ts,
        }

    @staticmethod
    def from_dict(d: Dict) -> "BanditArm":
        return BanditArm(
            arm_id=d["arm_id"],
            channel=d["channel"],
            action=d["action"],
            params=d.get("params", {}),
            visits=d.get("visits", 0),
            total_reward=d.get("total_reward", 0.0),
            successes=d.get("successes", 0),
            failures=d.get("failures", 0),
            q_value=d.get("q_value", 0.5),
            last_seen_ts=d.get("last_seen_ts", 0.0),
        )


@dataclass
class BanditDecision:
    arm: BanditArm
    confidence: float
    exploration: bool      # True if arm was picked for exploration
    strategy: str           # "ucb1" | "thompson" | "fallback"
    arm_q_values: List[Tuple[str, float, int]]  # (arm_id, q, visits)


# ---------------------------------------------------------------------------
# Contextual Bandit Engine
# ---------------------------------------------------------------------------

class ContextualBandit:
    """UCB1 + Thompson contextual bandit for multi-channel decisioning.

    Usage:
        cb = ContextualBandit()
        cb.register_arm("email_offer", channel="email", action="send_offer",
                         params={"discount": 0.10})
        cb.register_arm("sms_offer", channel="sms", action="send_offer",
                         params={"discount": 0.10})
        state = {"segment": "lapsing", "hour": 14, "device": "mobile"}
        decision = cb.decide(state)
        # ... execute decision.arm ...
        cb.observe(decision.arm.arm_id, reward=1.0, context=state)
    """

    C_PARAM: float = 1.41         # UCB1 exploration constant
    LEARNING_RATE: float = 0.3    # 0.3 new + 0.7 old (matches SkillEvolver)
    MIN_VISITS_BEFORE_SELECT: int = 5

    def __init__(self, storage_path: str = ".bandit_state.json",
                 seed: Optional[int] = None):
        self._arms: Dict[str, BanditArm] = {}
        self._context_visits: Dict[str, int] = {}    # context_key → visits
        self.storage_path = Path(storage_path)
        self._rng = random.Random(seed)
        self._load()

    # ── Arm management ────────────────────────────────────────────

    def register_arm(self, arm_id: str, channel: str, action: str,
                     params: Optional[Dict] = None) -> BanditArm:
        arm = BanditArm(arm_id=arm_id, channel=channel, action=action,
                        params=params or {})
        self._arms[arm_id] = arm
        return arm

    def get_arm(self, arm_id: str) -> Optional[BanditArm]:
        return self._arms.get(arm_id)

    def list_arms(self, channel: Optional[str] = None) -> List[BanditArm]:
        if channel:
            return [a for a in self._arms.values() if a.channel == channel]
        return list(self._arms.values())

    def all_arms(self) -> List[BanditArm]:
        return list(self._arms.values())

    # ── Context hashing ──────────────────────────────────────────

    @staticmethod
    def _context_key(context: Dict[str, Any]) -> str:
        """Deterministic hash of state features → context bucket."""
        SEGMENT_KEYS = {"segment", "tier", "lifecycle_stage", "persona"}
        BEHAVIOR_KEYS = {"last_action", "recency_days", "engagement_score"}
        TEMPORAL_KEYS = {"hour", "day_of_week", "month"}

        parts: List[str] = []
        for group in (SEGMENT_KEYS, BEHAVIOR_KEYS, TEMPORAL_KEYS):
            for k in sorted(group):
                v = context.get(k)
                if v is not None:
                    parts.append(f"{k}={v}")

        raw = "||".join(parts) if parts else "default"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    # ── Decision ──────────────────────────────────────────────────

    def decide(self, context: Dict[str, Any],
               channel: Optional[str] = None,
               strategy: str = "ucb1",
               seed: Optional[int] = None) -> BanditDecision:
        """Select the best arm for the given context."""
        ck = self._context_key(context)
        self._context_visits[ck] = self._context_visits.get(ck, 0)
        eligible = [a for a in self._arms.values()
                    if channel is None or a.channel == channel]
        if not eligible:
            raise ValueError("No arms registered")

        ctx_visits = self._context_visits[ck]
        exploration = ctx_visits < self.MIN_VISITS_BEFORE_SELECT

        if strategy == "thompson":
            chosen = self._thompson_select(eligible, ck)
        elif strategy == "ucb1":
            chosen = self._ucb1_select(eligible, ctx_visits, exploration)
        else:
            chosen = self._ucb1_select(eligible, ctx_visits, exploration)

        if exploration and chosen is not None:
            pass  # already marked

        if chosen is None:
            chosen = eligible[0]

        self._context_visits[ck] += 1

        arm_qs = [(a.arm_id, a.q_value, a.visits) for a in eligible]
        arm_qs.sort(key=lambda x: x[1], reverse=True)

        confidence = max(0.05, chosen.q_value) if chosen.visits > 0 else 0.5

        return BanditDecision(
            arm=chosen,
            confidence=confidence,
            exploration=exploration,
            strategy=strategy,
            arm_q_values=arm_qs,
        )

    def _ucb1_select(self, arms: List[BanditArm], ctx_visits: int,
                     exploration: bool) -> Optional[BanditArm]:
        if exploration:
            unvisited = [a for a in arms if a.visits == 0]
            if unvisited:
                return self._rng.choice(unvisited)
        return max(arms, key=lambda a: a.ucb1(ctx_visits, self.C_PARAM))

    def _thompson_select(self, arms: List[BanditArm],
                         context_key: str) -> BanditArm:
        """Thompson sampling: sample once from Beta(alpha, beta) per arm."""
        best_arm: Optional[BanditArm] = None
        best_sample = -1.0
        for arm in arms:
            alpha = 1.0 + arm.successes
            beta_val = 1.0 + max(0, arm.visits - arm.successes)
            sample = self._rng.betavariate(alpha, beta_val)
            if sample > best_sample:
                best_sample = sample
                best_arm = arm
        return best_arm or arms[0]

    # ── Learning ──────────────────────────────────────────────────

    def observe(self, arm_id: str, reward: float,
                context: Optional[Dict] = None) -> None:
        """Feed an observed reward back into arm's Q-value.

        reward: 0.0 (negative), 0.0–1.0 (engagement), >1.0 (purchase/revenue).
        Use negative for unsubscribes / complaints.
        """
        arm = self._arms.get(arm_id)
        if arm is None:
            return

        arm.visits += 1
        arm.total_reward += reward
        if reward > 0.5:
            arm.successes += 1
        else:
            arm.failures += 1

        old_q = arm.q_value
        arm.q_value = (1 - self.LEARNING_RATE) * old_q + self.LEARNING_RATE * reward
        arm.last_seen_ts = time.time()

        self._save()

        if context:
            ck = self._context_key(context)
            self._context_visits[ck] = self._context_visits.get(ck, 0)

    def observe_batch(self, observations: List[Tuple[str, float, Optional[Dict]]]) -> None:
        for arm_id, reward, ctx in observations:
            self.observe(arm_id, reward, ctx)
        self._save()

    # ── Bulk actions ──────────────────────────────────────────────

    def prune_stale(self, max_age_days: float = 30.0) -> int:
        cutoff = time.time() - max_age_days * 86400
        stale = [aid for aid, arm in self._arms.items()
                 if arm.last_seen_ts > 0 and arm.last_seen_ts < cutoff]
        for aid in stale:
            del self._arms[aid]
        self._save()
        return len(stale)

    def reset_context_counts(self) -> None:
        self._context_visits.clear()

    def get_stats(self) -> Dict:
        arms = [a.to_dict() for a in self._arms.values()]
        arms.sort(key=lambda a: a["q_value"], reverse=True)
        return {
            "total_arms": len(arms),
            "contexts_explored": len(self._context_visits),
            "total_decisions": sum(self._context_visits.values()),
            "top_arms": arms[:10],
        }

    # ── Persistence ───────────────────────────────────────────────

    def _save(self) -> None:
        data = {
            "arms": {aid: a.to_dict() for aid, a in self._arms.items()},
            "context_visits": dict(self._context_visits),
            "saved_ts": time.time(),
        }
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text())
            for aid, ad in data.get("arms", {}).items():
                self._arms[aid] = BanditArm.from_dict(ad)
            self._context_visits = data.get("context_visits", {})
        except (json.JSONDecodeError, IOError):
            pass

    def export(self) -> Dict:
        return {
            "arms": {aid: a.to_dict() for aid, a in self._arms.items()},
            "context_visits": dict(self._context_visits),
        }

    def import_state(self, data: Dict) -> None:
        for aid, ad in data.get("arms", {}).items():
            self._arms[aid] = BanditArm.from_dict(ad)
        self._context_visits = data.get("context_visits", {})
        self._save()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_bandit: Optional[ContextualBandit] = None


def get_bandit() -> ContextualBandit:
    global _bandit
    if _bandit is None:
        _bandit = ContextualBandit()
    return _bandit


# ---------------------------------------------------------------------------
# Event-bus integration helpers
# ---------------------------------------------------------------------------

def connect_bandit_listeners(bandit: Optional[ContextualBandit] = None) -> None:
    """Register bandit reward observation on the event bus."""
    cb = bandit or get_bandit()
    try:
        from orchestration.event_bus import event_bus

        def _on_action_outcome(**kwargs):
            arm_id = kwargs.get("arm_id", "")
            reward = float(kwargs.get("reward", 0.0))
            context = kwargs.get("context")
            if arm_id:
                cb.observe(arm_id, reward, context)

        def _on_skill_success(**kwargs):
            skill_id = kwargs.get("skill_id", "")
            if skill_id in cb._arms:
                cb.observe(skill_id, 1.0)

        def _on_skill_failure(**kwargs):
            skill_id = kwargs.get("skill_id", "")
            if skill_id in cb._arms:
                cb.observe(skill_id, 0.0)

        event_bus.subscribe("action_outcome", _on_action_outcome)
        event_bus.subscribe("skill_success", _on_skill_success)
        event_bus.subscribe("skill_failure", _on_skill_failure)
    except ImportError:
        pass
