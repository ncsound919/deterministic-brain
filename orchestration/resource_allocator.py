"""resource_allocator.py

Simple resource allocator to throttle concurrent skill executions.

Provides a conservative semaphore-based allocation API suitable for
wrapping expensive I/O-bound skills or limiting parallelism in the DCA.
"""
from __future__ import annotations
import threading
from contextlib import contextmanager
from typing import Dict


class ResourceAllocator:
    """Tracks and enforces a maximum concurrent unit quota.

    Usage:
        ra = ResourceAllocator(max_units=10)
        if ra.allocate("task-123", units=2, timeout=5):
            try:
                run_task()
            finally:
                ra.release("task-123", units=2)
    """

    def __init__(self, max_units: int = 8):
        self.max_units = max_units
        self._available = max_units
        self._allocations: Dict[str, int] = {}
        self._condition = threading.Condition()

    def allocate(self, key: str, units: int = 1, timeout: float = None) -> bool:
        """Attempt to allocate `units` for `key`. Returns True on success."""
        with self._condition:
            if not self._condition.wait_for(
                lambda: self._available >= units,
                timeout=timeout,
            ):
                return False
            self._available -= units
            self._allocations[key] = self._allocations.get(key, 0) + units
            return True

    def release(self, key: str, units: int = 1) -> None:
        """Release previously allocated units for `key`."""
        with self._condition:
            held = self._allocations.get(key, 0)
            release_units = min(units, held)
            if release_units <= 0:
                return
            held -= release_units
            if held:
                self._allocations[key] = held
            else:
                self._allocations.pop(key, None)
            self._available = min(self.max_units, self._available + release_units)
            self._condition.notify_all()

    def get_allocations(self) -> Dict[str, int]:
        with self._condition:
            return dict(self._allocations)

    def get_available(self) -> int:
        with self._condition:
            return int(self._available)

    @contextmanager
    def allocating(self, key: str, units: int = 1, timeout: float = None):
        ok = self.allocate(key, units, timeout)
        try:
            yield ok
        finally:
            if ok:
                self.release(key, units)


__all__ = ["ResourceAllocator"]
