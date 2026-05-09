"""Task Planner — scheduling, timeline, recurring tasks, planning board.

Provides: task queue, cron-like scheduling, dependency chains,
milestone tracking, and autonomous task generation from soul goals.
"""
from __future__ import annotations
import json
import os
import time
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class PlannedTask:
    id: str
    title: str
    query: str
    schedule: str = ""            # cron expression or "now"
    recurrence: str = ""          # "daily" | "weekly" | "monthly" | ""
    depends_on: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    priority: int = 0             # higher = more important
    status: str = "pending"       # pending | running | done | failed
    created_at: float = field(default_factory=time.time)
    last_run: float = 0
    next_run: float = 0
    run_count: int = 0
    max_runs: int = 0             # 0 = unlimited
    result: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "title": self.title, "query": self.query,
            "schedule": self.schedule, "recurrence": self.recurrence,
            "depends_on": self.depends_on, "tags": self.tags,
            "priority": self.priority, "status": self.status,
            "created_at": self.created_at, "last_run": self.last_run,
            "next_run": self.next_run, "run_count": self.run_count,
        }


class TaskPlanner:
    def __init__(self, db_path: str = "planner_tasks.json"):
        self.db_path = db_path
        self.tasks: Dict[str, PlannedTask] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path) as f:
                    data = json.load(f)
                for item in data:
                    t = PlannedTask(**item)
                    self.tasks[t.id] = t
            except Exception:
                pass

    def _save(self):
        with open(self.db_path, "w") as f:
            json.dump([t.to_dict() for t in self.tasks.values()], f, indent=2)

    def add(self, title: str, query: str, schedule: str = "now",
            depends_on: List[str] = None, tags: List[str] = None,
            recur: str = "", priority: int = 0, max_runs: int = 0) -> PlannedTask:
        tid = hashlib.sha256((title + query + str(time.time())).encode()).hexdigest()[:12]
        t = PlannedTask(
            id=tid, title=title, query=query, schedule=schedule,
            recurrence=recur, depends_on=depends_on or [],
            tags=tags or [], priority=priority, max_runs=max_runs,
        )
        t.next_run = self._parse_schedule(schedule)
        self.tasks[tid] = t
        self._save()
        return t

    def _parse_schedule(self, sched: str) -> float:
        if sched == "now":
            return time.time()
        if sched == "hourly":
            return time.time() + 3600
        if sched == "daily":
            tomorrow = datetime.now() + timedelta(days=1)
            return tomorrow.replace(hour=3, minute=0, second=0).timestamp()
        if sched == "weekly":
            next_monday = datetime.now() + timedelta(days=(7 - datetime.now().weekday()))
            return next_monday.replace(hour=3, minute=0, second=0).timestamp()
        try:
            parts = sched.split(":")
            if len(parts) == 2:
                target = datetime.now().replace(hour=int(parts[0]), minute=int(parts[1]), second=0)
                if target.timestamp() < time.time():
                    target += timedelta(days=1)
                return target.timestamp()
        except Exception:
            pass
        return time.time() + 300

    def get_due(self) -> List[PlannedTask]:
        now = time.time()
        due = []
        for t in self.tasks.values():
            if t.status not in ("pending",):
                continue
            if t.max_runs > 0 and t.run_count >= t.max_runs:
                continue
            if any(self.tasks[d].status != "done" for d in t.depends_on if d in self.tasks):
                continue
            if t.next_run <= now:
                due.append(t)
        return sorted(due, key=lambda x: -x.priority)

    def mark_running(self, task_id: str):
        if task_id in self.tasks:
            self.tasks[task_id].status = "running"
            self._save()

    def mark_done(self, task_id: str, result: Dict = None):
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.status = "done"
            t.run_count += 1
            t.last_run = time.time()
            t.result = result or {}
            if t.recurrence:
                if t.recurrence == "daily":
                    t.next_run = time.time() + 86400
                elif t.recurrence == "weekly":
                    t.next_run = time.time() + 604800
                elif t.recurrence == "monthly":
                    t.next_run = time.time() + 2592000
                else:
                    t.next_run = time.time() + 3600
            t.status = "pending"
            self._save()

    def mark_failed(self, task_id: str, error: str = ""):
        if task_id in self.tasks:
            t = self.tasks[task_id]
            t.status = "failed"
            t.result = {"error": error}
            t.next_run = time.time() + 300
            self._save()

    def delete(self, task_id: str) -> bool:
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save()
            return True
        return False

    def list_all(self) -> List[PlannedTask]:
        return sorted(self.tasks.values(), key=lambda x: -x.priority)

    def generate_from_soul(self, soul_goals: List[str]) -> List[PlannedTask]:
        """Auto-generate tasks from soul agenda goals."""
        new_tasks = []
        for goal in soul_goals:
            tid = hashlib.sha256(goal.encode()).hexdigest()[:12]
            if tid in self.tasks:
                continue
            t = PlannedTask(
                id=tid, title=goal, query=f"work toward: {goal}",
                schedule="daily", priority=5, tags=["soul", "autonomous"],
            )
            t.next_run = time.time() + 300
            self.tasks[tid] = t
            new_tasks.append(t)
        self._save()
        return new_tasks

    def get_timeline(self, hours: int = 24) -> List[Dict]:
        """Return a timeline of upcoming tasks."""
        now = time.time()
        window = now + hours * 3600
        upcoming = [t for t in self.tasks.values()
                    if t.next_run and t.next_run <= window and t.status == "pending"]
        return sorted([
            {
                "id": t.id, "title": t.title, "time": t.next_run,
                "priority": t.priority, "recurrence": t.recurrence,
            }
            for t in upcoming
        ], key=lambda x: x["time"])


_PLANNER: Optional[TaskPlanner] = None


def get_planner() -> TaskPlanner:
    global _PLANNER
    if _PLANNER is None:
        _PLANNER = TaskPlanner()
    return _PLANNER
