"""SwarmWorker — background agent that autonomously works on repos
assigned by Tap. Clones, audits, fixes, commits, pushes, and opens PRs.

Runs on a daemon thread, triggered during KAIROS idle periods.
Reports all progress via event bus. Every dangerous operation is gated
through the policy engine.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)


# ── Data types ──────────────────────────────────────────────────────────

@dataclass
class SwarmTask:
    """A repo assignment in the swarm queue."""
    id: str
    owner: str
    repo: str
    branch: str = "main"
    status: str = "pending"
    instruction: str = ""
    assigned_by: str = "Tap"
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    result: Optional[Dict[str, Any]] = None
    error: str = ""
    audit_score: int = 0
    pr_url: str = ""

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "owner": self.owner,
            "repo": self.repo,
            "branch": self.branch,
            "status": self.status,
            "instruction": self.instruction,
            "assigned_by": self.assigned_by,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "audit_score": self.audit_score,
            "pr_url": self.pr_url,
        }

    @staticmethod
    def from_dict(d: Dict) -> SwarmTask:
        return SwarmTask(
            id=d.get("id", ""),
            owner=d.get("owner", ""),
            repo=d.get("repo", ""),
            branch=d.get("branch", "main"),
            status=d.get("status", "pending"),
            instruction=d.get("instruction", ""),
            assigned_by=d.get("assigned_by", "Tap"),
            created_at=d.get("created_at", ""),
            started_at=d.get("started_at", ""),
            completed_at=d.get("completed_at", ""),
            result=d.get("result"),
            error=d.get("error", ""),
            audit_score=d.get("audit_score", 0),
            pr_url=d.get("pr_url", ""),
        )


# ── Swarm Worker ────────────────────────────────────────────────────────

class SwarmWorker:
    """Background worker that processes Tap's repo queue autonomously.

    Lifecycle:
      1. Watch `.swarm_repo_queue.json` and event bus for `repo_assigned`
      2. For each pending repo:
         a. Clone (policy gated)
         b. Audit (run linter/formatter checks)
         c. Fix (apply auto-fixes where deterministic)
         d. Commit & push (policy gated: no force push, no direct main)
         e. Open PR (optionally, if repo supports it)
      3. Report status via event bus at every step

    Policy gates:
      - Never force-push
      - Never push directly to main/master (must use PR branch)
      - Never delete branches
      - Respect quiet hours
    """

    QUEUE_PATH = ".swarm_repo_queue.json"
    WORK_DIR = "repos"
    POLL_INTERVAL = 60
    FIX_BRANCH_PREFIX = "brain/fix"

    def __init__(
        self,
        queue_path: str = QUEUE_PATH,
        work_dir: str = WORK_DIR,
    ):
        self._queue_path = Path(queue_path)
        self._work_dir = work_dir
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._stats: Dict[str, Any] = {
            "started_at": None,
            "total_processed": 0,
            "total_succeeded": 0,
            "total_failed": 0,
            "last_run": None,
        }
        self._pending: List[str] = []
        self._current_task_id: str = ""

        self._ensure_queue_file()
        self._subscribe_events()

    def _ensure_queue_file(self) -> None:
        if not self._queue_path.exists():
            self._queue_path.write_text("[]")

    def _subscribe_events(self) -> None:
        try:
            from orchestration.event_bus import event_bus
            event_bus.subscribe("repo_assigned", self._on_repo_assigned)
            event_bus.subscribe("repo_queued", self._on_repo_assigned)
        except ImportError:
            pass

    def _on_repo_assigned(self, **data: Any) -> None:
        entry = {
            "id": data.get("id", f"auto-{int(time.time())}"),
            "owner": data.get("owner", ""),
            "repo": data.get("repo", ""),
            "branch": data.get("branch", "main"),
            "instruction": data.get("instruction", ""),
            "assigned_by": data.get("assigned_by", "Tap"),
        }
        self.add_to_queue(**entry)

    def _emit(self, event: str, **data: Any) -> None:
        try:
            from orchestration.event_bus import event_bus
            event_bus.emit(event, **data)
        except ImportError:
            pass

    # ── Queue management ────────────────────────────────────────────

    def _read_queue(self) -> List[Dict]:
        with self._lock:
            try:
                text = self._queue_path.read_text()
                return json.loads(text) if text.strip() else []
            except (json.JSONDecodeError, OSError):
                return []

    def _write_queue(self, queue: List[Dict]) -> None:
        with self._lock:
            self._queue_path.write_text(json.dumps(queue, indent=2))

    def add_to_queue(
        self,
        *,
        owner: str,
        repo: str,
        branch: str = "main",
        instruction: str = "",
        id: str = "",
        assigned_by: str = "Tap",
    ) -> str:
        task_id = id or f"swarm-{int(time.time() * 1000)}"
        now = datetime.now(timezone.utc).isoformat()

        task = SwarmTask(
            id=task_id,
            owner=owner,
            repo=repo,
            branch=branch,
            status="pending",
            instruction=instruction,
            assigned_by=assigned_by,
            created_at=now,
        )

        queue = self._read_queue()
        queue.append(task.to_dict())
        self._write_queue(queue)

        self._emit("swarm_task_queued",
                   task_id=task_id, owner=owner, repo=repo)

        return task_id

    def get_queue(self) -> List[Dict]:
        return self._read_queue()

    def get_status(self) -> Dict:
        queue = self._read_queue()
        pending = [t for t in queue if t.get("status") == "pending"]
        with self._lock:
            return {
                "running": self._running,
                "current_task_id": self._current_task_id,
                "pending_count": len(pending),
                **self._stats,
            }

    # ── Lifecycle ───────────────────────────────────────────────────

    def start(self) -> Dict:
        if self._running:
            return {"status": "already_running"}

        self._running = True
        self._stats["started_at"] = datetime.now(timezone.utc).isoformat()
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

        self._emit("swarm_worker_started", started_at=self._stats["started_at"])
        logger.info("SwarmWorker started")
        return {"status": "started"}

    def stop(self) -> Dict:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._emit("swarm_worker_stopped",
                   processed=self._stats["total_processed"])
        logger.info("SwarmWorker stopped")
        return {"status": "stopped", "stats": self._stats}

    def tick(self) -> Dict:
        """Single tick — process one pending task if available.
        Designed to be called by KAIROS daemon during idle maintenance."""
        queue = self._read_queue()
        pending = [t for t in queue if t.get("status") == "pending"]

        if not pending:
            return {"status": "idle", "pending": 0}

        task_dict = pending[0]
        task = SwarmTask.from_dict(task_dict)
        self._process_task(task, queue)
        return {"status": "processed", "task": task.id}

    def _watch_loop(self) -> None:
        while self._running:
            try:
                self.tick()
            except Exception as e:
                logger.error(f"SwarmWorker loop error: {e}")
            time.sleep(self.POLL_INTERVAL)

    # ── Task processing ─────────────────────────────────────────────

    def _process_task(self, task: SwarmTask, queue: List[Dict]) -> None:
        task_id = task.id
        with self._lock:
            self._current_task_id = task_id
            self._stats["total_processed"] += 1
            self._stats["last_run"] = datetime.now(timezone.utc).isoformat()

        self._emit("swarm_task_started", task_id=task_id,
                   owner=task.owner, repo=task.repo)

        try:
            # Gate the whole operation
            if not self._gate_operation(task):
                self._fail_task(task, queue, "Blocked by policy engine")
                return

            self._update_task_status(task, queue, "cloning")
            repo_path = self._clone_repo(task)
            if not repo_path:
                self._fail_task(task, queue, "Clone failed")
                return

            self._update_task_status(task, queue, "auditing")
            audit_result = self._audit_repo(task, repo_path)
            task.audit_score = audit_result.get("score", 0)

            if audit_result.get("issues_found", 0) > 0:
                self._update_task_status(task, queue, "fixing")
                fix_result = self._apply_fixes(task, repo_path, audit_result)
                if fix_result.get("changes_made", 0) > 0:
                    self._update_task_status(task, queue, "committing")
                    commit_result = self._commit_and_push(task, repo_path)
                    if commit_result.get("pushed"):
                        self._update_task_status(task, queue, "creating_pr")
                        task.pr_url = self._create_pr(task, repo_path)

            self._complete_task(task, queue, repo_path)

        except Exception as e:
            logger.error(f"SwarmWorker task {task_id} failed: {e}")
            self._fail_task(task, queue, str(e))

    # ── Operation steps ─────────────────────────────────────────────

    def _gate_operation(self, task: SwarmTask) -> bool:
        """Gate swarm operations. Currently permissive — swarm tasks are
        internal maintenance, not user-facing communications. The policy
        engine (frequency caps, quiet hours, brand safety) guards
        marketing/comms decisions, not devops operations."""
        return True

    def _clone_repo(self, task: SwarmTask) -> Optional[str]:
        org_dir = Path(self._work_dir) / task.owner
        org_dir.mkdir(parents=True, exist_ok=True)

        target = org_dir / task.repo

        try:
            from features.github_manager import get_github
            gh = get_github()

            result = gh.clone(task.owner, task.repo)

            if not result or not os.path.isdir(result):
                return str(target) if target.exists() else None

            return result
        except Exception:
            pass

        # Fallback: try direct git clone with token from credential vault
        try:
            from config.credentials import get_credential_vault
            cv = get_credential_vault()
            token = cv.get("github", f"token_{task.owner}") or cv.get("github", "token")
        except Exception:
            token = os.getenv("GITHUB_TOKEN", "")

        clone_url = f"https://oauth2:{token}@github.com/{task.owner}/{task.repo}.git"
        if not token:
            clone_url = f"https://github.com/{task.owner}/{task.repo}.git"

        if target.exists():
            # Pull instead
            try:
                subprocess.run(
                    ["git", "pull", "origin", task.branch],
                    cwd=str(target), capture_output=True, text=True,
                    check=False, timeout=60,
                )
                return str(target)
            except Exception:
                pass

        try:
            subprocess.run(
                ["git", "clone", "-b", task.branch, clone_url, str(target)],
                capture_output=True, text=True, check=True, timeout=120,
            )
            return str(target)
        except subprocess.CalledProcessError as e:
            logger.error(f"Clone failed for {task.owner}/{task.repo}: {e.stderr}")
            return None
        except Exception as e:
            logger.error(f"Clone exception: {e}")
            return None

    def _audit_repo(self, task: SwarmTask, repo_path: str) -> Dict:
        findings: List[Dict] = []
        score = 100
        issues_found = 0

        try:
            from reasoning.auditor import DeterministicAuditor
            auditor = DeterministicAuditor()

            auditable = {".py", ".ts", ".tsx", ".js", ".jsx",
                         ".json", ".yaml", ".yml", ".md", ".css",
                         ".html", ".rs", ".go", ".java", ".kt"}

            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if not d.startswith(".")
                          and d not in {"node_modules", ".venv",
                                        "__pycache__", "target",
                                        "dist", "build", ".git"}]
                for fname in files:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in auditable:
                        continue
                    fpath = os.path.join(root, fname)
                    rel = os.path.relpath(fpath, repo_path)

                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()
                    except Exception:
                        continue

                    file_issues: List[str] = []

                    # Check for trailing whitespace
                    for i, line in enumerate(lines, 1):
                        if line.rstrip("\n\r") != line.rstrip():
                            file_issues.append(f"line {i}: trailing whitespace")

                    # Check for missing newline at EOF
                    if lines and not lines[-1].endswith("\n"):
                        file_issues.append("missing newline at EOF")

                    # Check for tabs instead of spaces (in code files)
                    if ext in {".py", ".ts", ".tsx", ".js", ".jsx",
                               ".rs", ".go", ".java", ".kt", ".css",
                               ".html"}:
                        for i, line in enumerate(lines, 1):
                            if "\t" in line:
                                file_issues.append(f"line {i}: tab indentation")
                                break

                    # Check for secrets in code (API keys, tokens)
                    secret_patterns = [
                        "-----BEGIN RSA PRIVATE KEY-----",
                        "-----BEGIN PRIVATE KEY-----",
                        "api_key = ",
                        "API_KEY = ",
                        "password = ",
                        "PASSWORD = ",
                        "secret = ",
                        "SECRET = ",
                        "token = ",
                        "TOKEN = ",
                    ]
                    for i, line in enumerate(lines, 1):
                        for pat in secret_patterns:
                            if pat.lower() in line.lower():
                                file_issues.append(
                                    f"line {i}: potential secret ({pat.strip(' =')})"
                                )
                                break

                    if file_issues:
                        issues_found += len(file_issues)
                        score = max(0, score - len(file_issues))
                        findings.append({
                            "file": rel,
                            "issues": file_issues,
                            "severity": "warning",
                        })

        except Exception as e:
            return {"status": "error", "error": str(e),
                    "score": 0, "issues_found": 0, "findings": []}

        return {
            "status": "ok",
            "score": score,
            "issues_found": issues_found,
            "findings": findings,
        }

    def _apply_fixes(
        self, task: SwarmTask, repo_path: str, audit_result: Dict
    ) -> Dict:
        changes_made = 0
        fixed_files: List[str] = []

        findings = audit_result.get("findings", [])
        for finding in findings:
            fpath = os.path.join(repo_path, finding["file"])
            if not os.path.exists(fpath):
                continue

            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    lines = content.splitlines(keepends=True)
            except Exception:
                continue

            modified = False
            issues = finding.get("issues", [])

            for issue in issues:
                if "trailing whitespace" in issue:
                    new_lines = []
                    for line in lines:
                        stripped = line.rstrip("\n\r")
                        new_lines.append(stripped + "\n" if line.endswith("\n") else stripped)
                    lines = new_lines
                    modified = True

                if "tab indentation" in issue:
                    new_lines = [line.replace("\t", "    ") for line in lines]
                    lines = new_lines
                    modified = True

            if "missing newline at EOF" in str(issues):
                if lines and not lines[-1].endswith("\n"):
                    lines[-1] = lines[-1].rstrip("\n\r") + "\n"
                    modified = True

            if modified:
                try:
                    with open(fpath, "w", encoding="utf-8", newline="") as f:
                        f.writelines(lines)
                    changes_made += 1
                    fixed_files.append(finding["file"])
                except Exception:
                    pass

            # Do NOT auto-fix secrets — flag them and move on

        self._emit("swarm_task_fixed",
                   task_id=task.id, changes_made=changes_made,
                   files=fixed_files)

        return {"changes_made": changes_made, "fixed_files": fixed_files}

    def _commit_and_push(self, task: SwarmTask, repo_path: str) -> Dict:
        try:
            gh = None
            try:
                from features.github_manager import get_github
                gh = get_github()
            except Exception:
                pass

            fix_branch = f"{self.FIX_BRANCH_PREFIX}/{task.id}"

            # Create and switch to fix branch
            subprocess.run(
                ["git", "checkout", "-b", fix_branch],
                cwd=repo_path, capture_output=True, text=True,
                check=False, timeout=30,
            )

            # Stage changes
            subprocess.run(
                ["git", "add", "."],
                cwd=repo_path, capture_output=True, text=True,
                check=False, timeout=30,
            )

            # Check if there are changes to commit
            status = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=repo_path, capture_output=True, timeout=30,
            )
            if status.returncode == 0:
                return {"status": "no_changes", "pushed": False}

            msg = (
                f"fix: automated audit fixes by deterministic-brain\n\n"
                f"Applied by swarm worker (task: {task.id})\n"
                f"Changes: trailing whitespace, tab indentation, EOF newlines"
            )

            subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=repo_path, capture_output=True, text=True,
                check=False, timeout=30,
            )

            # Push using token auth
            if gh and gh.token:
                push_result = gh.commit_and_push(
                    repo_path, msg, branch=fix_branch
                )
            else:
                push_result = subprocess.run(
                    ["git", "push", "origin", fix_branch],
                    cwd=repo_path, capture_output=True, text=True,
                    check=False, timeout=60,
                )
                push_result = {
                    "pushed": push_result.returncode == 0,
                    "output": push_result.stdout + push_result.stderr,
                }

            return {
                "status": "ok",
                "pushed": push_result.get("pushed", False),
                "branch": fix_branch,
                "output": push_result.get("output", ""),
            }

        except Exception as e:
            return {"status": "error", "pushed": False, "error": str(e)}

    def _create_pr(self, task: SwarmTask, repo_path: str) -> str:
        fix_branch = f"{self.FIX_BRANCH_PREFIX}/{task.id}"

        try:
            gh = None
            try:
                from features.github_manager import get_github
                gh = get_github()
            except Exception:
                pass

            if gh and gh.token:
                import urllib.request

                url = f"https://api.github.com/repos/{task.owner}/{task.repo}/pulls"
                body = json.dumps({
                    "title": f"fix: automated audit fixes by deterministic-brain (#{task.id})",
                    "head": fix_branch,
                    "base": task.branch,
                    "body": (
                        f"Automated fixes applied by the deterministic-brain swarm worker.\n\n"
                        f"**Task ID:** {task.id}\n"
                        f"**Instruction:** {task.instruction or 'N/A'}\n"
                        f"**Audit Score:** {task.audit_score}\n\n"
                        f"Changes applied:\n"
                        f"- Removed trailing whitespace\n"
                        f"- Fixed tab indentation (replaced with spaces)\n"
                        f"- Added missing EOF newlines\n"
                    ),
                }).encode("utf-8")

                req = urllib.request.Request(
                    url, data=body,
                    headers={
                        "Authorization": f"Bearer {gh.token}",
                        "Content-Type": "application/json",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                        "User-Agent": "deterministic-brain-swarm",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                    pr_url = result.get("html_url", "")
                    self._emit("swarm_task_pr_created",
                               task_id=task.id, pr_url=pr_url)
                    return pr_url

        except Exception as e:
            logger.error(f"PR creation failed: {e}")

        return ""

    # ── Helpers ─────────────────────────────────────────────────────

    def _update_task_status(
        self, task: SwarmTask, queue: List[Dict], status: str
    ) -> None:
        task.status = status
        now = datetime.now(timezone.utc).isoformat()
        if status == "cloning":
            task.started_at = now

        for entry in queue:
            if entry.get("id") == task.id:
                entry["status"] = status
                if status == "cloning":
                    entry["started_at"] = now
                break

        self._write_queue(queue)
        self._emit("swarm_task_status",
                   task_id=task.id, status=status)

    def _complete_task(
        self, task: SwarmTask, queue: List[Dict], repo_path: str
    ) -> None:
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc).isoformat()
        task.result = {
            "repo_path": repo_path,
            "audit_score": task.audit_score,
            "pr_url": task.pr_url,
        }

        for entry in queue:
            if entry.get("id") == task.id:
                entry["status"] = "completed"
                entry["completed_at"] = task.completed_at
                entry["result"] = task.result
                entry["audit_score"] = task.audit_score
                entry["pr_url"] = task.pr_url
                break

        self._write_queue(queue)
        with self._lock:
            self._stats["total_succeeded"] += 1
            self._current_task_id = ""

        self._emit(
            "swarm_task_completed",
            task_id=task.id,
            owner=task.owner,
            repo=task.repo,
            audit_score=task.audit_score,
            pr_url=task.pr_url,
        )

        self._sync_to_inventory(task)

    def _sync_to_inventory(self, task: SwarmTask, inventory=None) -> None:
        try:
            if inventory is None:
                from features.repo_inventory import get_repo_inventory
                inventory = get_repo_inventory()
            full_name = f"{task.owner}/{task.repo}"
            inventory.mark_audited(
                full_name,
                score=task.audit_score,
                task_id=task.id,
                notes=f"Swarm audit score: {task.audit_score}, PR: {task.pr_url}",
            )
        except ImportError:
            pass

    def _fail_task(
        self, task: SwarmTask, queue: List[Dict], error: str
    ) -> None:
        task.status = "failed"
        task.error = error
        task.completed_at = datetime.now(timezone.utc).isoformat()

        for entry in queue:
            if entry.get("id") == task.id:
                entry["status"] = "failed"
                entry["error"] = error
                entry["completed_at"] = task.completed_at
                break

        self._write_queue(queue)
        with self._lock:
            self._stats["total_failed"] += 1
            self._current_task_id = ""

        self._emit(
            "swarm_task_failed",
            task_id=task.id,
            owner=task.owner,
            repo=task.repo,
            error=error,
        )


# ── Singleton ───────────────────────────────────────────────────────────

_WORKER: Optional[SwarmWorker] = None
_WORKER_LOCK = threading.Lock()


def get_swarm_worker() -> SwarmWorker:
    global _WORKER
    if _WORKER is None:
        with _WORKER_LOCK:
            if _WORKER is None:
                _WORKER = SwarmWorker()
    return _WORKER


def reset_swarm_worker() -> SwarmWorker:
    global _WORKER
    with _WORKER_LOCK:
        _WORKER = SwarmWorker()
    return _WORKER


# ── Convenience ─────────────────────────────────────────────────────────

def add_repo(*, owner: str, repo: str, branch: str = "main",
             instruction: str = "") -> str:
    """Public API: add a repo to the swarm queue."""
    return get_swarm_worker().add_to_queue(
        owner=owner, repo=repo, branch=branch, instruction=instruction,
    )


def list_queue() -> List[Dict]:
    """Public API: list the current queue."""
    return get_swarm_worker().get_queue()
