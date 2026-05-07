"""State Replayer for Dialogue State Healing.

Reconstructs and replays dialogue state to identify and fix stuck states.
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DialogueState(Enum):
    """Known dialogue states."""
    IDLE = "idle"
    GREETING = "greeting"
    AWAITING_INPUT = "awaiting_input"
    PROCESSING = "processing"
    CONFIRMING = "confirming"
    HELPING = "helping"
    ERROR = "error"
    CLOSING = "closing"


@dataclass
class Turn:
    """A single dialogue turn."""
    user_input: str
    agent_response: str
    state: str
    slots: Dict[str, str] = field(default_factory=dict)


@dataclass 
class StateSnapshot:
    """Snapshot of dialogue state."""
    state: str
    history: List[Turn]
    context: Dict[str, Any]
    turn_count: int


class StateReplayer:
    """Replays dialogue state to identify and heal stuck conditions."""

    STUCK_THRESHOLD = 3
    STUCK_STATES = ["AWAITING_INPUT", "WAITING"]

    def __init__(self):
        self._transitions: Dict[str, Dict[str, str]] = self._build_transition_map()

    def _build_transition_map(self) -> Dict[str, Dict[str, str]]:
        """Build state transition map."""
        return {
            "idle": {"greeting": "greeting", "command": "processing", "question": "processing"},
            "greeting": {"any": "awaiting_input"},
            "awaiting_input": {
                "greeting": "greeting",
                "help": "helping", 
                "command": "processing",
                "question": "processing",
                "confirm": "confirming",
                "farewell": "closing",
            },
            "processing": {"success": "awaiting_input", "needs_confirmation": "confirming", "error": "error"},
            "confirming": {"confirm": "awaiting_input", "deny": "awaiting_input", "timeout": "error"},
            "helping": {"resolved": "awaiting_input"},
            "error": {"retry": "awaiting_input", "exit": "closing"},
            "closing": {"reset": "idle"},
        }

    def analyze_stuck(self, history: List[Dict[str, Any]], current_state: str) -> Optional[str]:
        """Analyze if state is stuck.
        
        Args:
            history: List of turn dicts with keys: user, agent, state
            current_state: Current state name
        
        Returns:
            Diagnosis string or None if not stuck
        """
        if current_state not in self.STUCK_STATES:
            return None
        
        turns_in_same_state = sum(1 for t in history if t.get("state") == current_state)
        
        if turns_in_same_state >= self.STUCK_THRESHOLD:
            last_user_input = history[-1].get("user", "") if history else ""
            
            return self._diagnose_stuck_reason(current_state, last_user_input, history)
        
        return None

    def _diagnose_stuck_reason(self, state: str, last_input: str, 
                              history: List[Dict[str, Any]]) -> str:
        """Diagnose why state is stuck."""
        if state in ["AWAITING_INPUT", "WAITING"]:
            if not last_input:
                return "Empty user input causing loop"
            
            input_lower = last_input.lower()
            
            if "?" in last_input:
                return "Question without answer - needs clarification path"
            
            if any(kw in input_lower for kw in ["weather", "forecast", "temperature"]):
                return "Weather intent without location - needs slot fill"
            
            if any(kw in input_lower for kw in ["create", "make", "build"]):
                return "Command without object - needs specification"
            
            return f"Unknown input causing stuck: '{last_input[:30]}'"
        
        return f"Unknown stuck condition at {state}"

    def heal_stuck(self, history: List[Dict[str, Any]], current_state: str) -> Optional[List[Dict]]:
        """Generate healed history by injecting clarification.
        
        Args:
            history: Current turn history
            current_state: Current state
        
        Returns:
            Healed history with inserted turns, or None
        """
        diagnosis = self.analyze_stuck(history, current_state)
        if not diagnosis:
            return None
        
        healed = list(history)
        
        if "location" in diagnosis.lower():
            healed.insert(-1, {
                "user": "Raleigh",
                "agent": "Got it, location set to Raleigh.",
                "state": "processing"
            })
            return healed
        
        if "object" in diagnosis.lower():
            healed.insert(-1, {
                "user": "button component",
                "agent": "Creating button component.",
                "state": "processing"
            })
            return healed
        
        if "clarification" in diagnosis.lower():
            healed.insert(-1, {
                "user": "help",
                "agent": "I can help with weather, creating components, and more.",
                "state": "awaiting_input"
            })
            return healed
        
        return None

    def simulate_transition(self, state: str, intent: str) -> str:
        """Simulate state transition.
        
        Args:
            state: Current state
            intent: Intent that occurred
        
        Returns:
            Next state
        """
        transitions = self._transitions.get(state, {})
        
        if intent in transitions:
            return transitions[intent]
        
        if "any" in transitions:
            return transitions["any"]
        
        return state

    def replay_with_injection(self, original_history: List[Dict], 
                            injections: List[Dict]) -> List[Turn]:
        """Replay history with injected turns.
        
        Args:
            original_history: Original turn history
            injections: Turns to inject
        
        Returns:
            Replayed history as Turn objects
        """
        merged = []
        
        for i, turn in enumerate(original_history):
            if i == len(injections):
                break
            if i < len(injections):
                merged.append(Turn(
                    user_input=injections[i].get("user", ""),
                    agent_response=injections[i].get("agent", ""),
                    state=injections[i].get("state", "unknown"),
                ))
            
            merged.append(Turn(
                user_input=turn.get("user", ""),
                agent_response=turn.get("agent", ""),
                state=turn.get("state", "unknown"),
            ))
        
        return merged

    def get_valid_transitions(self, state: str) -> List[str]:
        """Get valid transitions from a state."""
        return list(self._transitions.get(state, {}).keys())


def create_state_replayer() -> StateReplayer:
    """Create a state replayer."""
    return StateReplayer()