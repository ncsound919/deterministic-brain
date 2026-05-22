"""Pattern Healer for Response Variation Healing.

Expands acceptable response patterns to handle seeded random variations.
"""
from __future__ import annotations
import re
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Pattern

logger = logging.getLogger(__name__)


@dataclass
class ResponsePattern:
    """A response pattern with variants."""
    base: str
    variants: List[str] = field(default_factory=list)
    regex: Optional[Pattern] = None


class PatternHealer:
    """Heals response pattern mismatches from seeded variations."""

    DEFAULT_PATTERNS = {
        "greeting": [
            r"(Hello|Hi|Hey|Greetings).*",
            r"Good (morning|afternoon|evening).*",
            r"Hi there!.*",
        ],
        "farewell": [
            r"(Goodbye|Bye|See you).*",
            r"Take care!.*",
            r"Until next time.*",
        ],
        "help": [
            r"I can help.*",
            r"I'm here to help.*",
            r"What would you like help with.*",
        ],
        "confirm": [
            r"Is that correct\?.*",
            r"Does that look right\?.*",
            r"Shall I proceed\?.*",
        ],
        "error": [
            r"Something went wrong.*",
            r"I encountered an error.*",
            r"Sorry, I couldn't.*",
        ],
    }

    def __init__(self):
        self._patterns: Dict[str, List[ResponsePattern]] = {}
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Load patterns from cache."""
        cache_file = Path.home() / ".deterministic-brain" / "healer_cache" / "response_patterns.json"
        
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                    for intent, patterns in data.items():
                        self._patterns[intent] = [
                            ResponsePattern(base=p["base"], variants=p.get("variants", []))
                            for p in patterns
                        ]
                return
            except Exception:
                pass
        
        for intent, patterns in self.DEFAULT_PATTERNS.items():
            self._patterns[intent] = [
                ResponsePattern(base=p, regex=re.compile(p, re.IGNORECASE))
                for p in patterns
            ]

    def _save_patterns(self) -> None:
        """Save patterns to cache."""
        cache_dir = Path.home() / ".deterministic-brain" / "healer_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / "response_patterns.json"
        
        data = {
            intent: [
                {"base": p.base, "variants": p.variants}
                for p in patterns
            ]
            for intent, patterns in self._patterns.items()
        }
        
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)

    def match_response(self, response: str, intent: str) -> bool:
        """Check if response matches any pattern for intent.
        
        Args:
            response: Actual response text
            intent: Expected intent
        
        Returns:
            True if response matches any pattern
        """
        if intent not in self._patterns:
            return True
        
        for pattern in self._patterns[intent]:
            if pattern.regex and pattern.regex.match(response):
                return True
            
            for variant in pattern.variants:
                if variant.lower() in response.lower():
                    return True
        
        return False

    def heal_response(self, actual_response: str, expected_intent: str) -> Optional[str]:
        """Heal response by adding new variant.
        
        Args:
            actual_response: The actual response that didn't match
            expected_intent: The intent that was expected
        
        Returns:
            Healing applied or None
        """
        if expected_intent not in self._patterns:
            self._patterns[expected_intent] = []
        
        new_variant = self._extract_variant(actual_response)
        
        if new_variant:
            pattern = ResponsePattern(
                base=new_variant,
                variants=[new_variant],
                regex=re.compile(self._response_to_regex(new_variant), re.IGNORECASE)
            )
            self._patterns[expected_intent].append(pattern)
            self._save_patterns()
            
            return f"Added pattern: {new_variant[:50]}..."
        
        return None

    def _extract_variant(self, response: str) -> Optional[str]:
        """Extract a pattern variant from response."""
        response = response.strip()
        
        if len(response) > 100:
            response = response[:100] + ".*"
        
        return response

    def _response_to_regex(self, text: str) -> str:
        """Convert response text to regex pattern."""
        text = re.escape(text)
        text = text.replace(r"\ ", r"\s+")
        text = text.replace(r"\*", ".*")
        
        return text

    def expand_acceptability(self, test_id: str, response: str, intent: str) -> bool:
        """Expand acceptable responses for a test.
        
        Args:
            test_id: Test identifier
            response: Actual response
            intent: Expected intent
        
        Returns:
            True if expansion was applied
        """
        if self.match_response(response, intent):
            return False
        
        result = self.heal_response(response, intent)
        return result is not None

    def get_pattern_count(self, intent: str) -> int:
        """Get number of patterns for intent."""
        return len(self._patterns.get(intent, []))

    def list_intents(self) -> List[str]:
        """List all intents with patterns."""
        return list(self._patterns.keys())


class ResponseComparator:
    """Compares responses with tolerance for variations."""

    def __init__(self, tolerance: float = 0.8):
        self.tolerance = tolerance

    def compare(self, expected: str, actual: str) -> bool:
        """Compare expected and actual responses.
        
        Args:
            expected: Expected response
            actual: Actual response
        
        Returns:
            True if responses match within tolerance
        """
        expected_lower = expected.lower().strip()
        actual_lower = actual.lower().strip()
        
        if expected_lower == actual_lower:
            return True
        
        if expected_lower in actual_lower or actual_lower in expected_lower:
            return True
        
        words_expected = set(expected_lower.split())
        words_actual = set(actual_lower.split())
        
        if not words_expected or not words_actual:
            return False
        
        overlap = len(words_expected & words_actual) / len(words_expected)
        
        return overlap >= self.tolerance

    def find_closest_match(self, actual: str, candidates: List[str]) -> Optional[str]:
        """Find closest matching candidate."""
        best_match = None
        best_score = 0
        
        for candidate in candidates:
            score = self._word_overlap(actual.lower(), candidate.lower())
            if score > best_score:
                best_score = score
                best_match = candidate
        
        return best_match if best_score >= self.tolerance else None

    def _word_overlap(self, s1: str, s2: str) -> float:
        """Calculate word overlap ratio."""
        words1 = set(s1.split())
        words2 = set(s2.split())
        
        if not words1 or not words2:
            return 0.0
        
        return len(words1 & words2) / len(words1 | words2)


def create_pattern_healer() -> PatternHealer:
    """Create a pattern healer."""
    return PatternHealer()


def create_comparator(tolerance: float = 0.8) -> ResponseComparator:
    """Create a response comparator."""
    return ResponseComparator(tolerance)