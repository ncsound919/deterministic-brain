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


# Resolve skills from the brain's OWN skill packs by default. The old default
# pointed at a user-profile folder (C:\Users\User\Documents\skills) that is
# outside the repo: every chain step resolved there first, found nothing, and
# silently fell through — tasks "completed" without doing work.
_BRAIN_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = Path(os.getenv('SKILLS_BASE_PATH') or (_BRAIN_ROOT / 'skill_packs'))
# Optional extra search roots (env-separated), e.g. the legacy Documents dir.
_EXTRA_ROOTS = [Path(p) for p in os.getenv('SKILLS_EXTRA_PATHS', '').split(os.pathsep) if p.strip()]

# Fallback roots the resolver searches when the configured SKILLS_ROOT has no
# matching skill: the brain's own skill_packs (native skill.md) and lanes.
def _fallback_roots() -> list[Path]:
    base = Path(__file__).resolve().parent.parent
    return [base / "skill_packs", base / "lanes"]

logger = logging.getLogger(__name__)


class SkillResolver:
    def __init__(self):
        self._cache: Dict[str, str] = {}

    def resolve(self, skill_name: str) -> Optional[str]:
        """Resolve a skill name to a skill file path via keyword matching."""
        if skill_name in self._cache:
            return self._cache[skill_name]

        normalized = skill_name.lower().replace("-", "_").replace(" ", "_")

        roots = [SKILLS_ROOT, *_fallback_roots()]
        for root in roots:
            if not root.exists():
                continue
            for skill_file in root.rglob("*.md"):
                # Match on the parent directory name primarily (skill.md files
                # all share the generic "skill" stem, which would otherwise
                # falsely match any skill whose name contains "skill").
                parent = skill_file.parent.name
                if self._matches(parent, normalized, skill_name):
                    path = str(skill_file.resolve())
                    self._cache[skill_name] = path
                    logger.info("Resolved skill '%s' -> %s", skill_name, path)
                    return path
                # Fall back to a file stem match only when it is meaningful
                # (not the generic skill.md / SKILL.md stem).
                stem = skill_file.stem.lower()
                if stem not in ("skill", "skills") and self._matches(stem, normalized, skill_name):
                    path = str(skill_file.resolve())
                    self._cache[skill_name] = path
                    logger.info("Resolved skill '%s' -> %s", skill_name, path)
                    return path

        return None

    # Generic tokens carry zero discriminating signal — a file named
    # "skill.md" must never match every query via substring logic.
    _GENERIC_TOKENS = {"skill", "skills", "readme", "index", "main", "template"}

    def _matches(self, file_stem: str, normalized: str, original: str) -> bool:
        """Check if file stem matches the skill name (token-aware)."""
        def tokens(s: str) -> set:
            parts = s.lower().replace("-", "_").replace(" ", "_").split("_")
            return {p for p in parts if p and p not in self._GENERIC_TOKENS}

        stem = file_stem.lower()
        orig = original.lower()
        if stem == normalized or stem == orig:
            return True

        stem_toks = tokens(file_stem)
        query_toks = tokens(normalized) | tokens(original)
        if not stem_toks or not query_toks:
            return False
        # Match when any meaningful token coincides exactly.
        return bool(stem_toks & query_toks)

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
            # skill.md/SKILL.md files all have stem "skill" — use the parent
            # directory name as the actual skill id.
            skill_id = Path(path).parent.name if Path(path).stem in ("skill", "skills") else Path(path).stem
            task = {"raw": skill_name, "task": skill_name, **(inputs or {})}
            context = {}
            result = registry.execute(skill_id, task, context)

            # Record reward for bandit feedback loop
            status = "ok" if result.get("success") else "partial"
            try:
                from evolution.reward_tracker import get_reward_tracker
                rt = get_reward_tracker()
                # Arm format: skill:{skill_name}
                arm_id = f"skill:{skill_id}"
                reward = 1.0 if status == "ok" else 0.0
                rt.record(arm_id, reward, context={"status": status, "inputs": inputs or {}})
            except Exception as rt_err:
                logger.warning("Reward tracking failed: %s", rt_err)

            return {"status": status, "output": result}
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