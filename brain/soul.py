"""Soul manager — reads .soul.yaml, exposes identity/agenda/context to the brain.
All autonomous systems (AutoDream, KAIROS, template builder) pull from this.
The soul is the heartbeat — it tells the brain WHO to serve and WHY.
"""
from __future__ import annotations
import os
import yaml
import time
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema: required keys and their expected types for .soul.yaml validation
# ---------------------------------------------------------------------------
_SOUL_SCHEMA: Dict[str, type] = {
    "identity": dict,
    "agenda": dict,
    "context": dict,
    "preferences": dict,
}


def _validate_soul_yaml(data: Dict) -> List[str]:
    """Return a list of validation error messages, empty if clean."""
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["soul.yaml root must be a YAML mapping"]
    for key, expected_type in _SOUL_SCHEMA.items():
        if key not in data:
            errors.append(f"Missing required section: '{key}'")
        elif not isinstance(data[key], expected_type):
            errors.append(
                f"Section '{key}' must be a {expected_type.__name__}, "
                f"got {type(data[key]).__name__}"
            )
    return errors


@dataclass
class Soul:
    path: str = ".soul.yaml"
    # identity
    name: str = ""
    role: str = "developer"
    timezone: str = "UTC"
    pronouns: str = ""
    # agenda
    mission: str = ""
    goals: List[str] = field(default_factory=list)
    anti_goals: List[str] = field(default_factory=list)
    autonomous_directives: List[str] = field(default_factory=list)
    # context
    expertise: List[str] = field(default_factory=list)
    learning: List[str] = field(default_factory=list)
    stack_languages: List[str] = field(default_factory=list)
    stack_frameworks: List[str] = field(default_factory=list)
    stack_tools: List[str] = field(default_factory=list)
    notes: str = ""
    # preferences
    code_style: str = ""
    naming: str = ""
    testing: str = ""
    deploy: str = ""
    verbosity: str = "concise"
    tone: str = "direct"
    # knowledge
    knowledge_sources: List[str] = field(default_factory=list)
    project_templates: List[str] = field(default_factory=list)
    # meta
    meta_version: str = "1.0"
    meta_created: str = ""
    meta_updated: str = ""
    meta_sessions: int = 0

    def load(self) -> bool:
        # FIX: warn explicitly when .soul.yaml is missing instead of silent False
        if not os.path.exists(self.path):
            logger.warning(
                "[soul] .soul.yaml not found at '%s'. "
                "Copy .soul.yaml.example to .soul.yaml and fill in your details. "
                "Running with empty soul defaults.",
                os.path.abspath(self.path),
            )
            return False
        try:
            with open(self.path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error("[soul] Failed to parse .soul.yaml: %s", e)
            return False
        except Exception as e:
            logger.warning("[soul] Soul load failed: %s", e)
            return False

        # FIX: schema validation — log all issues before aborting
        errors = _validate_soul_yaml(data)
        if errors:
            for err in errors:
                logger.warning("[soul] Validation error: %s", err)
            logger.warning(
                "[soul] .soul.yaml has %d validation error(s). "
                "Check .soul.yaml.example for the expected structure.",
                len(errors),
            )
            # Non-fatal: continue loading what we can

        idn = data.get("identity", {})
        self.name = idn.get("name", "")
        self.role = idn.get("role", "developer")
        self.timezone = idn.get("timezone", "UTC")
        self.pronouns = idn.get("pronouns", "")

        agd = data.get("agenda", {})
        self.mission = agd.get("mission", "")
        self.goals = agd.get("goals", [])
        self.anti_goals = agd.get("anti_goals", [])
        self.autonomous_directives = agd.get("autonomous_directives", [])

        ctx = data.get("context", {})
        self.expertise = ctx.get("expertise", [])
        self.learning = ctx.get("learning", [])
        self.notes = ctx.get("notes", "")
        stack = ctx.get("stack", {})
        self.stack_languages = stack.get("languages", [])
        self.stack_frameworks = stack.get("frameworks", [])
        self.stack_tools = stack.get("tools", [])

        pref = data.get("preferences", {})
        self.code_style = pref.get("code_style", "")
        self.naming = pref.get("naming", "")
        self.testing = pref.get("testing", "")
        self.deploy = pref.get("deploy", "")
        comm = pref.get("communication", {})
        self.verbosity = comm.get("verbosity", "concise")
        self.tone = comm.get("tone", "direct")

        self.knowledge_sources = data.get("knowledge_sources", [])
        self.project_templates = data.get("project_templates", [])

        meta = data.get("meta", {})
        self.meta_version = meta.get("version", "1.0")
        self.meta_created = meta.get("created", "")
        self.meta_updated = meta.get("updated", "")
        self.meta_sessions = meta.get("sessions", 0)

        if self.name:
            logger.info("[soul] Loaded soul for '%s' (%s)", self.name, self.role)
        return True

    def save(self) -> bool:
        data = {
            "identity": {
                "name": self.name,
                "role": self.role,
                "timezone": self.timezone,
                "pronouns": self.pronouns,
            },
            "agenda": {
                "mission": self.mission,
                "goals": self.goals,
                "anti_goals": self.anti_goals,
                "autonomous_directives": self.autonomous_directives,
            },
            "context": {
                "expertise": self.expertise,
                "learning": self.learning,
                "stack": {
                    "languages": self.stack_languages,
                    "frameworks": self.stack_frameworks,
                    "tools": self.stack_tools,
                },
                "notes": self.notes,
            },
            "preferences": {
                "code_style": self.code_style,
                "naming": self.naming,
                "testing": self.testing,
                "deploy": self.deploy,
                "communication": {
                    "verbosity": self.verbosity,
                    "tone": self.tone,
                },
            },
            "knowledge_sources": self.knowledge_sources,
            "project_templates": self.project_templates,
            "meta": {
                "version": self.meta_version,
                "created": self.meta_created or time.strftime("%Y-%m-%d %H:%M"),
                "updated": time.strftime("%Y-%m-%d %H:%M"),
                "sessions": self.meta_sessions + 1,
            },
        }
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            logger.error("[soul] Soul save failed: %s", e)
            return False

    def pulse(self) -> Dict:
        """Called on every session start. Increments session counter, saves."""
        self.meta_sessions += 1
        self.meta_updated = time.strftime("%Y-%m-%d %H:%M")
        self.save()
        return self.summary()

    def summary(self) -> Dict:
        return {
            "name": self.name or "(no soul loaded)",
            "role": self.role,
            "mission": self.mission or "(none)",
            "goals": len(self.goals),
            "directives": len(self.autonomous_directives),
            "sources": len(self.knowledge_sources),
            "templates": len(self.project_templates),
            "sessions": self.meta_sessions,
            "loaded": self.name != "",
        }

    def to_context(self) -> str:
        """Generate a context string for injection into skill exec_inputs."""
        parts = []
        if self.name:
            parts.append(f"Building for: {self.name} ({self.role})")
        if self.mission:
            parts.append(f"Mission: {self.mission}")
        if self.goals:
            parts.append("Goals: " + "; ".join(self.goals))
        if self.stack_languages:
            parts.append("Languages: " + ", ".join(self.stack_languages))
        if self.stack_frameworks:
            parts.append("Frameworks: " + ", ".join(self.stack_frameworks))
        if self.code_style:
            parts.append(f"Style: {self.code_style}")
        if self.testing:
            parts.append(f"Testing: {self.testing}")
        if self.deploy:
            parts.append(f"Deploy: {self.deploy}")
        if self.autonomous_directives:
            # FIX: autonomous_directives were stored but never surfaced — expose them
            parts.append("Directives: " + "; ".join(self.autonomous_directives))
        if self.notes:
            parts.append(f"Notes: {self.notes}")
        return "\n".join(parts)

    def merge_into_exec_inputs(self, exec_inputs: Dict) -> None:
        ctx = self.to_context()
        if ctx:
            existing = exec_inputs.get("soul_context", "")
            exec_inputs["soul_context"] = (existing + "\n" + ctx).strip()


_SOUL: Optional[Soul] = None


def get_soul() -> Soul:
    global _SOUL
    if _SOUL is None:
        _SOUL = Soul()
        _SOUL.load()
    return _SOUL


def reset_soul() -> None:
    global _SOUL
    _SOUL = None
