"""Dialogue Policy — deterministic state machine with transitions."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DialogueState(Enum):
    """Dialogue states."""
    IDLE = "idle"
    GREETING = "greeting"
    AWAITING_INPUT = "awaiting_input"
    PROCESSING = "processing"
    CONFIRMING = "confirming"
    HELPING = "helping"
    ERROR = "error"
    CLOSING = "closing"


@dataclass
class DialogueAction:
    """An action to take in the dialogue."""
    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    response_template: Optional[str] = None


@dataclass
class DialogueTurn:
    """A single dialogue turn."""
    state: DialogueState
    nlu_result: Any
    action: Optional[DialogueAction] = None
    response: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


class DialogueStateMachine:
    """Deterministic dialogue state machine with explicit transitions."""

    def __init__(self):
        self.current_state = DialogueState.IDLE
        self.context: Dict[str, Any] = {}
        self.history: List[DialogueTurn] = []
        self._transitions = self._build_transitions()

    def _build_transitions(self) -> Dict[DialogueState, Dict[str, DialogueState]]:
        """Build the state transition map."""
        return {
            DialogueState.IDLE: {
                "greeting": DialogueState.GREETING,
                "command": DialogueState.PROCESSING,
                "question": DialogueState.PROCESSING,
            },
            DialogueState.GREETING: {
                "any": DialogueState.AWAITING_INPUT,
            },
            DialogueState.AWAITING_INPUT: {
                "greeting": DialogueState.GREETING,
                "help": DialogueState.HELPING,
                "command": DialogueState.PROCESSING,
                "question": DialogueState.PROCESSING,
                "confirm": DialogueState.CONFIRMING,
                "deny": DialogueState.PROCESSING,
                "farewell": DialogueState.CLOSING,
            },
            DialogueState.PROCESSING: {
                "success": DialogueState.AWAITING_INPUT,
                "needs_confirmation": DialogueState.CONFIRMING,
                "error": DialogueState.ERROR,
            },
            DialogueState.CONFIRMING: {
                "confirm": DialogueState.AWAITING_INPUT,
                "deny": DialogueState.AWAITING_INPUT,
                "timeout": DialogueState.ERROR,
            },
            DialogueState.HELPING: {
                "resolved": DialogueState.AWAITING_INPUT,
            },
            DialogueState.ERROR: {
                "retry": DialogueState.AWAITING_INPUT,
                "exit": DialogueState.CLOSING,
            },
            DialogueState.CLOSING: {
                "reset": DialogueState.IDLE,
            },
        }

    def transition(self, event: str) -> DialogueState:
        """Transition to next state based on event."""
        possible = self._transitions.get(self.current_state, {})
        
        if event in possible:
            new_state = possible[event]
        elif "any" in possible:
            new_state = possible["any"]
        else:
            new_state = self.current_state
        
        logger.info(f"State transition: {self.current_state.value} -> {new_state.value} (event: {event})")
        self.current_state = new_state
        return new_state

    def get_next_action(self, nlu_result: Any) -> DialogueAction:
        """Determine the next action based on current state and NLU result."""
        intent = nlu_result.intent.value if hasattr(nlu_result, 'intent') else "unknown"
        
        if self.current_state == DialogueState.IDLE:
            return DialogueAction(
                action_type="greet",
                response_template="Hello! How can I help you today?"
            )
        
        elif self.current_state == DialogueState.GREETING:
            return DialogueAction(
                action_type="acknowledge_greeting",
                response_template="Hi there! What would you like to do?"
            )
        
        elif self.current_state == DialogueState.AWAITING_INPUT:
            if intent == "help":
                return DialogueAction(
                    action_type="provide_help",
                    response_template="I can help with coding tasks, answer questions, or assist with various commands."
                )
            elif intent == "question":
                return DialogueAction(
                    action_type="process_question",
                    params={"slots": nlu_result.slots, "entities": nlu_result.entities}
                )
            elif intent == "command":
                return DialogueAction(
                    action_type="execute_command",
                    params={"slots": nlu_result.slots, "entities": nlu_result.entities}
                )
            elif intent == "farewell":
                return DialogueAction(
                    action_type="farewell",
                    response_template="Goodbye! Have a great day."
                )
            else:
                return DialogueAction(
                    action_type="clarify",
                    response_template="I'm not sure I understand. Could you rephrase that?"
                )
        
        elif self.current_state == DialogueState.PROCESSING:
            return DialogueAction(
                action_type="process",
                params={"nlu_result": nlu_result.to_dict()}
            )
        
        elif self.current_state == DialogueState.CONFIRMING:
            return DialogueAction(
                action_type="request_confirmation",
                response_template="Can you confirm this action?"
            )
        
        elif self.current_state == DialogueState.HELPING:
            return DialogueAction(
                action_type="provide_help",
                response_template="Here's some help information..."
            )
        
        elif self.current_state == DialogueState.ERROR:
            return DialogueAction(
                action_type="error_recovery",
                response_template="Something went wrong. Would you like to try again?"
            )
        
        elif self.current_state == DialogueState.CLOSING:
            return DialogueAction(
                action_type="close",
                response_template="Conversation ended."
            )
        
        return DialogueAction(action_type="noop")

    def update_context(self, key: str, value: Any) -> None:
        """Update dialogue context."""
        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Get value from context."""
        return self.context.get(key, default)

    def record_turn(self, turn: DialogueTurn) -> None:
        """Record a dialogue turn in history."""
        self.history.append(turn)

    def reset(self) -> None:
        """Reset to initial state."""
        self.current_state = DialogueState.IDLE
        self.context.clear()
        self.history.clear()


class ProbabilisticPolicy:
    """Probabilistic rule-based dialogue policy (like OpenDial).
    
    Uses weighted rules and Bayesian-style state updates.
    """

    def __init__(self):
        self.rules: List[Dict[str, Any]] = []
        self.state_beliefs: Dict[str, float] = {}

    def add_rule(self, condition: Callable, action: DialogueAction, weight: float = 1.0) -> None:
        """Add a probabilistic rule."""
        self.rules.append({
            "condition": condition,
            "action": action,
            "weight": weight,
        })

    def select_action(self, context: Dict[str, Any]) -> DialogueAction:
        """Select action using weighted rule matching."""
        matching_rules = []
        
        for rule in self.rules:
            try:
                if rule["condition"](context):
                    matching_rules.append(rule)
            except Exception:
                continue
        
        if not matching_rules:
            return DialogueAction(action_type="fallback")
        
        total_weight = sum(r["weight"] for r in matching_rules)
        
        import random
        random.seed(context.get("seed", None))
        r = random.random() * total_weight
        
        cumulative = 0
        for rule in matching_rules:
            cumulative += rule["weight"]
            if r <= cumulative:
                return rule["action"]
        
        return matching_rules[-1]["action"]

    def update_belief(self, key: str, value: float) -> None:
        """Update belief state (Bayesian-style)."""
        if key in self.state_beliefs:
            prior = self.state_beliefs[key]
            posterior = prior * value
            self.state_beliefs[key] = posterior / (posterior + (1 - prior) * (1 - value) + 1e-10)
        else:
            self.state_beliefs[key] = value


def create_default_policy() -> DialogueStateMachine:
    """Create default deterministic dialogue policy."""
    return DialogueStateMachine()