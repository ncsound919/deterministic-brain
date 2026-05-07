"""Response Realization — template selection with weighted variation and grammar-based realizer."""
from __future__ import annotations
import random
import re
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ResponseTemplate:
    """A response template with placeholders and weight."""
    template: str
    weight: float = 1.0
    variations: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.variations and not self.weight:
            self.weight = 1.0 / len(self.variations)


@dataclass
class RealizedResponse:
    """A fully realized response."""
    text: str
    template_used: str
    slots_filled: Dict[str, str]
    variation_used: Optional[str] = None


class TemplateRealizer:
    """Select and realize response templates with weighted variation."""

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self._rng = random.Random(seed)
        self._templates: Dict[str, List[ResponseTemplate]] = {}

    def register_template(self, intent: str, template: ResponseTemplate) -> None:
        """Register a response template for an intent."""
        if intent not in self._templates:
            self._templates[intent] = []
        self._templates[intent].append(template)

    def register_batch(self, intent: str, templates: List[ResponseTemplate]) -> None:
        """Register multiple templates for an intent."""
        self._templates[intent] = templates

    def realize(self, intent: str, slots: Dict[str, str], context: Dict[str, Any] = None) -> RealizedResponse:
        """Realize a response for the given intent and slots."""
        if intent not in self._templates:
            return RealizedResponse(
                text=f"I understand you're asking about {intent}.",
                template_used="fallback",
                slots_filled=slots,
            )

        templates = self._templates[intent]
        
        weights = [t.weight for t in templates]
        total = sum(weights)
        probs = [w / total for w in weights]
        
        selected_idx = self._weighted_choice(probs)
        selected_template = templates[selected_idx]

        text = self._fill_template(selected_template.template, slots, context or {})

        return RealizedResponse(
            text=text,
            template_used=selected_template.template,
            slots_filled=slots,
            variation_used=None,
        )

    def _weighted_choice(self, probs: List[float]) -> int:
        """Select index based on probabilities using seeded random."""
        r = self._rng.random()
        cumulative = 0.0
        for i, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                return i
        return len(probs) - 1

    def _fill_template(self, template: str, slots: Dict[str, str], context: Dict[str, Any]) -> str:
        """Fill template placeholders with slot values."""
        result = template
        
        for key, value in slots.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))
        
        for key, value in context.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))
        
        result = re.sub(r'\{[^}]+\}', '', result)
        
        return result.strip()


class GrammarRealizer:
    """Grammar-based response realizer for sentence-level diversity."""

    def __init__(self):
        self._grammar_rules: Dict[str, List[str]] = {
            "greeting_prefix": ["Hello", "Hi", "Hey", "Greetings"],
            "greeting_suffix": ["!", ".", ""],
            "question_prefix": ["Could you", "Would you mind", "Please"],
            "command_verb": ["Create", "Make", "Build", "Generate"],
            "confirm_phrase": ["Is that correct?", "Does that look right?", "Shall I proceed?"],
        }

    def realize_with_grammar(self, template: str, slots: Dict[str, str]) -> str:
        """Realize a template using grammar rules for variation."""
        result = template
        
        for category, options in self._grammar_rules.items():
            placeholder = f"[{category}]"
            if placeholder in result:
                choice = random.choice(options)
                result = result.replace(placeholder, choice)
        
        result = self._fill_template(result, slots)
        
        return result

    def _fill_template(self, template: str, slots: Dict[str, str]) -> str:
        """Fill slot placeholders."""
        for key, value in slots.items():
            placeholder = f"{{{key}}}"
            template = template.replace(placeholder, str(value))
        return template


class ResponsePool:
    """Weighted response pool with rejection sampling."""

    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self._rng = random.Random(seed)
        self._responses: List[ResponseTemplate] = []
        self._min_confidence: float = 0.0

    def add(self, template: str, weight: float = 1.0, conditions: Optional[Dict[str, Any]] = None) -> None:
        """Add a response to the pool."""
        self._responses.append(ResponseTemplate(template=template, weight=weight))

    def sample(self, context: Dict[str, Any], max_attempts: int = 10) -> Optional[str]:
        """Sample a response using rejection sampling."""
        for _ in range(max_attempts):
            weights = [r.weight for r in self._responses]
            total = sum(weights)
            probs = [w / total for w in weights]
            
            idx = self._weighted_choice(probs)
            candidate = self._responses[idx]
            
            if self._check_conditions(candidate, context):
                return candidate.template
        
        return self._responses[0].template if self._responses else None

    def _weighted_choice(self, probs: List[float]) -> int:
        r = self._rng.random()
        cumulative = 0.0
        for i, p in enumerate(probs):
            cumulative += p
            if r <= cumulative:
                return i
        return len(probs) - 1

    def _check_conditions(self, template: ResponseTemplate, context: Dict[str, Any]) -> bool:
        """Check if template conditions are satisfied."""
        return True


def create_default_realizer(seed: Optional[int] = None) -> TemplateRealizer:
    """Create a default response realizer with standard templates."""
    realizer = TemplateRealizer(seed=seed)

    realizer.register_batch("greeting", [
        ResponseTemplate(template="Hello! How can I help you today?", weight=0.4),
        ResponseTemplate(template="Hi there! What can I do for you?", weight=0.3),
        ResponseTemplate(template="Greetings! How may I assist you?", weight=0.3),
    ])

    realizer.register_batch("farewell", [
        ResponseTemplate(template="Goodbye! Have a great day.", weight=0.5),
        ResponseTemplate(template="See you later! Take care.", weight=0.3),
        ResponseTemplate(template="Farewell! Until next time.", weight=0.2),
    ])

    realizer.register_batch("help", [
        ResponseTemplate(template="I can help you with coding tasks, data analysis, and general questions.", weight=0.4),
        ResponseTemplate(template="I'm here to help! I can assist with programming, debugging, and more.", weight=0.3),
        ResponseTemplate(template="What would you like help with? I support various tasks.", weight=0.3),
    ])

    realizer.register_batch("confirm", [
        ResponseTemplate(template="Is that correct?", weight=0.5),
        ResponseTemplate(template="Does that look right to you?", weight=0.3),
        ResponseTemplate(template="Shall I proceed with this?", weight=0.2),
    ])

    realizer.register_batch("command", [
        ResponseTemplate(template="I'll {action} the {object}.", weight=0.5),
        ResponseTemplate(template="Creating {object} as requested.", weight=0.3),
        ResponseTemplate(template="Executing: {action} {object}", weight=0.2),
    ])

    return realizer


def realize_response(intent: str, slots: Dict[str, str], seed: Optional[int] = None) -> RealizedResponse:
    """Convenience function for response realization."""
    realizer = create_default_realizer(seed=seed)
    return realizer.realize(intent, slots)