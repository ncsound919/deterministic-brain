"""MoE Router — deterministic decision tree, config-driven, zero LLM."""
from __future__ import annotations
import os
import yaml
from typing import Dict, Optional

_DEFAULT_ROUTES: Dict[str, str] = {
    "create-react-component": "skill_packs/react",
    "scaffold-rest-api":      "skill_packs/rest_api",
    "add-auth":               "skill_packs/auth",
    "generate-dockerfile":    "skill_packs/docker",
    "audit-repo":             "lanes/audit_repo",
    "live-docs-to-skill":     "lanes/live_docs_to_skill",
}


class MoERouter:
    def __init__(self, routes_path: Optional[str] = None):
        self.routes = dict(_DEFAULT_ROUTES)
        if routes_path and os.path.exists(routes_path):
            with open(routes_path) as f:
                overrides = yaml.safe_load(f) or {}
            self.routes.update(overrides.get("routes", {}))

    def route(self, task: Dict) -> Optional[str]:
        task_name = task.get("task", "unknown")
        return self.routes.get(task_name)

    def register(self, task_name: str, expert_path: str) -> None:
        """Dynamically register a new route at runtime."""
        self.routes[task_name] = expert_path
