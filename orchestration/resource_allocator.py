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
        self._lock = threading.Lock()
        self._available = max_units
        self._allocations: Dict[str, int] = {}

    def allocate(self, key: str, units: int = 1, timeout: float = None) -> bool:
        """Attempt to allocate `units` for `key`. Returns True on success."""
        end = None
        if timeout is not None:
            import time
            end = time.time() + timeout

        with self._lock:
            while self._available < units:
                if end is not None and time.time() > end:
                    return False
                # release the lock briefly to avoid deadlock
                self._lock.release()
                try:
                    import time
                    time.sleep(0.01)
                finally:
                    self._lock.acquire()

            # allocate
            self._available -= units
            self._allocations[key] = self._allocations.get(key, 0) + units
            return True

    def release(self, key: str, units: int = 1) -> None:
        """Release previously allocated units for `key`."""
        with self._lock:
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

    def get_allocations(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._allocations)

    def get_available(self) -> int:
        with self._lock:
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
