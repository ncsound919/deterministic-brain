"""Distributed task queue using Redis lists.

Enqueues tasks for background processing and runs workers
that poll and execute them. Falls back to in-process execution
when DISTRIBUTED_MODE=0 or Redis is unavailable.
"""
from __future__ import annotations
import os
import json
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")


class TaskQueue:
    """Distributed task queue using Redis lists.

    When DISTRIBUTED_MODE=1 + Redis available: tasks are enqueued to Redis
    and workers poll via BRPOP.
    When unavailable: tasks are executed synchronously (in-process).
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._handlers_lock = threading.Lock()
        self._workers: Dict[str, threading.Thread] = {}
        self._running_event = threading.Event()

    def register_handler(self, task_type: str, handler: Callable) -> None:
        """Register a handler function for a task type."""
        with self._handlers_lock:
            self._handlers[task_type] = handler

    def enqueue(self, queue_name: str, task_type: str, *args, **kwargs) -> None:
        """Enqueue a task for background execution.

        When distributed: pushes to Redis list for worker to pick up.
        When not distributed: executes synchronously.
        """
        if _DISTRIBUTED:
            try:
                from tools.redis_client import get_redis
                r = get_redis()
                if r.available:
                    r.enqueue(queue_name, {
                        "task_type": task_type,
                        "args": args,
                        "kwargs": kwargs,
                    })
                    logger.debug("Enqueued %s to %s", task_type, queue_name)
                    return
            except Exception:
                pass
        # fallback: execute synchronously
        self._execute_now(task_type, *args, **kwargs)

    def start_worker(self, queue_name: str, poll_interval: float = 1.0) -> None:
        """Start a background worker thread that polls the given queue."""
        if queue_name in self._workers and self._workers[queue_name].is_alive():
            logger.warning("Worker already running for queue: %s", queue_name)
            return
        t = threading.Thread(
            target=self._worker_loop,
            args=(queue_name, poll_interval),
            daemon=True,
        )
        t.start()
        self._workers[queue_name] = t
        self._running_event.set()
        logger.info("Started worker for queue: %s", queue_name)

    def stop_all(self) -> None:
        """Signal all workers to stop."""
        self._running_event.clear()

    def _worker_loop(self, queue_name: str, poll_interval: float) -> None:
        """Background loop: polls Redis for tasks and executes them."""
        while self._running_event.is_set():
            task_data = None
            if _DISTRIBUTED:
                try:
                    from tools.redis_client import get_redis
                    r = get_redis()
                    if r.available:
                        task_data = r.dequeue(queue_name, timeout=1)
                except Exception:
                    pass
            if task_data:
                task_type = task_data.get("task_type", "")
                args = task_data.get("args", ())
                kwargs = task_data.get("kwargs", {})
                self._execute_now(task_type, *args, **kwargs)
            else:
                time.sleep(poll_interval)

    def _execute_now(self, task_type: str, *args, **kwargs) -> Any:
        """Execute a task synchronously."""
        with self._handlers_lock:
            handler = self._handlers.get(task_type)
        if handler is None:
            logger.error("No handler registered for task type: %s", task_type)
            return None
        try:
            result = handler(*args, **kwargs)
            logger.debug("Executed %s: %s", task_type, result)
            return result
        except Exception as e:
            logger.error("Task %s failed: %s", task_type, e)
            return None


_task_queue: Optional[TaskQueue] = None
_task_queue_lock = threading.Lock()


def get_task_queue() -> TaskQueue:
    """Get or create the global TaskQueue singleton."""
    global _task_queue
    if _task_queue is None:
        with _task_queue_lock:
            if _task_queue is None:
                _task_queue = TaskQueue()
    return _task_queue


def reset_task_queue() -> None:
    """Reset the task queue singleton (for testing)."""
    global _task_queue
    if _task_queue is not None:
        _task_queue.stop_all()
    _task_queue = None
