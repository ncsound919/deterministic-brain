"""Task Parser — regex + keyword matching, zero LLM."""
from __future__ import annotations
import re
from typing import Dict, List


PATTERNS = [
    (
        r"create (?:a )?react component named ([\w]+)(?: with props ([\w ,]+))?",
        {"task": "create-react-component",
         "group_map": {"component_name": 1, "props": 2}},
    ),
    (
        r"scaffold (?:a )?rest api for ([\w]+)",
        {"task": "scaffold-rest-api",
         "group_map": {"resource": 1}},
    ),
    (
        r"add auth to ([\w]+)",
        {"task": "add-auth",
         "group_map": {"resource": 1}},
    ),
    (
        r"generate (?:a )?dockerfile for ([\w]+)",
        {"task": "generate-dockerfile",
         "group_map": {"service": 1}},
    ),
    (
        r"audit (?:repo|repository|project) ([\w./\-]+)",
        {"task": "audit-repo",
         "group_map": {"repo_path": 1}},
    ),
    (
        r"scrape docs (?:from )?(.+)",
        {"task": "live-docs-to-skill",
         "group_map": {"url": 1}},
    ),
    # fallback
    (r".*", {"task": "unknown"}),
]


class TaskParser:
    def __init__(self, extra_patterns: list | None = None):
        self.patterns = (extra_patterns or []) + PATTERNS

    def parse(self, user_input: str) -> Dict:
        for regex, mapping in self.patterns:
            m = re.match(regex, user_input.strip(), re.IGNORECASE)
            if m:
                task: Dict = {"task": mapping["task"], "raw": user_input}
                for param, idx in mapping.get("group_map", {}).items():
                    val = m.group(idx) if m.lastindex and idx <= m.lastindex else ""
                    task[param] = val.strip() if val else ""
                # normalise props string → list
                if "props" in task and task["props"]:
                    task["props"] = [p.strip() for p in task["props"].split(",")]
                elif "props" in task:
                    task["props"] = []
                return task
        return {"task": "unknown", "raw": user_input}
