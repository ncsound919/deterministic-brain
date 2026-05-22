"""MoE Router — deterministic decision tree, config-driven, zero LLM."""
from __future__ import annotations
import os
import re
import yaml
from typing import Dict, Optional

_DEFAULT_ROUTES: Dict[str, str] = {
    "create-react-component": "skill_packs/react",
    "scaffold-rest-api":      "skill_packs/rest_api",
    "add-auth":               "skill_packs/auth",
    "generate-dockerfile":    "skill_packs/docker",
    "audit-repo":             "lanes/audit_repo",
    "live-docs-to-skill":     "lanes/live_docs_to_skill",
    "landing-page":           "skill_packs/landing-page",
    "react-component":        "skill_packs/react-component",
    "api-scaffold":           "skill_packs/api-scaffold",
    "css-layout":             "skill_packs/css-layout",
}

LANE_PATTERNS = [
    (re.compile(r'\b(code|program|function|class|implement|refactor|write|build)\b', re.IGNORECASE), 'coding'),
    (re.compile(r'\b(policy|rule|approval|compliance|budget|business|logic)\b', re.IGNORECASE), 'business_logic'),
    (re.compile(r'\b(agent|browser|click|navigate|autonom)\b', re.IGNORECASE), 'agent_brain'),
    (re.compile(r'\b(tool|call|invoke|api|validate|execute)\b', re.IGNORECASE), 'tool_calling'),
]

def route_lane(query: str) -> str:
    """Route a natural language query to a lane name.

    Returns one of: coding, business_logic, agent_brain, tool_calling, cross_domain
    Uses deterministic regex matching - same query always returns same lane.
    """
    q_lower = query.lower()
    for pattern, lane in LANE_PATTERNS:
        if pattern.search(q_lower):
            return lane
    return 'cross_domain'


class MoERouter:
    def __init__(self, routes_path: Optional[str] = None, warn_on_missing: bool = True):
        self.routes = dict(_DEFAULT_ROUTES)
        self.aliases: Dict[str, list] = {}
        if routes_path and os.path.exists(routes_path):
            try:
                with open(routes_path, encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                self.routes.update(config.get("routes", {}))
                self.aliases = config.get("aliases", {})
            except (yaml.YAMLError, Exception) as e:
                import logging as _log
                _log.getLogger(__name__).warning("MoERouter: failed to load %s: %s", routes_path, e)
        if warn_on_missing:
            issues = self.validate_routes()
            if issues:
                import warnings
                for issue in issues:
                    warnings.warn(f"[MoERouter] {issue}")

    def validate_routes(self) -> list[str]:
        """Check all registered routes have skill.md files. Returns list of warnings."""
        missing = []
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for task, path in self.routes.items():
            full_path = os.path.join(base, path)
            skill_file = os.path.join(full_path, "skill.md")
            if not os.path.exists(skill_file):
                missing.append(f"Task '{task}' -> {path}/skill.md (NOT FOUND)")
        return missing

    def route(self, task: Dict) -> Optional[str]:
        task_name = task.get("task", "unknown")
        path = self.routes.get(task_name)
        if path:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            full_path = os.path.join(base, path)
            skill_file = os.path.join(full_path, "skill.md")
            if not os.path.exists(skill_file):
                return None
        return path

    def register(self, task_name: str, expert_path: str) -> None:
        """Dynamically register a new route at runtime."""
        self.routes[task_name] = expert_path

    def enriched_candidates(self) -> list[tuple[str, str]]:
        """Return (skill_id, enriched_text) pairs for BM25 ranking.

        Each enriched_text = readable skill name + aliases, so BM25
        has meaningful tokens to match against the query.
        """
        results = []
        for skill_id in self.routes:
            alias_phrases = self.aliases.get(skill_id, [])
            readable_id = skill_id.replace("-", " ").replace("_", " ")
            enriched = f"{readable_id} {' '.join(alias_phrases)}"
            results.append((skill_id, enriched.strip()))
        return results

    def enriched_texts(self) -> list[str]:
        """Return just the enriched text strings (for legacy TF cosine compatibility)."""
        return [t for _, t in self.enriched_candidates()]
