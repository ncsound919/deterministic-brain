"""Task Parser — regex + keyword matching, zero LLM."""
from __future__ import annotations
import re
from typing import Dict, List


PATTERNS = [
    # Old explicit patterns (backward compat)
    (
        r"create (?:a )?react component (?:named |called )?([\w]+)(?: with props ([\w ,]+))?",
        {"task": "react-component",
         "group_map": {"component_name": 1, "props": 2}},
    ),
    (
        r"scaffold (?:a )?(?:rest )?api for ([\w]+)",
        {"task": "api-scaffold",
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
    # Natural language build patterns
    (
        r"(?:build|create|make|generate|design) (?:a |an |the )?(?:landing page|homepage)",
        {"task": "landing-page"},
    ),
    (
        r"(?:build|create|make|generate) (?:a |an )?(?:react component|component)(?: (?:named|called) ([\w]+))?",
        {"task": "react-component", "group_map": {"component_name": 1}},
    ),
    (
        r"(?:build|create|make|generate|scaffold) (?:a |an )?(?:api|backend|server|endpoint)",
        {"task": "api-scaffold"},
    ),
    (
        r"(?:build|create|make|generate) (?:a |an )?(?:layout|grid|flex|sidebar)",
        {"task": "css-layout"},
    ),
    (
        r"(?:build|create|make|generate|design|code)\s+(?:a |an |the )?(?:responsive )?(?:web(?:site|.?page|.?app)?|page|dashboard|portfolio|blog|shop|store)",
        {"task": "landing-page"},
    ),
    (
        r"(?:build|create|make|generate|design|code)\s+.+",
        {"task": "landing-page"},
    ),
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
                if "props" in task and task["props"]:
                    task["props"] = [p.strip() for p in task["props"].split(",")]
                elif "props" in task:
                    task["props"] = []
                return task
        return {"task": "unknown", "raw": user_input}
