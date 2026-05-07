"""Self-Healing Test Framework for Deterministic-Brain E2E Tests.

Detection → Diagnosis → Repair → Validate cycle for test stability.

Usage:
    # Enable in conftest.py
    pytest_plugins = ['self_healing.plugin']
    
    # Or run with plugin
    pytest tests/e2e/ -v --self-healing
"""
from self_healing.healer import Healer, create_healer, FailureType, HealRecord
from self_healing.fuzzy_matcher import FuzzyMatcher, IntentFuzzyMatcher, create_fuzzy_matcher, create_intent_matcher
from self_healing.state_replayer import StateReplayer, create_state_replayer, Turn, DialogueState
from self_healing.pattern_healer import PatternHealer, ResponseComparator, create_pattern_healer, create_comparator
from self_healing.golden_manager import GoldenManager, create_golden_manager, GoldenRecord, RegenerationPolicy

__all__ = [
    "Healer",
    "create_healer",
    "FailureType", 
    "HealRecord",
    "FuzzyMatcher",
    "IntentFuzzyMatcher",
    "create_fuzzy_matcher",
    "create_intent_matcher",
    "StateReplayer",
    "create_state_replayer",
    "Turn",
    "DialogueState",
    "PatternHealer",
    "ResponseComparator",
    "create_pattern_healer",
    "create_comparator",
    "GoldenManager",
    "create_golden_manager",
    "GoldenRecord",
    "RegenerationPolicy",
]