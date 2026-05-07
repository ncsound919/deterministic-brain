"""File I/O tools."""
from __future__ import annotations
import os


def file_write(path: str, content: str) -> dict:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return {"status": "ok", "path": path}


def file_read(path: str) -> dict:
    if not os.path.exists(path):
        return {"error": f"File not found: {path}"}
    with open(path) as f:
        return {"content": f.read(), "path": path}
