"""Linter tool — dispatches by file extension."""
from __future__ import annotations
import os
import subprocess


EXT_COMMANDS = {
    ".tsx": ["npx", "eslint"],
    ".ts":  ["npx", "eslint"],
    ".js":  ["npx", "eslint"],
    ".py":  ["pylint", "--errors-only"],
}


def run_linter(file_path: str) -> dict:
    ext = os.path.splitext(file_path)[1].lower()
    cmd = EXT_COMMANDS.get(ext)
    if not cmd:
        return {"status": "skipped", "reason": f"No linter for {ext}"}
    result = subprocess.run(
        cmd + [file_path], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Linter failed ({file_path}):\n{result.stderr or result.stdout}")
    return {"status": "ok", "file": file_path}
