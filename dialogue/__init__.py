"""Dialogue System — deterministic voice/dialogue pipeline.

5-Layer Architecture:
1. Input Normalization - text cleanup, spelling tolerance, canonicalization
2. NLU Layer - intent classification and slot/entity extraction (spaCy + rule-based)
3. Dialogue Policy - deterministic state machine with transitions
4. Response Realization - template selection with weighted variation
5. Speech Layer - offline TTS via Piper (in features/voice_mode.py)

Key Features:
- Offline-first: works without cloud APIs for NLU and TTS
- Deterministic: seeded randomness for reproducibility
- Modular: layers can be swapped independently
"""
from dialogue.pipeline import DialoguePipeline, create_dialogue_pipeline, DialogueResult
from dialogue.nlu_layer import NLUPipeline, Intent, NLUResult, Entity
from dialogue.dialogue_policy import DialogueStateMachine, DialogueState, DialogueAction
from dialogue.response_realizer import TemplateRealizer, ResponseTemplate, RealizedResponse
from dialogue.input_normalizer import InputNormalizer, NormalizedInput
from dialogue.reproducibility import (
    ReproducibilityManager,
    start_dialogue_session,
    log_dialogue_event,
    end_dialogue_session,
    replay_session,
)

__all__ = [
    "DialoguePipeline",
    "create_dialogue_pipeline", 
    "DialogueResult",
    "NLUPipeline",
    "Intent",
    "NLUResult",
    "Entity",
    "DialogueStateMachine",
    "DialogueState",
    "DialogueAction",
    "TemplateRealizer",
    "ResponseTemplate",
    "RealizedResponse",
    "InputNormalizer",
    "NormalizedInput",
    "ReproducibilityManager",
    "start_dialogue_session",
    "log_dialogue_event",
    "end_dialogue_session",
    "replay_session",
]