"""NLU Layer — intent classification and slot/entity extraction."""
from __future__ import annotations
import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class Intent(Enum):
    """Known intent types."""
    GREETING = "greeting"
    FAREWELL = "farewell"
    CONFIRM = "confirm"
    DENY = "deny"
    HELP = "help"
    QUESTION = "question"
    COMMAND = "command"
    STATEMENT = "statement"
    UNKNOWN = "unknown"


@dataclass
class Entity:
    """Extracted entity with span and type."""
    text: str
    start: int
    end: int
    entity_type: str
    value: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "type": self.entity_type,
            "value": self.value
        }


@dataclass
class NLUResult:
    """Result of NLU processing."""
    intent: Intent
    intent_confidence: float
    slots: Dict[str, str] = field(default_factory=dict)
    entities: List[Entity] = field(default_factory=list)
    raw_text: str = ""
    normalized_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "confidence": self.intent_confidence,
            "slots": self.slots,
            "entities": [e.to_dict() for e in self.entities],
            "raw_text": self.raw_text,
            "normalized_text": self.normalized_text,
        }


class SpacyNLU:
    """spaCy-based NLU for tokenization, POS, and NER."""

    def __init__(self, model_name: str = "en_core_web_sm"):
        self._nlp = None
        self._model_name = model_name
        self._load_model()

    def _load_model(self) -> None:
        """Load spaCy model."""
        try:
            import spacy
            try:
                self._nlp = spacy.load(self._model_name)
            except OSError:
                logger.warning(f"spaCy model '{self._model_name}' not found, using blank")
                self._nlp = spacy.blank("en")
            logger.info(f"Loaded spaCy model: {self._model_name}")
        except ImportError:
            logger.warning("spaCy not installed, NLU will use fallback")
            self._nlp = None

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        if self._nlp:
            doc = self._nlp(text)
            return [t.text for t in doc]
        return text.split()

    def pos_tags(self, text: str) -> List[Tuple[str, str]]:
        """Get POS tags for each token."""
        if self._nlp:
            doc = self._nlp(text)
            return [(t.text, t.pos_) for t in doc]
        return []

    def extract_entities(self, text: str) -> List[Entity]:
        """Extract named entities using spaCy NER."""
        if not self._nlp:
            return []
        
        doc = self._nlp(text)
        entities = []
        for ent in doc.ents:
            entities.append(Entity(
                text=ent.text,
                start=ent.start_char,
                end=ent.end_char,
                entity_type=ent.label_,
            ))
        return entities


class SnipsStyleIntentClassifier:
    """Rule-based intent classifier inspired by Snips NLU.
    
    Uses pattern matching and keyword scoring for offline intent classification.
    Works without ML models - deterministic and reproducible.
    """

    def __init__(self):
        self._intent_patterns = {
            "greeting": [
                r'\b(hello|hi|hey|good morning|good afternoon|good evening|greetings|howdy|yo|hiya)\b',
                r"\bwhat'?s up\b",
            ],
            "farewell": [
                r'\b(bye|goodbye|see you|later|farewell|good night|good day|take care)\b',
            ],
            "confirm": [
                r'\b(yes|yeah|yep|sure|ok|okay|correct|right|exactly|definitely|absolutely|affirmative)\b',
            ],
            "deny": [
                r'\b(no|nope|nah|not|never|wrong|incorrect|deny|decline|refuse)\b',
            ],
            "help": [
                r'\b(help|assist|support|guide|explain|tell me how|what is|how do|can you)\b',
            ],
            "question": [
                r'\?$',
                r'\b(what|who|where|when|why|how|which|whose)\b',
            ],
            "command": [
                r'\b(do|make|create|run|execute|start|stop|open|close|save|delete|show|get|find|search)\b',
            ],
        }

    def classify(self, text: str) -> Tuple[Intent, float]:
        """Classify text into an intent.
        
        Returns:
            Tuple of (Intent, confidence_score)
        """
        text_lower = text.lower()
        scores = {}

        intent_map = {
            "greeting": Intent.GREETING,
            "farewell": Intent.FAREWELL,
            "confirm": Intent.CONFIRM,
            "deny": Intent.DENY,
            "help": Intent.HELP,
            "question": Intent.QUESTION,
            "command": Intent.COMMAND,
        }

        for intent_key, patterns in self._intent_patterns.items():
            score = 0.0
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 1.0
            if score > 0:
                scores[intent_map[intent_key]] = score

        if not scores:
            return Intent.UNKNOWN, 0.5

        max_intent = max(scores, key=scores.get)
        max_score = scores[max_intent]
        confidence = min(max_score / 2.0, 1.0)

        return max_intent, confidence

    def extract_slots(self, text: str, intent: Intent) -> Dict[str, str]:
        """Extract slots based on intent and patterns."""
        slots = {}
        text_lower = text.lower()

        if intent == Intent.COMMAND:
            if match := re.search(r'(create|make|build)\s+(?:a\s+)?(\w+)', text_lower):
                slots["action"] = match.group(1)
                slots["object"] = match.group(2)
            if match := re.search(r'(?:named|called)\s+(\w+)', text_lower):
                slots["name"] = match.group(1)

        if intent == Intent.QUESTION:
            question_words = ["what", "who", "where", "when", "why", "how"]
            for qw in question_words:
                if qw in text_lower:
                    slots["question_word"] = qw
                    break

        if match := re.search(r'\b(\d+)\b', text):
            slots["number"] = match.group(1)

        return slots


class NLUPipeline:
    """Complete NLU pipeline combining normalization, spaCy, and intent classification."""

    def __init__(self, spacy_model: str = "en_core_web_sm"):
        self.normalizer = None
        self.spacy_nlu = None
        self.intent_classifier = SnipsStyleIntentClassifier()
        self._init_components(spacy_model)

    def _init_components(self, model_name: str) -> None:
        """Initialize NLU components."""
        try:
            from dialogue.input_normalizer import InputNormalizer
            self.normalizer = InputNormalizer()
        except ImportError:
            logger.warning("Input normalizer not available")

        try:
            self.spacy_nlu = SpacyNLU(model_name)
        except Exception as e:
            logger.warning(f"spaCy NLU not available: {e}")

    def process(self, text: str) -> NLUResult:
        """Process input text through full NLU pipeline.
        
        Args:
            text: Raw user input
        
        Returns:
            NLUResult with intent, slots, and entities
        """
        normalized = text
        if self.normalizer:
            norm_result = self.normalizer.normalize(text)
            normalized = norm_result.text

        intent, confidence = self.intent_classifier.classify(normalized)
        slots = self.intent_classifier.extract_slots(normalized, intent)

        entities = []
        if self.spacy_nlu:
            entities = self.spacy_nlu.extract_entities(normalized)

        return NLUResult(
            intent=intent,
            intent_confidence=confidence,
            slots=slots,
            entities=entities,
            raw_text=text,
            normalized_text=normalized,
        )


def create_nlu_pipeline(spacy_model: str = "en_core_web_sm") -> NLUPipeline:
    """Create and return an NLU pipeline."""
    return NLUPipeline(spacy_model)