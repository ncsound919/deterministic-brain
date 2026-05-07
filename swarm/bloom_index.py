"""swarm/bloom_index.py — Deterministic Bloom filter for skill token membership."""
from __future__ import annotations
import hashlib
import re
from typing import Iterable, List, Set


def _tokenize(text: str) -> List[str]:
    """Split on hyphens, underscores, spaces; lowercase; drop empty strings."""
    return [t for t in re.split(r'[-_\s]+', text.lower()) if t]


class BloomFilter:
    """
    Pure-Python Bloom filter using three independent hash functions.
    False-positive rate ~1% at default capacity=2048.
    Guarantees NO false negatives: if an item was added, might_contain always True.
    """

    def __init__(self, capacity: int = 2048):
        self._bits = bytearray(capacity)
        self._size = capacity
        self._add_count = 0

    def _positions(self, item: str):
        b = item.lower().encode()
        h1 = int(hashlib.md5(b).hexdigest(),    16) % self._size
        h2 = int(hashlib.sha256(b).hexdigest(), 16) % self._size
        h3 = int(hashlib.sha1(b).hexdigest(),   16) % self._size
        return h1, h2, h3

    def add(self, item: str) -> None:
        """Add a single token (already atomized — no further splitting)."""
        for pos in self._positions(item):
            self._bits[pos] = 1
        self._add_count += 1

    def might_contain(self, item: str) -> bool:
        return all(self._bits[pos] for pos in self._positions(item))

    @property
    def count(self) -> int:
        return self._add_count


class SkillBloomIndex:
    """
    Wraps BloomFilter with skill-aware indexing.

    For every skill name added (e.g. "create-react-component"), it adds:
      1. The full name as-is              -> "create-react-component"
      2. Every individual token           -> "create", "react", "component"

    This ensures might_have_skill('react') returns True whenever any loaded
    skill contains "react" as a component, preventing false negatives.
    """

    def __init__(self, capacity: int = 2048):
        self._filter    = BloomFilter(capacity)
        self._skill_set: Set[str] = set()   # exact membership for audit

    def add_skill(self, skill_name: str) -> None:
        """Index a skill by its full name and every hyphen/underscore token."""
        self._skill_set.add(skill_name)
        # Full name
        self._filter.add(skill_name)
        # Individual tokens — this is what makes might_have_skill("react") work
        for token in _tokenize(skill_name):
            self._filter.add(token)

    def add_skills(self, skill_names: Iterable[str]) -> None:
        for name in skill_names:
            self.add_skill(name)

    def might_have_skill(self, query: str) -> bool:
        """
        Returns True if query *might* match any indexed skill token.
        Checks the query itself AND its tokens (handles compound queries).
        No false negatives — if it was indexed, this always returns True.
        """
        # Check the query as a whole token
        if self._filter.might_contain(query):
            return True
        # Also check each sub-token of the query (handles "react-component" queries)
        for token in _tokenize(query):
            if self._filter.might_contain(token):
                return True
        return False

    def exact_skill_known(self, skill_name: str) -> bool:
        """O(1) exact check — use this when you need certainty, not the Bloom filter."""
        return skill_name in self._skill_set

    @property
    def indexed_count(self) -> int:
        return len(self._skill_set)


# ---------------------------------------------------------------------------
# Module-level singleton — lazily populated from the task parser's PATTERNS
# ---------------------------------------------------------------------------

_INDEX: SkillBloomIndex | None = None

_KNOWN_SKILLS = [
    "create-react-component",
    "scaffold-rest-api",
    "add-auth",
    "generate-dockerfile",
    "audit-repo",
    "live-docs-to-skill",
]


def get_skill_index() -> SkillBloomIndex:
    """Return the module-level SkillBloomIndex, building it on first call."""
    global _INDEX
    if _INDEX is None:
        _INDEX = SkillBloomIndex()
        _INDEX.add_skills(_KNOWN_SKILLS)
    return _INDEX
