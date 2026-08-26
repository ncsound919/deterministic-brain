"""File I/O tools — confined to the workspace root.

Untrusted paths (from skill directives, API payloads, task inputs) are
resolved via tools.workspace.resolve_confined so they cannot escape the
workspace via absolute paths, ``..`` segments, or symlinks.
Set BRAIN_ALLOW_ANY_PATH=1 to disable confinement for trusted local use.
"""
from __future__ import annotations
import os

from tools.workspace import resolve_confined


def file_write(path: str, content: str) -> dict:
    try:
        safe_path = str(resolve_confined(path))
    except PermissionError as e:
        return {"error": str(e)}
    os.makedirs(os.path.dirname(safe_path) or ".", exist_ok=True)
    with open(safe_path, "w") as f:
        f.write(content)
    return {"status": "ok", "path": safe_path}


def file_read(path: str) -> dict:
    try:
        safe_path = str(resolve_confined(path, must_exist=True))
    except FileNotFoundError as e:
        return {"error": str(e)}
    except PermissionError as e:
        return {"error": str(e)}
    with open(safe_path) as f:
        return {"content": f.read(), "path": safe_path}
