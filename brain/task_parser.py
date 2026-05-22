"""Task Parser — regex + keyword matching, zero LLM."""
from __future__ import annotations
import re
from typing import Dict


PATTERNS = [
    # Old explicit patterns (backward compat)
    (
        re.compile(r"create (?:a )?react component (?:named |called )?([\w]+)(?: with props ([\w ,]+))?", re.IGNORECASE),
        {"task": "react-component",
         "group_map": {"component_name": 1, "props": 2}},
    ),
    (
        re.compile(r"scaffold (?:a )?(?:rest )?api for ([\w]+)", re.IGNORECASE),
        {"task": "api-scaffold",
         "group_map": {"resource": 1}},
    ),
    (
        re.compile(r"add auth to ([\w]+)", re.IGNORECASE),
        {"task": "add-auth",
         "group_map": {"resource": 1}},
    ),
    (
        re.compile(r"generate (?:a )?dockerfile for ([\w]+)", re.IGNORECASE),
        {"task": "generate-dockerfile",
         "group_map": {"service": 1}},
    ),
    (
        re.compile(r"audit (?:repo|repository|project) ([\w./\-]+)", re.IGNORECASE),
        {"task": "audit-repo",
         "group_map": {"repo_path": 1}},
    ),
    (
        re.compile(r"scrape docs (?:from )?(.+)", re.IGNORECASE),
        {"task": "live-docs-to-skill",
         "group_map": {"url": 1}},
    ),
    # Natural language build patterns
    (
        re.compile(r"(?:build|create|make|generate|design) (?:a |an |the )?(?:landing page|homepage)", re.IGNORECASE),
        {"task": "landing-page"},
    ),
    (
        re.compile(r"(?:build|create|make|generate) (?:a |an )?(?:react component|component)(?: (?:named|called) ([\w]+))?", re.IGNORECASE),
        {"task": "react-component", "group_map": {"component_name": 1}},
    ),
    (
        re.compile(r"(?:build|create|make|generate|scaffold) (?:a |an )?(?:api|backend|server|endpoint)", re.IGNORECASE),
        {"task": "api-scaffold"},
    ),
    (
        re.compile(r"(?:build|create|make|generate) (?:a |an )?(?:layout|grid|flex|sidebar)", re.IGNORECASE),
        {"task": "css-layout"},
    ),
    (
        re.compile(r"(?:build|create|make|generate|design|code)\s+(?:a |an |the )?(?:responsive )?(?:web(?:site|.?page|.?app)?|page|dashboard|portfolio|blog|shop|store)", re.IGNORECASE),
        {"task": "landing-page"},
    ),
    (
        re.compile(r"(?:build|create|make|generate|design|code)\s+.+", re.IGNORECASE),
        {"task": "landing-page"},
    ),
    (
        re.compile(r"Initialize session for agent: ([\w\-]+)", re.IGNORECASE),
        {"task": "initialize-session", "group_map": {"agent_id": 1}},
    ),
    (
        re.compile(r".*", re.IGNORECASE),
        {"task": "unknown"},
    ),
]


class TaskParser:
    def __init__(self, extra_patterns: list | None = None):
        if extra_patterns:
            compiled = []
            for regex_str, mapping in extra_patterns:
                if isinstance(regex_str, re.Pattern):
                    compiled.append((regex_str, mapping))
                else:
                    compiled.append((re.compile(regex_str, re.IGNORECASE), mapping))
            self.patterns = compiled + PATTERNS
        else:
            self.patterns = list(PATTERNS)

    def parse(self, user_input: str) -> Dict:
        text = user_input.strip()
        for regex, mapping in self.patterns:
            m = regex.match(text)
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
