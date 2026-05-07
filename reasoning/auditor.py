"""DeterministicAuditor — linters, static analysis, exit-code-based verdicts."""
from __future__ import annotations
import subprocess
from typing import Dict, List


class DeterministicAuditor:
    """
    Runs the audit commands declared in a skill.md frontmatter.
    Every verdict is based on subprocess exit codes — no LLM, no guessing.
    """

    def run_audit(self, commands: List[str], ctx: Dict) -> bool:
        for cmd_template in commands:
            try:
                cmd = cmd_template.format(**ctx)
            except KeyError:
                cmd = cmd_template
            parts = cmd.split()
            try:
                subprocess.run(parts, capture_output=True, text=True, check=True, timeout=60)
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
                return False
        return True

    def score(self, result: Dict) -> int:
        """Minimal binary score — used as fallback if scorer.py is not wired yet."""
        return 1 if result.get("success") else 0
