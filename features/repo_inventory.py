"""Repo Inventory — full awareness of all Tap's repos across GitHub accounts.

Discovers every repo on both accounts (tap919, ncsound919), tracks their
state (stars, language, last pushed, archived, private, hosted pages),
and feeds the swarm worker with repos that need auditing.

Persisted to .repo_inventory.json and refreshed during KAIROS idle cycles.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

INVENTORY_PATH = ".repo_inventory.json"
TAP_ACCOUNTS = ["tap919", "ncsound919"]


@dataclass
class RepoEntry:
    owner: str
    name: str
    full_name: str = ""
    url: str = ""
    description: str = ""
    language: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    last_pushed: str = ""
    created_at: str = ""
    updated_at: str = ""
    archived: bool = False
    private: bool = False
    fork: bool = False
    has_pages: bool = False
    topics: List[str] = field(default_factory=list)
    homepage: str = ""
    default_branch: str = "main"
    size_kb: int = 0

    # Brain-managed fields
    is_cloned: bool = False
    local_path: str = ""
    audited: bool = False
    last_audit: str = ""
    audit_score: int = 0
    in_swarm_queue: bool = False
    swarm_task_id: str = ""
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "owner": self.owner,
            "name": self.name,
            "full_name": self.full_name,
            "url": self.url,
            "description": self.description,
            "language": self.language,
            "stars": self.stars,
            "forks": self.forks,
            "open_issues": self.open_issues,
            "last_pushed": self.last_pushed,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "archived": self.archived,
            "private": self.private,
            "fork": self.fork,
            "has_pages": self.has_pages,
            "topics": self.topics,
            "homepage": self.homepage,
            "default_branch": self.default_branch,
            "size_kb": self.size_kb,
            "is_cloned": self.is_cloned,
            "local_path": self.local_path,
            "audited": self.audited,
            "last_audit": self.last_audit,
            "audit_score": self.audit_score,
            "in_swarm_queue": self.in_swarm_queue,
            "swarm_task_id": self.swarm_task_id,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(d: Dict) -> RepoEntry:
        return RepoEntry(
            owner=d.get("owner", ""),
            name=d.get("name", ""),
            full_name=d.get("full_name", ""),
            url=d.get("url", ""),
            description=d.get("description", ""),
            language=d.get("language", ""),
            stars=d.get("stars", 0),
            forks=d.get("forks", 0),
            open_issues=d.get("open_issues", 0),
            last_pushed=d.get("last_pushed", ""),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            archived=d.get("archived", False),
            private=d.get("private", False),
            fork=d.get("fork", False),
            has_pages=d.get("has_pages", False),
            topics=d.get("topics", []),
            homepage=d.get("homepage", ""),
            default_branch=d.get("default_branch", "main"),
            size_kb=d.get("size_kb", 0),
            is_cloned=d.get("is_cloned", False),
            local_path=d.get("local_path", ""),
            audited=d.get("audited", False),
            last_audit=d.get("last_audit", ""),
            audit_score=d.get("audit_score", 0),
            in_swarm_queue=d.get("in_swarm_queue", False),
            swarm_task_id=d.get("swarm_task_id", ""),
            notes=d.get("notes", ""),
        )

    @staticmethod
    def from_github_api(api_data: Dict, owner: str) -> RepoEntry:
        return RepoEntry(
            owner=owner,
            name=api_data.get("name", ""),
            full_name=api_data.get("full_name", ""),
            url=api_data.get("html_url", ""),
            description=api_data.get("description") or "",
            language=api_data.get("language") or "",
            stars=api_data.get("stargazers_count", 0),
            forks=api_data.get("forks_count", 0),
            open_issues=api_data.get("open_issues_count", 0),
            last_pushed=api_data.get("pushed_at", ""),
            created_at=api_data.get("created_at", ""),
            updated_at=api_data.get("updated_at", ""),
            archived=api_data.get("archived", False),
            private=api_data.get("private", False),
            fork=api_data.get("fork", False),
            has_pages=api_data.get("has_pages", False),
            topics=api_data.get("topics", []),
            homepage=api_data.get("homepage") or "",
            default_branch=api_data.get("default_branch", "main"),
            size_kb=api_data.get("size", 0),
        )


class RepoInventory:
    """Full inventory of all repos across Tap's GitHub accounts.

    Lifecycle:
      1. discover()  — fetch all repos from GitHub API
      2. refresh()   — re-fetch and merge with local state
      3. auto_queue() — feed un-audited repos to swarm worker
      4. persist to .repo_inventory.json

    Accounts: tap919, ncsound919
    """

    def __init__(self, inventory_path: str = INVENTORY_PATH):
        self._path = Path(inventory_path)
        self._repos: Dict[str, RepoEntry] = {}
        self._accounts = list(TAP_ACCOUNTS)
        self._last_refresh: str = ""
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text())
            for r in data.get("repos", []):
                entry = RepoEntry.from_dict(r)
                self._repos[entry.full_name] = entry
            self._last_refresh = data.get("last_refresh", "")
        except (json.JSONDecodeError, OSError):
            pass

    def _save(self) -> None:
        data = {
            "last_refresh": self._last_refresh,
            "accounts": self._accounts,
            "total_repos": len(self._repos),
            "repos": [r.to_dict() for r in sorted(
                self._repos.values(), key=lambda x: (-x.stars, x.full_name)
            )],
        }
        self._path.write_text(json.dumps(data, indent=2))

    # ── Discovery ───────────────────────────────────────────────────

    def discover(self, accounts: Optional[List[str]] = None) -> Dict:
        """Fetch all repos from GitHub API for all (or specified) accounts."""
        accounts = accounts or self._accounts
        now = datetime.now(timezone.utc).isoformat()

        try:
            from features.github_manager import get_github
            gh = get_github()
        except ImportError:
            return {"status": "error", "reason": "github_manager_not_loaded"}

        if not gh.token:
            return {
                "status": "error",
                "reason": (
                    "No GitHub token configured. Set GITHUB_TOKEN env var "
                    "or store in credential vault: "
                    "get_credential_vault().set('github', 'token', 'ghp_xxx')"
                ),
            }

        discovered = 0
        new_repos = 0
        errors: List[str] = []

        for account in accounts:
            try:
                repos_raw = gh.list_user_repos(account, include_archived=True)
            except Exception as e:
                errors.append(f"{account}: {e}")
                continue

            for raw in repos_raw:
                full_name = raw.get("full_name", "")
                if not full_name:
                    continue

                discovered += 1

                if full_name in self._repos:
                    existing = self._repos[full_name]
                    existing.stars = raw.get("stargazers_count", existing.stars)
                    existing.forks = raw.get("forks_count", existing.forks)
                    existing.open_issues = raw.get("open_issues_count", existing.open_issues)
                    existing.last_pushed = raw.get("pushed_at", existing.last_pushed)
                    existing.updated_at = raw.get("updated_at", existing.updated_at)
                    existing.archived = raw.get("archived", False)
                    existing.language = raw.get("language") or existing.language
                    existing.size_kb = raw.get("size", existing.size_kb)
                else:
                    self._repos[full_name] = RepoEntry.from_github_api(raw, account)
                    new_repos += 1

        self._last_refresh = now
        self._save()

        stats = self.get_stats()

        try:
            from orchestration.event_bus import event_bus
            event_bus.emit("repo_inventory_refreshed",
                           accounts=accounts, discovered=discovered,
                           new_repos=new_repos, total=stats["total"],
                           errors=errors)
        except ImportError:
            pass

        return {
            "status": "ok",
            "discovered": discovered,
            "new_repos": new_repos,
            "total": stats["total"],
            "accounts": accounts,
            "errors": errors,
        }

    def refresh(self) -> Dict:
        """Re-discover all repos, merging with existing state."""
        return self.discover()

    # ── Query ───────────────────────────────────────────────────────

    def get(self, full_name: str) -> Optional[RepoEntry]:
        return self._repos.get(full_name)

    def get_by_account(self, account: str) -> List[RepoEntry]:
        return [r for r in self._repos.values() if r.owner == account]

    def get_by_language(self, language: str) -> List[RepoEntry]:
        lang = language.lower()
        return [r for r in self._repos.values()
                if r.language and r.language.lower() == lang]

    def get_by_topic(self, topic: str) -> List[RepoEntry]:
        return [r for r in self._repos.values() if topic in r.topics]

    def list_all(self) -> List[RepoEntry]:
        return sorted(self._repos.values(),
                      key=lambda x: (-x.stars, x.full_name))

    def list_active(self) -> List[RepoEntry]:
        return [r for r in self._repos.values()
                if not r.archived and not r.fork]

    def list_high_value(self, min_stars: int = 1) -> List[RepoEntry]:
        return [r for r in self.list_active() if r.stars >= min_stars]

    def list_needing_audit(self) -> List[RepoEntry]:
        return [r for r in self.list_active() if not r.audited]

    def list_cloned(self) -> List[RepoEntry]:
        return [r for r in self._repos.values() if r.is_cloned]

    def search(self, query: str) -> List[RepoEntry]:
        q = query.lower()
        return [r for r in self._repos.values()
                if q in r.name.lower() or q in r.description.lower()
                or any(q in t.lower() for t in r.topics)]

    def get_stats(self) -> Dict:
        repos = list(self._repos.values())
        active = [r for r in repos if not r.archived]
        cloned = [r for r in repos if r.is_cloned]
        audited = [r for r in repos if r.audited]
        queued = [r for r in repos if r.in_swarm_queue]

        languages: Dict[str, int] = {}
        for r in active:
            lang = r.language or "unknown"
            languages[lang] = languages.get(lang, 0) + 1

        by_account: Dict[str, int] = {}
        for r in repos:
            by_account[r.owner] = by_account.get(r.owner, 0) + 1

        return {
            "total": len(repos),
            "active": len(active),
            "archived": len(repos) - len(active),
            "private": sum(1 for r in repos if r.private),
            "forks": sum(1 for r in repos if r.fork),
            "cloned": len(cloned),
            "audited": len(audited),
            "in_swarm_queue": len(queued),
            "by_account": by_account,
            "by_language": dict(
                sorted(languages.items(), key=lambda x: -x[1])
            ),
            "total_stars": sum(r.stars for r in repos),
            "total_forks": sum(r.forks for r in repos),
            "last_refresh": self._last_refresh,
            "pages_deployed": sum(1 for r in repos if r.has_pages),
        }

    # ── Swarm integration ───────────────────────────────────────────

    def auto_queue(self, max_per_run: int = 5) -> Dict:
        """Feed un-audited repos to the swarm worker for processing.

        Skips archived repos, forks, and repos already in the queue.
        Prioritizes by recency (most recently pushed first).
        """
        candidates = [
            r for r in self.list_active()
            if not r.audited and not r.in_swarm_queue
        ]
        candidates.sort(key=lambda x: x.last_pushed, reverse=True)

        if not candidates:
            return {"status": "idle", "reason": "all_repos_audited"}

        try:
            from orchestration.swarm_worker import get_swarm_worker
            worker = get_swarm_worker()
        except ImportError:
            return {"status": "error", "reason": "swarm_worker_not_loaded"}

        queued = 0
        for entry in candidates[:max_per_run]:
            task_id = worker.add_to_queue(
                owner=entry.owner,
                repo=entry.name,
                branch=entry.default_branch,
                instruction=f"Auto-audit: {entry.description[:200]}" if entry.description else "",
            )
            entry.in_swarm_queue = True
            entry.swarm_task_id = task_id
            queued += 1

        if queued:
            self._save()

        return {
            "status": "ok",
            "queued": queued,
            "remaining": len(candidates) - queued,
            "candidates": [f"{r.owner}/{r.name}" for r in candidates[:max_per_run]],
        }

    def mark_audited(self, full_name: str, score: int,
                     task_id: str = "", notes: str = "") -> bool:
        """Mark a repo as audited after swarm worker completes."""
        entry = self._repos.get(full_name)
        if not entry:
            return False
        entry.audited = True
        entry.last_audit = datetime.now(timezone.utc).isoformat()
        entry.audit_score = score
        entry.in_swarm_queue = False
        if task_id:
            entry.swarm_task_id = task_id
        if notes:
            entry.notes = notes
        self._save()
        return True

    def mark_cloned(self, full_name: str, local_path: str) -> bool:
        entry = self._repos.get(full_name)
        if not entry:
            return False
        entry.is_cloned = True
        entry.local_path = local_path
        self._save()
        return True

    # ── Admin ───────────────────────────────────────────────────────

    def set_accounts(self, accounts: List[str]) -> None:
        self._accounts = list(accounts)

    def add_note(self, full_name: str, note: str) -> bool:
        entry = self._repos.get(full_name)
        if not entry:
            return False
        entry.notes = note
        self._save()
        return True

    def summary(self) -> str:
        stats = self.get_stats()
        lines = [
            f"Repo Inventory — {stats['last_refresh'] or 'never refreshed'}",
            f"  Total: {stats['total']} repos across {len(stats['by_account'])} accounts",
            f"  Active: {stats['active']} | Archived: {stats['archived']}",
            f"  Private: {stats['private']} | Forks: {stats['forks']}",
            f"  Stars: {stats['total_stars']} | Forks: {stats['total_forks']}",
            f"  Cloned: {stats['cloned']} | Audited: {stats['audited']} | Queued: {stats['in_swarm_queue']}",
            f"  Pages deployed: {stats['pages_deployed']}",
        ]
        if stats["by_account"]:
            lines.append(f"  By account: {stats['by_account']}")
        if stats["by_language"]:
            lines.append(f"  Top languages: {dict(list(stats['by_language'].items())[:8])}")
        return "\n".join(lines)


# ── Singleton ───────────────────────────────────────────────────────────

_INVENTORY: Optional[RepoInventory] = None


def get_repo_inventory() -> RepoInventory:
    global _INVENTORY
    if _INVENTORY is None:
        _INVENTORY = RepoInventory()
    return _INVENTORY


def reset_repo_inventory() -> RepoInventory:
    global _INVENTORY
    _INVENTORY = RepoInventory()
    return _INVENTORY
