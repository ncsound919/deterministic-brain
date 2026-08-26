"""Workspace path confinement helpers.

All file-touching tools (file_read/file_write, template uploads, forge
validate/install, git clone targets, zip extraction) must resolve untrusted
paths through :func:`resolve_confined` so they can never escape the workspace
root via ``..`` segments, symlinks, or absolute paths.

Escape hatch for trusted CLI use: set ``BRAIN_ALLOW_ANY_PATH=1``.
"""
from __future__ import annotations

import os
from pathlib import Path


def workspace_root() -> Path:
    """The directory all tool-mediated file access is confined to."""
    return Path(os.getenv("BRAIN_WORKSPACE_ROOT", os.getcwd())).resolve()


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def allow_any_path() -> bool:
    """True when path confinement is explicitly disabled (trusted local use)."""
    return os.getenv("BRAIN_ALLOW_ANY_PATH", "").lower() in ("1", "true", "yes")


def resolve_confined(path: str | os.PathLike, base: str | os.PathLike | None = None,
                     must_exist: bool = False) -> Path:
    """Resolve ``path`` relative to ``base`` and refuse escapes.

    Returns the fully-resolved Path. Raises ``PermissionError`` when the
    resolved path lands outside the confinement root, and ``FileNotFoundError``
    when ``must_exist`` is set and the path does not exist.
    """
    root = Path(base).resolve() if base else workspace_root()
    p = Path(path)
    if not p.is_absolute():
        p = root / p
    try:
        resolved = p.resolve()
    except OSError as e:
        raise FileNotFoundError(f"Unresolvable path: {path}") from e
    if not allow_any_path() and resolved != root and not _is_within(resolved, root):
        raise PermissionError(f"Path escapes workspace root: {path}")
    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")
    return resolved
