"""Input Normalization Layer — text cleanup, spelling tolerance, canonicalization."""
from __future__ import annotations
import re
import unicodedata
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class NormalizedInput:
    """Normalized input with metadata."""
    text: str
    original: str
    language: Optional[str] = None
    confidence: float = 1.0
    corrections: list = None

    def __post_init__(self):
        if self.corrections is None:
            self.corrections = []


class InputNormalizer:
    """Normalizes raw user input for downstream NLU processing."""

    def __init__(self, language: str = "en"):
        self.language = language
        self._common_corrections = self._load_common_corrections()

    def _load_common_corrections(self) -> Dict[str, str]:
        """Load common misspellings and abbreviations."""
        return {
            "u": "you",
            "ur": "your",
            "r": "are",
            "bc": "because",
            "plz": "please",
            "pls": "please",
            "thx": "thanks",
            "thnx": "thanks",
            "idk": "I don't know",
            "btw": "by the way",
            "fyi": "for your information",
            "imo": "in my opinion",
            "omg": "oh my god",
            "wtf": "what the",
            "lol": "laughing out loud",
            "gonna": "going to",
            "wanna": "want to",
            "gotta": "got to",
            "kinda": "kind of",
            "sorta": "sort of",
            "dunno": "don't know",
            "gimme": "give me",
            "lemme": "let me",
            "shoulda": "should have",
            "coulda": "could have",
            "woulda": "would have",
        }

    def normalize(self, text: str) -> NormalizedInput:
        """Normalize input text.
        
        Steps:
        1. Unicode normalization (NFC)
        2. Lowercase for non-proper nouns
        3. Expand abbreviations
        4. Remove excessive punctuation
        5. Normalize whitespace
        6. Basic spelling corrections
        """
        original = text
        corrections = []
        
        text = unicodedata.normalize('NFC', text)
        
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        words = text.split()
        normalized_words = []
        for word in words:
            lower = word.lower()
            if lower in self._common_corrections:
                expanded = self._common_corrections[lower]
                corrections.append(f"'{word}' -> '{expanded}'")
                normalized_words.append(expanded)
            else:
                normalized_words.append(word)
        
        text = ' '.join(normalized_words)
        
        text = re.sub(r'[!?]{2,}', lambda m: m.group(1)[0], text)
        
        text = re.sub(r'([a-z])\1{2,}', r'\1\1', text)
        
        text = text.replace("'", "'").replace("'", "'")
        text = text.replace(""", '"').replace(""", '"')
        text = text.replace("…", "...")
        
        return NormalizedInput(
            text=text,
            original=original,
            language=self.language,
            corrections=corrections
        )

    def add_correction(self, wrong: str, correct: str) -> None:
        """Add a custom abbreviation or correction."""
        self._common_corrections[wrong.lower()] = correct


def normalize_input(text: str) -> NormalizedInput:
    """Convenience function for input normalization."""
    normalizer = InputNormalizer()
    return normalizer.normalize(text)