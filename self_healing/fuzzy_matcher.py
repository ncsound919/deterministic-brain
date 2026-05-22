"""Fuzzy Matching for Intent and Text Healing.

Uses Levenshtein distance for typo correction and intent matching.
"""
from __future__ import annotations
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    logger.warning("rapidfuzz not installed, using fallback matching")


class FuzzyMatcher:
    """Fuzzy string matching for input normalization."""

    def __init__(self, threshold: float = 80.0):
        self.threshold = threshold
        self._corrections: Dict[str, str] = {}
        self._load_corrections()

    def _load_corrections(self) -> None:
        """Load common corrections from cache."""
        try:
            from pathlib import Path
            cache = Path.home() / ".deterministic-brain" / "healer_cache" / "corrections.json"
            if cache.exists():
                import json
                with open(cache) as f:
                    self._corrections = json.load(f)
        except Exception:
            pass

    def _save_corrections(self) -> None:
        """Save corrections to cache."""
        try:
            from pathlib import Path
            cache_dir = Path.home() / ".deterministic-brain" / "healer_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache = cache_dir / "corrections.json"
            import json
            with open(cache, "w") as f:
                json.dump(self._corrections, f, indent=2)
        except Exception:
            pass

    def match(self, text: str, candidates: List[str]) -> Optional[Tuple[str, float]]:
        """Find best match above threshold.
        
        Args:
            text: Input text
            candidates: List of candidate strings
        
        Returns:
            (matched_string, score) or None
        """
        if not candidates:
            return None
        
        if RAPIDFUZZ_AVAILABLE:
            result = process.extractOne(text, candidates, scorer=fuzz.ratio)
            if result and result[1] >= self.threshold:
                return (result[0], result[1])
        else:
            best_score = 0
            best_match = None
            for candidate in candidates:
                score = self._levenshtein_ratio(text.lower(), candidate.lower())
                if score > best_score and score >= self.threshold:
                    best_score = score
                    best_match = candidate
            if best_match:
                return (best_match, best_score)
        
        return None

    def correct_spelling(self, text: str, dictionary: Dict[str, str]) -> str:
        """Correct spelling using dictionary.
        
        Args:
            text: Input text
            dictionary: Word -> correction mapping
        
        Returns:
            Corrected text
        """
        words = text.split()
        corrected = []
        
        for word in words:
            lower = word.lower()
            if lower in self._corrections:
                corrected.append(self._corrections[lower])
            elif lower in dictionary:
                corrected.append(dictionary[lower])
            else:
                corrected.append(word)
        
        return " ".join(corrected)

    def add_correction(self, wrong: str, correct: str) -> None:
        """Add a spelling correction."""
        self._corrections[wrong.lower()] = correct
        self._save_corrections()

    def _levenshtein_ratio(self, s1: str, s2: str) -> float:
        """Calculate Levenshtein similarity ratio."""
        if not s1 or not s2:
            return 0.0
        
        len1, len2 = len(s1), len(s2)
        if len1 > len2:
            s1, s2 = s2, s1
            len1, len2 = len2, len1
        
        current_row = range(len1 + 1)
        for i in range(1, len2 + 1):
            previous_row, current_row = current_row, [i] + [0] * len1
            for j in range(1, len1 + 1):
                add = previous_row[j] + 1
                delete = current_row[j-1] + 1
                change = previous_row[j-1]
                if s1[j-1] != s2[i-1]:
                    change += 1
                current_row[j] = min(add, delete, change)
        
        distance = current_row[len1]
        return (1 - distance / max(len1, len2)) * 100


class IntentFuzzyMatcher(FuzzyMatcher):
    """Specialized fuzzy matcher for intent classification."""

    def __init__(self, threshold: float = 70.0):
        super().__init__(threshold)
        self._intent_patterns: Dict[str, List[str]] = {
            "greeting": ["hello", "hi", "hey", "greetings", "howdy"],
            "farewell": ["bye", "goodbye", "see you", "later", "farewell"],
            "help": ["help", "assist", "support", "guide"],
            "weather": ["weather", "temperature", "forecast", "rain", "sunny"],
            "question": ["what", "who", "where", "when", "why", "how"],
            "command": ["create", "make", "build", "generate", "add"],
        }

    def match_intent(self, user_input: str) -> Optional[str]:
        """Match user input to intent.
        
        Returns:
            Intent name or None
        """
        result = self.match(user_input, self._expand_intents())
        if result:
            intent = self._find_intent_for_match(result[0])
            return intent
        return None

    def _expand_intents(self) -> List[str]:
        """Expand intent patterns to flat list."""
        expanded = []
        for intent, patterns in self._intent_patterns.items():
            expanded.extend(patterns)
        return expanded

    def _find_intent_for_match(self, matched: str) -> Optional[str]:
        """Find which intent a matched word belongs to."""
        matched_lower = matched.lower()
        for intent, patterns in self._intent_patterns.items():
            if matched_lower in [p.lower() for p in patterns]:
                return intent
        return None

    def add_intent_pattern(self, intent: str, pattern: str) -> None:
        """Add a pattern to an intent."""
        if intent not in self._intent_patterns:
            self._intent_patterns[intent] = []
        if pattern not in self._intent_patterns[intent]:
            self._intent_patterns[intent].append(pattern)


def create_fuzzy_matcher(threshold: float = 80.0) -> FuzzyMatcher:
    """Create a fuzzy matcher."""
    return FuzzyMatcher(threshold)


def create_intent_matcher(threshold: float = 70.0) -> IntentFuzzyMatcher:
    """Create an intent fuzzy matcher."""
    return IntentFuzzyMatcher(threshold)