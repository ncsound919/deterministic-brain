from __future__ import annotations
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from config import cfg
from brain.autodream import run_autodream
from features.autonomy import get_autonomy

logger = logging.getLogger(__name__)


class KairosDaemon:
    """Persistent daemon that runs maintenance tasks when user is idle."""

    def __init__(self, idle_threshold_minutes: int = None):
        self.idle_threshold = (idle_threshold_minutes or cfg.kairos_idle_threshold_minutes) * 60
        self.last_activity = time.time()
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._maintenance_callback: Optional[Callable] = None
        self._stats = {
            "start_time": None,
            "last_maintenance": None,
            "total_runs": 0,
            "idle_triggers": 0,
        }

    def update_activity(self) -> None:
        """Call this when user interacts via CLI/API."""
        self.last_activity = time.time()

    def is_idle(self) -> bool:
        """Check if user has been idle beyond threshold."""
        return (time.time() - self.last_activity) > self.idle_threshold

    def set_maintenance_callback(self, callback: Callable) -> None:
        """Set callback for additional maintenance tasks."""
        self._maintenance_callback = callback

    def _run_maintenance(self) -> None:
        """Execute maintenance tasks."""
        self._stats["last_maintenance"] = datetime.now(timezone.utc).isoformat()
        self._stats["total_runs"] += 1

        run_autodream(dry_run=False)

        if self._maintenance_callback:
            try:
                self._maintenance_callback()
            except Exception as e:
                logger.warning("Maintenance callback failed: %s", e)

        try:
            get_autonomy().tick()
        except Exception as e:
            logger.warning("Autonomy tick failed: %s", e)

        self._cleanup_cache()

    def _cleanup_cache(self) -> None:
        """Clean .aether_prime_cache if it grows too large."""
        import os
        import shutil

        cache_dir = ".aether_prime_cache"
        if not os.path.exists(cache_dir):
            return

        total_size = 0
        for f in os.listdir(cache_dir):
            fpath = os.path.join(cache_dir, f)
            if os.path.isfile(fpath):
                total_size += os.path.getsize(fpath)

        if total_size > 100 * 1024 * 1024:
            try:
                shutil.rmtree(cache_dir)
                os.makedirs(cache_dir, exist_ok=True)
            except Exception as e:
                logger.warning("Cache cleanup failed: %s", e)

    def run_maintenance_loop(self) -> None:
        """Main daemon loop - runs when idle."""
        self._stats["start_time"] = datetime.now(timezone.utc).isoformat()

        while self.running:
            if self.is_idle():
                self._stats["idle_triggers"] += 1
                self._run_maintenance()
                time.sleep(300)  # Sleep 5 minutes after maintenance
            else:
                time.sleep(60)  # Check every minute

    def start(self) -> None:
        """Start the daemon in a background thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self.run_maintenance_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the daemon."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)

    def get_stats(self) -> Dict:
        """Return daemon statistics."""
        return {
            **self._stats,
            "running": self.running,
            "idle_threshold_seconds": self.idle_threshold,
            "is_currently_idle": self.is_idle(),
            "seconds_since_activity": round(time.time() - self.last_activity),
        }


_daemon: Optional[KairosDaemon] = None


def get_daemon() -> KairosDaemon:
    global _daemon
    if _daemon is None:
        _daemon = KairosDaemon()
    return _daemon


def start_kairos() -> Dict:
    daemon = get_daemon()
    daemon.start()
    return daemon.get_stats()


def stop_kairos() -> Dict:
    daemon = get_daemon()
    daemon.stop()
    return daemon.get_stats()


def kairos_status() -> Dict:
    daemon = get_daemon()
    return daemon.get_stats()
