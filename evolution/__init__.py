"""Evolution — skill performance tracking, weight optimization, and reward attribution.

No external ML dependencies. Uses simple weighted blends of success rate
and latency to adjust skill routing weights over time.

Includes reward_tracker for delayed-reward attribution (multi-step conversion
chains feeding back into bandit weights and skill evolution).
"""
from __future__ import annotations
from .skill_evolver import SkillEvolver
from .nightly_scorer import NightlyScorer
from .weight_store import WeightStore
from .reward_tracker import (
    RewardTracker,
    get_reward_tracker,
    connect_tracker_listeners,
    TimeDecayAttribution,
    LinearAttribution,
    FirstTouchAttribution,
    LastTouchAttribution,
    UShapedAttribution,
    ActionRecord,
    ConversionEvent,
)

__all__ = [
    "SkillEvolver",
    "NightlyScorer",
    "WeightStore",
    "RewardTracker",
    "get_reward_tracker",
    "connect_tracker_listeners",
    "TimeDecayAttribution",
    "LinearAttribution",
    "FirstTouchAttribution",
    "LastTouchAttribution",
    "UShapedAttribution",
    "ActionRecord",
    "ConversionEvent",
]
