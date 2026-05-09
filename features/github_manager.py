"""GitHub Manager — token-based repo ops, auto-commit, skill sync.

Handles: repo creation, cloning, commit, push, PR creation,
auto-downloading Claude skill packs from GitHub, background sync.
"""
from __future__ import annotations
import os
import subprocess
import json
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class GHRepo:
    owner: str
    name: str
    url: str = ""
    description: str = ""
    stars: int = 0
    language: str = ""
    local_path: str = ""
    is_cloned: bool = False

    def to_dict(self) -> Dict:
        return {
            "owner": self.owner, "name": self.name, "url": self.url,
            "description": self.description, "stars": self.stars,
            "language": self.language, "local_path": self.local_path,
            "is_cloned": self.is_cloned,
        }


class GitHubManager:
    def __init__(self, token: str = "", work_dir: str = "repos"):
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self._account_tokens: Dict[str, str] = {}
        self._load_account_tokens()
        self.work_dir = work_dir
        self._repos: Dict[str, GHRepo] = {}
        os.makedirs(work_dir, exist_ok=True)

    def _load_account_tokens(self) -> None:
        try:
            from config.credentials import get_credential_vault
            v = get_credential_vault()
            for key, val in v.get_category("github").items():
                if key.startswith("token_") and val:
                    account = key.replace("token_", "")
                    self._account_tokens[account] = val
        except ImportError:
            pass

    def token_for(self, owner: str) -> str:
        """Get the GitHub token for a specific account, falling back to default."""
        return self._account_tokens.get(owner, self.token)

    def list_accounts(self) -> List[str]:
        return sorted(self._account_tokens.keys())

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/vnd.github.v3+json", "User-Agent": "DeterministicBrain/1.0"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _api(self, path: str) -> Any:
        req = urllib.request.Request(f"https://api.github.com{path}", headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            return {"error": str(e)}

    def search_repos(self, query: str, per_page: int = 10) -> List[GHRepo]:
        data = self._api(f"/search/repositories?q={query}&per_page={per_page}&sort=stars")
        if isinstance(data, dict) and data.get("error"):
            return []
        repos = []
        for item in data.get("items", []):
            r = GHRepo(
                owner=item["owner"]["login"], name=item["name"],
                url=item["html_url"], description=item.get("description", ""),
                stars=item.get("stargazers_count", 0),
                language=item.get("language", ""),
            )
            repos.append(r)
            self._repos[f"{r.owner}/{r.name}"] = r
        return repos

    def list_user_repos(self, username: str, include_archived: bool = True) -> List[Dict]:
        """Fetch ALL repos for a GitHub user via paginated API.

        Returns raw dicts with full repo metadata: name, description,
        language, stars, forks, last_pushed, archived, private, etc.
        """
        repos: List[Dict] = []
        page = 1
        per_page = 100

        while True:
            path = (
                f"/users/{username}/repos"
                f"?per_page={per_page}&page={page}"
                f"&sort=updated&type=all"
            )
            data = self._api(path)
            if isinstance(data, dict) and data.get("error"):
                break
            if not isinstance(data, list) or not data:
                break
            repos.extend(data)
            if len(data) < per_page:
                break
            page += 1

        if not include_archived:
            repos = [r for r in repos if not r.get("archived", False)]

        for r in repos:
            key = f"{r['owner']['login']}/{r['name']}"
            self._repos[key] = GHRepo(
                owner=r["owner"]["login"],
                name=r["name"],
                url=r["html_url"],
                description=r.get("description", ""),
                stars=r.get("stargazers_count", 0),
                language=r.get("language", ""),
            )

        return repos

    def clone(self, owner: str, repo: str) -> Optional[str]:
        path = os.path.join(self.work_dir, repo)
        url = f"https://github.com/{owner}/{repo}.git"
        token = self.token_for(owner)
        if token:
            url = f"https://{token}@github.com/{owner}/{repo}.git"
        try:
            result = subprocess.run(
                ["git", "clone", url, path],
                capture_output=True, text=True, timeout=60,
                cwd=self.work_dir, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            if result.returncode == 0:
                key = f"{owner}/{repo}"
                if key in self._repos:
                    self._repos[key].local_path = path
                    self._repos[key].is_cloned = True
                return path
        except Exception as e:
            pass
        return None

    def commit_and_push(self, repo_path: str, message: str, branch: str = "main") -> Dict:
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            subprocess.run(["git", "add", "."], cwd=repo_path, capture_output=True, timeout=10, creationflags=flags)
            result = subprocess.run(
                ["git", "commit", "-m", message],
                cwd=repo_path, capture_output=True, text=True, timeout=10, creationflags=flags,
            )
            if "nothing to commit" in result.stdout + result.stderr:
                return {"status": "nothing_to_commit"}
            push = subprocess.run(
                ["git", "push", "origin", branch],
                cwd=repo_path, capture_output=True, text=True, timeout=30, creationflags=flags,
            )
            if push.returncode == 0:
                return {"status": "ok", "message": message, "branch": branch}
            return {"status": "push_failed", "error": push.stderr}
        except Exception as e:
            return {"error": str(e)}

    def list_local(self) -> List[GHRepo]:
        return [r for r in self._repos.values() if r.is_cloned]

    def download_skill_packs(self, target_dir: str = "skill_packs") -> Dict:
        """Auto-download Claude/OpenAI skill packs from GitHub."""
        queries = [
            "anthropics/claude-code skills topic:claude-code",
            "skill-pack topic:ai-agent language:markdown",
        ]
        downloaded = 0
        for q in queries:
            repos = self.search_repos(q, per_page=20)
            for repo in repos:
                if repo.name.endswith("-skills") or "skill" in repo.name.lower():
                    path = self.clone(repo.owner, repo.name)
                    if path:
                        downloaded += 1
        return {"downloaded": downloaded, "total_found": sum(len(self.search_repos(q, 5)) for q in queries)}


_MANAGER: Optional[GitHubManager] = None


def get_github() -> GitHubManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = GitHubManager()
    if not _MANAGER.token:
        try:
            from config.credentials import get_credential_vault
            token = get_credential_vault().get("github", "token")
            if token:
                _MANAGER.token = token
        except ImportError:
            pass
    return _MANAGER
