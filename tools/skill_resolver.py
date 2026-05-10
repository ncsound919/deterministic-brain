"""Skill resolver — direct skill registry lookup with Gemma fallback.

Replaces DCA-based skill execution for deterministic chains.
Routes skill names directly to .md skill files using keyword matching.
Falls back to local Gemma for ambiguous skill names.
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from config import cfg

SKILLS_ROOT = Path(os.getenv('SKILLS_BASE_PATH', r'C:\Users\User\Documents\skills'))

logger = logging.getLogger(__name__)


class SkillResolver:
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def resolve(self, skill_name: str) -> Optional[str]:
        """Resolve a skill name to a skill file path via keyword matching."""
        if skill_name in self._cache:
            return self._cache[skill_name]

        normalized = skill_name.lower().replace("-", "_").replace(" ", "_")

        if SKILLS_ROOT.exists():
            for skill_file in SKILLS_ROOT.rglob("*.md"):
                if self._matches(skill_file.stem, normalized, skill_name):
                    path = str(skill_file.resolve())
                    self._cache[skill_name] = path
                    logger.info("Resolved skill '%s' -> %s", skill_name, path)
                    return path

        return None

    def _matches(self, file_stem: str, normalized: str, original: str) -> bool:
        """Check if file stem matches the skill name."""
        stem = file_stem.lower()
        orig = original.lower()
        return (stem == normalized or
                stem == orig or
                normalized in stem or
                stem in normalized or
                orig in stem)

    def resolve_with_gemma(self, skill_name: str) -> Optional[str]:
        """Try direct resolution first, then Gemma fallback."""
        path = self.resolve(skill_name)
        if path:
            return path

        from tools.local_gemma import get_gemma
        gemma = get_gemma()

        if not gemma.is_available():
            logger.warning("Gemma unavailable, cannot resolve '%s'", skill_name)
            return None

        available = list(self._cache.keys())

        prompt = (
            f"Map this skill name to the best matching skill from this list: {available}. "
            f"Return ONLY the skill name from the list, nothing else. "
            f"Skill to map: '{skill_name}'"
        )

        guessed = gemma.complete(prompt, n_predict=32, temperature=0.1)
        if guessed:
            return self.resolve(guessed.strip())
        return None

    def execute(self, skill_name: str, inputs: Dict) -> Dict:
        """Resolve skill and execute it, returning status."""
        path = self.resolve_with_gemma(skill_name)
        if not path:
            return {"status": "error", "error": f"Skill not found: {skill_name}"}

        try:
            from orchestration.skill_registry import get_skill_registry
            registry = get_skill_registry()
            skill_id = Path(path).stem
            task = {"raw": skill_name, "task": skill_name, **(inputs or {})}
            context = {}
            result = registry.execute(skill_id, task, context)
            return {"status": "ok" if result.get("success") else "partial", "output": result}
        except FileNotFoundError:
            return {"status": "error", "error": f"Skill file not found: {path}"}
        except Exception as e:
            logger.error("Skill execution failed: %s - %s", skill_name, e)
            return {"status": "error", "error": str(e)}


_resolver: Optional[SkillResolver] = None


def get_resolver() -> SkillResolver:
    global _resolver
    if _resolver is None:
        _resolver = SkillResolver()
    return _resolver