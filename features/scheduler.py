"""Scheduler — APScheduler-based task scheduling for deterministic brain.

Allows scheduling:
- Cron-based tasks ("0 9 * * *" = daily at 9am)
- Interval-based tasks (every N seconds/minutes/hours)
- One-time delayed tasks
- Notification on completion (email, webhook)

Usage:
    from features.scheduler import schedule_task, get_scheduler
    
    # Schedule a periodic task with notification
    schedule_task(
        name="daily-audit",
        skill="audit-repo",
        cron_expr="0 9 * * *",
        inputs={"repo_path": "./my-project"},
        notify_email="you@example.com",
        notify_webhook="https://your-tunnel.cloudflare.net/notify"
    )
    
    # Get scheduler state
    scheduler = get_scheduler()
    print(scheduler.list_tasks())
"""
from __future__ import annotations
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed. Install with: pip install apscheduler")


@dataclass
class TaskDefinition:
    """Definition of a schedulable task."""
    name: str
    skill: str
    trigger_type: str  # "cron", "interval"
    cron_expr: Optional[str] = None
    interval_seconds: Optional[int] = None
    inputs: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    notify_email: Optional[str] = None
    notify_webhook: Optional[str] = None


@dataclass
class TaskResult:
    """Result of a task execution."""
    name: str
    skill: str
    started_at: datetime
    finished_at: datetime
    status: str  # "success", "error"
    output: Any = None
    error: Optional[str] = None


class NotificationService:
    """Handles email and webhook notifications."""
    
    def __init__(self):
        self._config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load notification config from environment or file."""
        config = {
            "smtp_host": os.getenv("SMTP_HOST", ""),
            "smtp_port": int(os.getenv("SMTP_PORT", "587")),
            "smtp_user": os.getenv("SMTP_USER", ""),
            "smtp_password": os.getenv("SMTP_PASSWORD", ""),
            "from_email": os.getenv("FROM_EMAIL", "noreply@deterministic-brain.local"),
        }
        
        config_path = os.path.expanduser("~/.deterministic-brain/notifications.json")
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    config.update(json.load(f))
            except:
                pass
        
        return config
    
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send email notification."""
        if not self._config.get("smtp_host"):
            logger.debug("SMTP not configured, skipping email")
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            msg = MIMEMultipart()
            msg["From"] = self._config["from_email"]
            msg["To"] = to
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            
            with smtplib.SMTP(
                self._config["smtp_host"],
                self._config["smtp_port"]
            ) as server:
                server.starttls()
                if self._config.get("smtp_user"):
                    server.login(
                        self._config["smtp_user"],
                        self._config["smtp_password"]
                    )
                server.send_message(msg)
            
            logger.info(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def send_webhook(self, url: str, payload: Dict) -> bool:
        """Send webhook notification to phone app."""
        if not url:
            return False
        
        try:
            import requests
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code < 400:
                logger.info(f"Webhook sent to {url}")
                return True
            else:
                logger.warning(f"Webhook failed: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
            return False
    
    def notify(self, task_def: TaskDefinition, result: TaskResult) -> None:
        """Send notifications based on task config."""
        summary = f"[{result.status.upper()}] {task_def.name}"
        
        if task_def.notify_email:
            body = f"""Task: {task_def.name}
Skill: {task_def.skill}
Status: {result.status}
Started: {result.started_at.isoformat()}
Finished: {result.finished_at.isoformat()}
"""
            if result.error:
                body += f"Error: {result.error}\n"
            else:
                body += f"Output: {str(result.output)[:500]}\n"
            
            self.send_email(task_def.notify_email, summary, body)
        
        if task_def.notify_webhook:
            self.send_webhook(task_def.notify_webhook, {
                "task": task_def.name,
                "skill": task_def.skill,
                "status": result.status,
                "started_at": result.started_at.isoformat(),
                "finished_at": result.finished_at.isoformat(),
                "error": result.error,
            })


class Scheduler:
    """APScheduler-based task scheduler with notifications."""
    
    def __init__(self, storage_path: str = ".scheduler_tasks.json"):
        self.storage_path = storage_path
        self._tasks: Dict[str, TaskDefinition] = {}
        self._results: Dict[str, List[TaskResult]] = {}
        self._aps_scheduler: Optional[Any] = None
        self._notifications = NotificationService()
        
        if APSCHEDULER_AVAILABLE:
            self._aps_scheduler = BackgroundScheduler()
        
        self._executor_callback: Optional[Callable] = None
        self._load()
    
    def _load(self) -> None:
        """Load tasks from disk."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path) as f:
                    data = json.load(f)
                    for name, task_data in data.items():
                        self._tasks[name] = TaskDefinition(
                            name=task_data["name"],
                            skill=task_data["skill"],
                            trigger_type=task_data["trigger_type"],
                            cron_expr=task_data.get("cron_expr"),
                            interval_seconds=task_data.get("interval_seconds"),
                            inputs=task_data.get("inputs", {}),
                            enabled=task_data.get("enabled", True),
                            notify_email=task_data.get("notify_email"),
                            notify_webhook=task_data.get("notify_webhook"),
                        )
                logger.info(f"Loaded {len(self._tasks)} scheduled tasks")
            except Exception as e:
                logger.warning(f"Failed to load tasks: {e}")
    
    def _save(self) -> None:
        """Save tasks to disk."""
        data = {}
        for name, task in self._tasks.items():
            data[name] = {
                "name": task.name,
                "skill": task.skill,
                "trigger_type": task.trigger_type,
                "cron_expr": task.cron_expr,
                "interval_seconds": task.interval_seconds,
                "inputs": task.inputs,
                "enabled": task.enabled,
                "notify_email": task.notify_email,
                "notify_webhook": task.notify_webhook,
            }
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def set_executor(self, callback: Callable) -> None:
        """Set the callback that executes skills."""
        self._executor_callback = callback
    
    def add_task(self, task: TaskDefinition) -> str:
        """Add a task to the scheduler."""
        if not APSCHEDULER_AVAILABLE:
            raise RuntimeError("APScheduler not installed")
        
        self._tasks[task.name] = task
        
        job_id = f"task_{task.name}"
        
        if task.trigger_type == "cron":
            trigger = CronTrigger.from_crontab(task.cron_expr)
        else:
            trigger = IntervalTrigger(seconds=task.interval_seconds)
        
        self._aps_scheduler.add_job(
            self._execute_task,
            trigger=trigger,
            id=job_id,
            name=task.name,
            replace_existing=True,
        )
        
        self._save()
        logger.info(f"Scheduled task: {task.name} ({task.trigger_type})")
        return task.name
    
    def remove_task(self, name: str) -> bool:
        """Remove a task from the scheduler."""
        if name in self._tasks:
            job_id = f"task_{name}"
            try:
                self._aps_scheduler.remove_job(job_id)
            except:
                pass
            del self._tasks[name]
            self._save()
            logger.info(f"Removed task: {name}")
            return True
        return False
    
    def list_tasks(self) -> List[Dict]:
        """List all scheduled tasks."""
        jobs = self._aps_scheduler.get_jobs() if self._aps_scheduler else []
        job_ids = {j.id: j.next_run_time for j in jobs}
        
        return [
            {
                "name": t.name,
                "skill": t.skill,
                "trigger": t.trigger_type,
                "cron_expr": t.cron_expr,
                "interval_seconds": t.interval_seconds,
                "enabled": t.enabled,
                "notify_email": t.notify_email is not None,
                "notify_webhook": t.notify_webhook is not None,
                "next_run": job_ids.get(f"task_{t.name}"),
            }
            for t in self._tasks.values()
        ]
    
    def get_results(self, name: str = None) -> Dict[str, List[Dict]]:
        """Get execution results."""
        if name:
            results = self._results.get(name, [])
            return {name: [self._result_to_dict(r) for r in results]}
        
        return {k: [self._result_to_dict(r) for r in v] 
                for k, v in self._results.items()}
    
    def _result_to_dict(self, result: TaskResult) -> Dict:
        return {
            "name": result.name,
            "skill": result.skill,
            "started_at": result.started_at.isoformat(),
            "finished_at": result.finished_at.isoformat(),
            "status": result.status,
            "output": str(result.output)[:500] if result.output else None,
            "error": result.error,
        }
    
    def _execute_task(self) -> None:
        """Execute a scheduled task."""
        for name, task in list(self._tasks.items()):
            if not task.enabled:
                continue
            
            logger.info(f"Executing scheduled task: {name}")
            
            started = datetime.utcnow()
            status = "success"
            output = None
            error_msg = None
            
            try:
                if self._executor_callback:
                    output = self._executor_callback(task.skill, task.inputs)
                else:
                    output = {"status": "no_executor", "skill": task.skill}
            except Exception as e:
                status = "error"
                error_msg = str(e)
                logger.error(f"Task {name} failed: {e}")
            
            finished = datetime.utcnow()
            
            result = TaskResult(
                name=name,
                skill=task.skill,
                started_at=started,
                finished_at=finished,
                status=status,
                output=output,
                error=error_msg,
            )
            
            if name not in self._results:
                self._results[name] = []
            self._results[name].append(result)
            
            self._notifications.notify(task, result)
    
    def start(self) -> None:
        """Start the scheduler."""
        if self._aps_scheduler and not self._aps_scheduler.running:
            self._aps_scheduler.start()
            logger.info("Scheduler started")
    
    def stop(self) -> None:
        """Stop the scheduler."""
        if self._aps_scheduler and self._aps_scheduler.running:
            self._aps_scheduler.shutdown()
            logger.info("Scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._aps_scheduler.running if self._aps_scheduler else False


class WorkflowRunner:
    """Chain or parallelize multiple skills."""
    
    def __init__(self, skill_executor=None):
        self.skill_executor = skill_executor
    
    def run_sequence(self, steps: List[Dict]) -> List[Dict]:
        """Run skills in sequence, passing output to next input."""
        results = []
        
        for i, step in enumerate(steps):
            skill = step.get("skill")
            inputs = step.get("inputs", {})
            
            if i > 0 and results:
                inputs["previous_output"] = results[-1].get("output")
            
            try:
                if self.skill_executor:
                    result = self.skill_executor.execute(skill, inputs, {})
                else:
                    result = {"success": False, "output": "No executor"}
                results.append(result)
            except Exception as e:
                results.append({"success": False, "error": str(e)})
        
        return results
    
    def run_parallel(self, steps: List[Dict]) -> List[Dict]:
        """Run skills in parallel."""
        import concurrent.futures
        
        def run_step(step):
            skill = step.get("skill")
            inputs = step.get("inputs", {})
            if self.skill_executor:
                return self.skill_executor.execute(skill, inputs, {})
            return {"success": False, "output": "No executor"}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(steps)) as executor:
            futures = [executor.submit(run_step, s) for s in steps]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        return results


# Global scheduler
_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    """Get global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler


def schedule_task(
    name: str,
    skill: str,
    cron_expr: str = None,
    interval_seconds: int = None,
    inputs: Dict = None,
    notify_email: str = None,
    notify_webhook: str = None,
) -> str:
    """Schedule a task with optional notifications.
    
    Args:
        name: Unique task name
        skill: Skill to execute
        cron_expr: Cron expression (e.g., "0 9 * * *" = daily at 9am)
        interval_seconds: Alternative to cron, run every N seconds
        inputs: Dict of inputs to pass to the skill
        notify_email: Email to notify on completion
        notify_webhook: Webhook URL to call on completion
    
    Returns:
        Task name
    
    Example:
        schedule_task(
            name="daily-audit",
            skill="audit-repo",
            cron_expr="0 9 * * *",
            inputs={"repo_path": "./my-project"},
            notify_email="you@example.com",
            notify_webhook="https://your-tunnel.cloudflare.net/notify"
        )
    """
    if not cron_expr and not interval_seconds:
        raise ValueError("Must provide cron_expr or interval_seconds")
    
    scheduler = get_scheduler()
    
    task = TaskDefinition(
        name=name,
        skill=skill,
        trigger_type="cron" if cron_expr else "interval",
        cron_expr=cron_expr,
        interval_seconds=interval_seconds,
        inputs=inputs or {},
        notify_email=notify_email,
        notify_webhook=notify_webhook,
    )
    
    return scheduler.add_task(task)