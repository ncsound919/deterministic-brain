"""Unified Dialogue Pipeline — combines all 5 layers into a deterministic conversation system."""
from __future__ import annotations
import logging
from typing import Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DialogueResult:
    """Result of a complete dialogue turn."""
    input_text: str
    normalized_text: str
    intent: str
    intent_confidence: float
    slots: Dict[str, str]
    entities: list
    state: str
    action: str
    response: str
    session_id: str


class DialoguePipeline:
    """Complete 5-layer dialogue pipeline:
    
    1. Input Normalization - text cleanup, spelling, canonicalization
    2. NLU Layer - intent classification and slot/entity extraction
    3. Dialogue Policy - deterministic state machine transitions
    4. Response Realization - template selection with weighted variation
    5. (Speech Layer - handled separately in voice_mode.py for TTS)
    """

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        
        from dialogue.input_normalizer import InputNormalizer
        from dialogue.nlu_layer import NLUPipeline
        from dialogue.dialogue_policy import DialogueStateMachine
        from dialogue.response_realizer import create_default_realizer
        from dialogue import reproducibility as repro

        self.normalizer = InputNormalizer()
        self._log_event = repro.log_dialogue_event
        self._start_session = repro.start_dialogue_session
        self._end_session = repro.end_dialogue_session
        
        try:
            self.nlu = NLUPipeline()
        except Exception as e:
            logger.warning(f"NLU pipeline initialization warning: {e}")
            from dialogue.nlu_layer import NLUPipeline
            self.nlu = NLUPipeline()
        
        self.policy = DialogueStateMachine()
        self.realizer = create_default_realizer(seed=seed)
        
        self.session_id = self._start_session(seed)

    def process(self, text: str) -> DialogueResult:
        """Process a single dialogue turn through all layers."""
        self._log_event("input", "raw_input", {"text": text}, {})

        norm_result = self.normalizer.normalize(text)
        normalized = norm_result.text
        
        self._log_event("normalization", "normalized", 
                          {"original": text}, {"normalized": normalized, "corrections": norm_result.corrections})

        nlu_result = self.nlu.process(normalized)
        
        self._log_event("nlu", "parsed",
                          {"normalized": normalized},
                          nlu_result.to_dict())

        event = nlu_result.intent.value
        self.policy.transition(event)
        
        action = self.policy.get_next_action(nlu_result)
        
        self._log_event("policy", "state_transition",
                          {"intent": event, "previous_state": self.policy.current_state.value},
                          {"action": action.action_type, "params": action.params})

        if action.response_template:
            response_result = self.realizer.realize(action.action_type, nlu_result.slots)
            response = response_result.text
        else:
            response = f"Processing: {nlu_result.intent.value}"

        self._log_event("realization", "response_generated",
                          {"action": action.action_type, "slots": nlu_result.slots},
                          {"response": response})

        return DialogueResult(
            input_text=text,
            normalized_text=normalized,
            intent=nlu_result.intent.value,
            intent_confidence=nlu_result.intent_confidence,
            slots=nlu_result.slots,
            entities=[e.to_dict() for e in nlu_result.entities],
            state=self.policy.current_state.value,
            action=action.action_type,
            response=response,
            session_id=self.session_id,
        )

    def reset(self) -> None:
        """Reset the dialogue state."""
        self.policy.reset()
        self.session_id = self._start_session(self.seed)

    def close(self) -> None:
        """Close the session and save logs."""
        self._end_session()


def create_dialogue_pipeline(seed: Optional[int] = None) -> DialoguePipeline:
    """Create a new dialogue pipeline."""
    return DialoguePipeline(seed=seed)


def process_dialogue_turn(text: str, seed: Optional[int] = None) -> DialogueResult:
    """Convenience function to process a single turn."""
    pipeline = create_dialogue_pipeline(seed=seed)
    result = pipeline.process(text)
    pipeline.close()
    return result