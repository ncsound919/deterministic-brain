"""Skill executor — bridges brain decisions to skill execution."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional

from orchestration.skill_registry import (
    get_skill_registry,
    SkillRegistry,
    SkillMetadata,
)

logger = logging.getLogger(__name__)


class SkillExecutor:
    """Executes skills through the registry, handling backend routing."""

    def __init__(self, registry: Optional[SkillRegistry] = None):
        self.registry = registry or get_skill_registry()

    def execute(
        self,
        skill_id: str,
        task: Dict,
        context: Dict,
    ) -> Dict[str, Any]:
        """Execute a skill, routing to the appropriate backend.

        Args:
            skill_id: ID of the skill to execute
            task: Task dict with 'raw', 'task', and extracted params
            context: Execution context including session state

        Returns:
            Execution result with success, output, artifacts, logs
        """
        return self.registry.execute(skill_id, task, context)

    def can_execute(self, skill_id: str) -> bool:
        """Check if a skill can be executed."""
        metadata = self.registry.get(skill_id)
        if not metadata:
            return False

        backend = self.registry.get_backend(skill_id)
        return backend is not None

    def get_skill_info(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get skill metadata as dict."""
        metadata = self.registry.get(skill_id)
        return metadata.to_dict() if metadata else None

    def list_skills(self, backend: Optional[str] = None) -> list[Dict[str, Any]]:
        """List all available skills."""
        skills = self.registry.list_all(backend)
        return [s.to_dict() for s in skills]

    def translate_and_register(
        self,
        external_skill: Dict[str, Any],
        target_backend: str,
    ) -> bool:
        """Import an external skill into our registry.

        Args:
            external_skill: Skill definition from external system
            target_backend: Which backend (claude/openclaw/hermes)

        Returns:
            True if successfully registered
        """
        try:
            metadata = self.registry.translate_external_skill(
                external_skill, target_backend
            )
            self.registry.register(metadata)
            logger.info(f"Registered external skill: {metadata.skill_id} -> {target_backend}")
            return True
        except Exception as e:
            logger.error(f"Failed to register external skill: {e}")
            return False


_EXECUTOR: Optional[SkillExecutor] = None


def get_skill_executor() -> SkillExecutor:
    """Get the global skill executor instance."""
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = SkillExecutor()
    return _EXECUTOR