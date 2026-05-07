"""GitHub API client — issues, PRs, repos, CI status.

Token savings: ~300 tokens per GitHub API call vs LLM-based approach.
"""

from __future__ import annotations
import os
from typing import Dict, List

from tools.api_client import AuthenticatedClient


class GitHubClient:
    """GitHub API v3 client with repo/issue/PR management."""

    def __init__(self, token: str = ""):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.client = AuthenticatedClient(
            base_url="https://api.github.com",
            api_key=self.token,
            auth_prefix="token ",
        )

    def list_repos(self, owner: str = "") -> Dict:
        path = f"/users/{owner}/repos" if owner else "/user/repos"
        return self.client.get(path)

    def list_issues(self, owner: str, repo: str, state: str = "open") -> Dict:
        return self.client.get(f"/repos/{owner}/{repo}/issues",
                               params={"state": state, "per_page": 50})

    def create_issue(self, owner: str, repo: str, title: str,
                     body: str, labels: List[str] = None) -> Dict:
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        return self.client.post(f"/repos/{owner}/{repo}/issues", data=data)

    def list_prs(self, owner: str, repo: str, state: str = "open") -> Dict:
        return self.client.get(f"/repos/{owner}/{repo}/pulls",
                               params={"state": state})

    def get_ci_status(self, owner: str, repo: str, ref: str = "main") -> Dict:
        return self.client.get(f"/repos/{owner}/{repo}/commits/{ref}/status")

    def search_code(self, query: str) -> Dict:
        return self.client.get("/search/code", params={"q": query, "per_page": 10})
