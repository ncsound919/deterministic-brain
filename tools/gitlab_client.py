"""GitLab API client — issues, MRs, pipelines, repos.

Teams on GitLab instead of GitHub. Same deterministic approach.
Uses tools/api_client.py AuthenticatedClient.

Token savings: ~300 tokens per GitLab API call vs LLM.
"""

from __future__ import annotations
import os
from typing import Dict, List

from tools.api_client import AuthenticatedClient


class GitLabClient:
    """GitLab API v4 client."""

    def __init__(self, token: str = "", instance: str = ""):
        self.token = token or os.environ.get("GITLAB_TOKEN", "")
        self.instance = (instance or os.environ.get("GITLAB_INSTANCE", "https://gitlab.com")).rstrip("/")
        self.client = AuthenticatedClient(
            base_url=f"{self.instance}/api/v4",
            api_key=self.token,
            auth_header="PRIVATE-TOKEN",
            auth_prefix="",
        )

    def list_projects(self, search: str = "", owned: bool = True) -> Dict:
        params = {"owned": str(owned).lower(), "per_page": 50}
        if search:
            params["search"] = search
        return self.client.get("/projects", params=params)

    def list_issues(self, project_id: int, state: str = "opened") -> Dict:
        return self.client.get(f"/projects/{project_id}/issues",
                               params={"state": state, "per_page": 50})

    def create_issue(self, project_id: int, title: str,
                     description: str = "", labels: List[str] = None) -> Dict:
        data = {"title": title, "description": description}
        if labels:
            data["labels"] = ",".join(labels)
        return self.client.post(f"/projects/{project_id}/issues", data=data)

    def list_merge_requests(self, project_id: int, state: str = "opened") -> Dict:
        return self.client.get(f"/projects/{project_id}/merge_requests",
                               params={"state": state})

    def get_pipeline(self, project_id: int, pipeline_id: int) -> Dict:
        return self.client.get(f"/projects/{project_id}/pipelines/{pipeline_id}")

    def list_pipelines(self, project_id: int, status: str = "") -> Dict:
        params = {"per_page": 10}
        if status:
            params["status"] = status
        return self.client.get(f"/projects/{project_id}/pipelines", params=params)

    def search_projects(self, query: str) -> Dict:
        return self.client.get("/projects", params={"search": query, "per_page": 20})
