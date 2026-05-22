"""Skill registry — unified discovery and management across all backends."""
from __future__ import annotations
import os
import yaml
import logging
import threading
import time
from typing import Dict, List, Optional, Any

from orchestration.backends import (
    get_backend,
    SkillBackend,
)

logger = logging.getLogger(__name__)

_HOT_RELOAD_DEBOUNCE = 1.0  # seconds to debounce file change events


class SkillMetadata:
    """Metadata for a skill, parsed from skill.md or SKILL.md front-matter."""

    def __init__(
        self,
        skill_id: str,
        skill_name: str,
        version: str = "1.0",
        backend: str = "local",
        backend_skill_id: str = "",
        description: str = "",
        inputs: Dict[str, str] = None,
        tools: List[str] = None,
        audit: List[str] = None,
        monte_carlo: bool = False,
        source_format: str = "native",
        requires_env: List[str] = None,
        requires_bins: List[str] = None,
        skill_path: str = "",
        choices: Dict[str, List[str]] = None,
    ):
        self.skill_id = skill_id
        self.skill_name = skill_name
        self.version = version
        self.backend = backend
        self.backend_skill_id = backend_skill_id or skill_id
        self.description = description
        self.inputs = inputs or {}
        self.tools = tools or []
        self.audit = audit or []
        self.monte_carlo = monte_carlo
        self.source_format = source_format
        self.requires_env = requires_env or []
        self.requires_bins = requires_bins or []
        self.skill_path = skill_path
        self.choices = choices or {}

    @classmethod
    def from_file(cls, skill_path: str, skill_id: str) -> Optional["SkillMetadata"]:
        """Parse skill.md or SKILL.md and extract metadata."""
        if not os.path.exists(skill_path):
            return None

        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()

            filename = os.path.basename(skill_path)
            is_external = filename == "SKILL.md"
            if is_external:
                return cls._parse_external(skill_id, content, skill_path)
            else:
                return cls._parse_native(skill_id, content, skill_path)
        except Exception as e:
            logger.warning(f"Failed to parse {skill_path}: {e}")
            return None

    @classmethod
    def _parse_native(cls, skill_id: str, content: str, skill_path: str = "") -> Optional["SkillMetadata"]:
        """Parse our native skill.md format."""
        import re

        fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if not fm_match:
            return None

        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            return None

        return cls(
            skill_id=skill_id,
            skill_name=fm.get("skill", fm.get("name", skill_id)),
            version=fm.get("version", "1.0"),
            backend=fm.get("backend", "local"),
            backend_skill_id=fm.get("backend_skill_id", ""),
            description=fm.get("description", ""),
            inputs=fm.get("inputs", {}),
            tools=fm.get("tools", []),
            audit=fm.get("audit", []),
            monte_carlo=fm.get("monte_carlo", False),
            source_format="native",
            skill_path=skill_path,
            choices=fm.get("choices", None),
        )

    @classmethod
    def _parse_external(cls, skill_id: str, content: str, skill_path: str = "") -> Optional["SkillMetadata"]:
        """Parse Hermes/OpenClaw SKILL.md format."""
        import re

        fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if not fm_match:
            return None

        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            return None

        name = fm.get("name", skill_id)
        description = fm.get("description", "")
        requires = fm.get("requires", {})
        env_requires = requires.get("env", []) if isinstance(requires, dict) else []
        bins_requires = requires.get("bins", []) if isinstance(requires, dict) else []

        detected_backend = fm.get("backend", "local")

        return cls(
            skill_id=skill_id,
            skill_name=name,
            version=fm.get("version", "1.0"),
            backend=detected_backend,
            backend_skill_id="",
            description=description,
            inputs={},
            tools=[],
            audit=[],
            monte_carlo=False,
            source_format="external",
            requires_env=env_requires,
            requires_bins=bins_requires,
            skill_path=skill_path,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "version": self.version,
            "backend": self.backend,
            "backend_skill_id": self.backend_skill_id,
            "description": self.description,
            "inputs": self.inputs,
            "tools": self.tools,
            "audit": self.audit,
            "monte_carlo": self.monte_carlo,
            "source_format": self.source_format,
            "requires_env": self.requires_env,
            "requires_bins": self.requires_bins,
            "skill_path": self.skill_path,
            "choices": self.choices,
        }


class SkillDirWatcher:
    """Watch skill directories for changes and trigger hot-reload.

    Uses watchdog if available, otherwise falls back to polling.
    """

    def __init__(self, registry: 'SkillRegistry', directories: list[str]):
        self.registry = registry
        self.directories = [d for d in directories if os.path.isdir(d)]
        self._lock = threading.Lock()
        self._last_event = 0.0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("SkillDirWatcher started on %s", self.directories)

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        try:
            self._watch_watchdog()
        except ImportError:
            logger.info("watchdog not installed — falling back to polling SkillDirWatcher")
            self._watch_poll()
        except Exception as exc:
            logger.warning("watchdog error (%s) — falling back to polling", exc)
            self._watch_poll()

    def _watch_watchdog(self) -> None:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class _Handler(FileSystemEventHandler):
            def __init__(self, watcher: SkillDirWatcher):
                self.watcher = watcher

            def on_any_event(self, event):
                if not event.is_directory:
                    self.watcher._notify()

        handler = _Handler(self)
        observer = Observer()
        for d in self.directories:
            observer.schedule(handler, d, recursive=True)
        observer.start()
        try:
            while self._running:
                time.sleep(0.5)
        finally:
            observer.stop()
            observer.join()

    def _watch_poll(self) -> None:
        mtimes: dict[str, float] = {}
        for d in self.directories:
            for root, _dirs, files in os.walk(d):
                for f in files:
                    fpath = os.path.join(root, f)
                    try:
                        mtimes[fpath] = os.path.getmtime(fpath)
                    except OSError:
                        pass
        while self._running:
            time.sleep(_HOT_RELOAD_DEBOUNCE)
            changed = False
            for d in self.directories:
                for root, _dirs, files in os.walk(d):
                    for f in files:
                        fpath = os.path.join(root, f)
                        try:
                            new_mtime = os.path.getmtime(fpath)
                            if mtimes.get(fpath, 0) != new_mtime:
                                mtimes[fpath] = new_mtime
                                changed = True
                        except OSError:
                            pass
            if changed:
                self._notify()

    def _notify(self) -> None:
        now = time.time()
        if now - self._last_event < _HOT_RELOAD_DEBOUNCE:
            return
        self._last_event = now
        with self._lock:
            logger.info("Skill change detected — refreshing registry")
            self.registry._refresh_registry()


class SkillRegistry:
    """Unified registry for all skills across all backends."""

    def __init__(self, local_skills_root: Optional[str] = None):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.local_skills_root = local_skills_root or os.path.join(base, "skill_packs")
        self.lanes_root = os.path.join(base, "lanes")
        self._skills: Dict[str, SkillMetadata] = {}
        self._backends: Dict[str, SkillBackend] = {}
        self._discovered = False
        self._enable_watch = False
        self._watcher: Optional[SkillDirWatcher] = None
        self._refresh_lock = threading.Lock()

    def enable_watch(self) -> None:
        """Start watching skill directories for changes (hot-reload)."""
        if self._enable_watch:
            return
        self._enable_watch = True
        self._watcher = SkillDirWatcher(self, [self.local_skills_root, self.lanes_root])
        self._watcher.start()

    def disable_watch(self) -> None:
        """Stop watching skill directories."""
        self._enable_watch = False
        if self._watcher:
            self._watcher.stop()
            self._watcher = None

    def _refresh_registry(self) -> None:
        """Re-discover all skills from disk (thread-safe)."""
        with self._refresh_lock:
            self._skills.clear()
            self._backends.clear()
            self._discovered = False
            self.discover()

    def discover(self) -> None:
        """Discover all local skills from skill_packs and lanes."""
        if self._discovered:
            return

        self._discover_from_dir(self.local_skills_root)
        self._discover_from_dir(self.lanes_root)

        self._discovered = True

    def _discover_from_dir(self, root_dir: str) -> None:
        """Discover skills from a directory with 2-level nesting support.

        Supports:
        - skill_packs/<skill_name>/skill.md (flat structure)
        - skill_packs/<category>/<skill_name>/SKILL.md (imported structure)
        """
        if not os.path.exists(root_dir):
            return

        for item in os.listdir(root_dir):
            item_path = os.path.join(root_dir, item)
            if not os.path.isdir(item_path):
                continue

            # Check if this dir has its own skill file (flat structure)
            direct = self._find_direct_skill_file(item_path, item)
            if direct[0]:
                metadata = SkillMetadata.from_file(direct[0], direct[1])
                if metadata:
                    self._skills[direct[1]] = metadata
            else:
                # Category dir — iterate all children (imported structure)
                for subitem in os.listdir(item_path):
                    subpath = os.path.join(item_path, subitem)
                    if not os.path.isdir(subpath):
                        continue
                    child = self._find_direct_skill_file(subpath, subitem)
                    if child[0]:
                        metadata = SkillMetadata.from_file(child[0], child[1])
                        if metadata:
                            self._skills[child[1]] = metadata

    def _find_direct_skill_file(self, dir_path: str, dir_name: str) -> tuple:
        """Check only the immediate directory for SKILL.md or skill.md (no recursion)."""
        files = os.listdir(dir_path)
        if "SKILL.md" in files:
            return os.path.join(dir_path, "SKILL.md"), dir_name
        if "skill.md" in files:
            return os.path.join(dir_path, "skill.md"), dir_name
        return None, dir_name

    def register(self, metadata: SkillMetadata) -> None:
        """Manually register a skill."""
        self._skills[metadata.skill_id] = metadata

    def get(self, skill_id: str) -> Optional[SkillMetadata]:
        """Get skill metadata by ID."""
        self.discover()
        return self._skills.get(skill_id)

    def get_backend(self, skill_id: str) -> Optional[SkillBackend]:
        """Get the backend for a specific skill."""
        metadata = self.get(skill_id)
        if not metadata:
            return None

        if metadata.backend not in self._backends:
            try:
                self._backends[metadata.backend] = get_backend(metadata.backend)
            except ValueError:
                return None

        return self._backends[metadata.backend]

    def list_all(self, backend_filter: Optional[str] = None) -> List[SkillMetadata]:
        """List all skills, optionally filtered by backend."""
        self.discover()
        skills = list(self._skills.values())
        if backend_filter:
            skills = [s for s in skills if s.backend == backend_filter]
        return skills

    def list_by_backend(self) -> Dict[str, List[SkillMetadata]]:
        """List skills grouped by backend."""
        self.discover()
        result: Dict[str, List[SkillMetadata]] = {}
        for skill in self._skills.values():
            if skill.backend not in result:
                result[skill.backend] = []
            result[skill.backend].append(skill)
        return result

    def find_by_task(self, task_type: str) -> Optional[SkillMetadata]:
        """Find a skill that handles a specific task type."""
        self.discover()
        for skill in self._skills.values():
            if skill.skill_id == task_type or skill.skill_name == task_type:
                return skill
        return None

    def execute(self, skill_id: str, task: Dict, context: Dict) -> Dict[str, Any]:
        """Execute a skill using the appropriate backend."""
        metadata = self.get(skill_id)
        if not metadata:
            return {
                "success": False,
                "output": f"Skill not found: {skill_id}",
                "artifacts": [],
                "logs": [f"ERROR: No skill registered with ID '{skill_id}'"],
            }

        backend = self.get_backend(skill_id)
        if not backend:
            return {
                "success": False,
                "output": f"Backend not available: {metadata.backend}",
                "artifacts": [],
                "logs": [f"ERROR: Could not create backend '{metadata.backend}'"],
            }

        if metadata.skill_path:
            task["_skill_path"] = metadata.skill_path
        return backend.run(metadata.backend_skill_id, task, context)

    def translate_external_skill(
        self,
        external_skill: Dict[str, Any],
        target_backend: str,
    ) -> SkillMetadata:
        """Translate an external skill definition into our format.

        Args:
            external_skill: Dict with keys from external system (name, description, etc.)
            target_backend: Which backend this skill should use (claude, openclaw, hermes)

        Returns:
            SkillMetadata that can be registered in our registry
        """
        skill_id = external_skill.get("id", external_skill.get("name", "unknown"))
        return SkillMetadata(
            skill_id=skill_id,
            skill_name=external_skill.get("name", skill_id),
            version=external_skill.get("version", "1.0"),
            backend=target_backend,
            backend_skill_id=skill_id,
            description=external_skill.get("description", ""),
            inputs=external_skill.get("inputs", {}),
            tools=external_skill.get("tools", []),
            audit=external_skill.get("audit", []),
        )


_REGISTRY: Optional[SkillRegistry] = None
_REGISTRY_LOCK = None


def get_skill_registry(local_root: Optional[str] = None,
                        enable_watch: bool = False) -> SkillRegistry:
    """Get the global skill registry instance (thread-safe).

    Args:
        local_root: Optional override for skills root directory.
        enable_watch: If True, start hot-reload file watcher on first init.
    """
    global _REGISTRY, _REGISTRY_LOCK
    if _REGISTRY_LOCK is None:
        _REGISTRY_LOCK = threading.Lock()
    if _REGISTRY is None:
        with _REGISTRY_LOCK:
            if _REGISTRY is None:
                _REGISTRY = SkillRegistry(local_root)
                if enable_watch:
                    _REGISTRY.enable_watch()
    return _REGISTRY


def reset_skill_registry() -> None:
    """Reset the global registry (useful for testing)."""
    global _REGISTRY
    with _REGISTRY_LOCK:
        if _REGISTRY is not None:
            _REGISTRY.disable_watch()
        _REGISTRY = None