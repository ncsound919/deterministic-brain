"""Linear task sync — bridge issue tracker to the brain's skill system.

Teams use Linear for task management. This client creates, updates, and
syncs Linear issues with skill execution results.

Token savings: ~350 tokens per Linear API call vs LLM wrapper.
"""

from __future__ import annotations
import os
from typing import Dict

from tools.api_client import AuthenticatedClient


class LinearClient:
    """Linear GraphQL API client for task management."""

    def __init__(self, api_key: str = ""):
        self.client = AuthenticatedClient(
            base_url="https://api.linear.app/graphql",
            api_key=api_key or os.environ.get("LINEAR_API_KEY", ""),
            auth_prefix="",
        )

    def _query(self, query: str, variables: dict = None) -> Dict:
        """Execute a GraphQL query."""
        data = {"query": query}
        if variables:
            data["variables"] = variables
        return self.client.post("", data=data)

    def list_teams(self) -> Dict:
        q = """query { teams { nodes { id name key } } }"""
        return self._query(q)

    def list_issues(self, team_id: str, limit: int = 25) -> Dict:
        q = """
        query($teamId: String!, $limit: Int!) {
          issues(filter: {team: {id: {eq: $teamId}}}, first: $limit) {
            nodes { id title state { name } priority assignee { name } url }
          }
        }
        """
        return self._query(q, {"teamId": team_id, "limit": limit})

    def create_issue(self, team_id: str, title: str,
                     description: str = "", priority: int = 2) -> Dict:
        q = """
        mutation($title: String!, $description: String!, $teamId: String!, $priority: Int!) {
          issueCreate(input: {title: $title, description: $description,
                              teamId: $teamId, priority: $priority}) {
            success
            issue { id title url }
          }
        }
        """
        return self._query(q, {"title": title, "description": description,
                                "teamId": team_id, "priority": priority})

    def search_issues(self, query_str: str, limit: int = 10) -> Dict:
        q = """
        query($query: String!, $limit: Int!) {
          issueSearch(query: $query, first: $limit) {
            nodes { id title state { name } priority url }
          }
        }
        """
        return self._query(q, {"query": query_str, "limit": limit})


class JiraClient:
    """Jira REST API client for teams on Atlassian stack."""

    def __init__(self, email: str = "", token: str = "", domain: str = ""):
        self.client = AuthenticatedClient(
            base_url=f"https://{domain or os.environ.get('JIRA_DOMAIN', '')}.atlassian.net/rest/api/3",
            api_key=token or os.environ.get("JIRA_API_TOKEN", ""),
            auth_header="Authorization",
            auth_prefix="Basic ",
        )
        import base64
        self.email = email or os.environ.get("JIRA_EMAIL", "")
        raw_token = token or os.environ.get("JIRA_API_TOKEN", "")
        if self.email and raw_token:
            self.client.api_key = base64.b64encode(f"{self.email}:{raw_token}".encode()).decode()

    def list_issues(self, jql: str = "project = PROJ", limit: int = 20) -> Dict:
        return self.client.post("/search", data={"jql": jql, "maxResults": limit})

    def create_issue(self, project_key: str, summary: str,
                     description: str = "", issue_type: str = "Task") -> Dict:
        return self.client.post("/issue", data={
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
            }
        })

    def get_issue(self, issue_key: str) -> Dict:
        return self.client.get(f"/issue/{issue_key}")
