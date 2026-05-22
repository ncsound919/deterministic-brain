"""Redis client for distributed caching, pub/sub, and task queue.

Gated by DISTRIBUTED_MODE=1. Falls back to in-memory when Redis unavailable.
"""
from __future__ import annotations
import os
import json
import threading
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_DISTRIBUTED = os.environ.get("DISTRIBUTED_MODE", "").lower() in ("1", "true", "yes")


class RedisClient:
    """Redis connection manager with in-memory fallback.

    When DISTRIBUTED_MODE=1 + Redis available: uses Redis for all operations.
    Otherwise: uses in-memory dicts (single-worker compatible).
    """

    def __init__(self):
        self._redis = None
        self._available = False
        # In-memory fallback stores
        self._cache: Dict[str, Dict] = {}
        self._pubsub_callbacks: Dict[str, List[Callable]] = {}
        self._task_queues: Dict[str, list] = {}
        self._fallback_lock = threading.Lock()

    def connect(self, url: Optional[str] = None) -> bool:
        """Initialize Redis connection. Returns True if successful."""
        if not _DISTRIBUTED:
            return False
        try:
            import redis as redis_mod
            url = url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            self._redis = redis_mod.from_url(url, decode_responses=True)
            self._redis.ping()
            self._available = True
            logger.info("Redis connected: %s", url)
            return True
        except Exception as e:
            logger.warning("Redis unavailable, using in-memory fallback: %s", e)
            return False

    @property
    def available(self) -> bool:
        return self._available

    # ── Cache operations ───────────────────────────────────────

    def cache_get(self, key: str) -> Optional[str]:
        if self._available:
            return self._redis.get(key)
        with self._fallback_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.get("expires_at", float("inf")) < __import__("time").time():
                self._cache.pop(key, None)
                return None
            return entry["value"]

    def cache_set(self, key: str, value: str, ttl: int = 60) -> None:
        if self._available:
            self._redis.setex(key, ttl, value)
        else:
            with self._fallback_lock:
                self._cache[key] = {
                    "value": value,
                    "expires_at": __import__("time").time() + ttl,
                }

    def cache_delete(self, key: str) -> None:
        if self._available:
            self._redis.delete(key)
        else:
            self._cache.pop(key, None)

    def cache_scan_delete(self, prefix: str) -> None:
        """Delete all keys with a given prefix."""
        if self._available:
            for key in self._redis.scan_iter(f"{prefix}*"):
                self._redis.delete(key)
        else:
            with self._fallback_lock:
                self._cache = {
                    k: v for k, v in self._cache.items() if not k.startswith(prefix)
                }

    # ── Pub/Sub operations ─────────────────────────────────────

    def publish(self, channel: str, message: str) -> None:
        if self._available:
            self._redis.publish(channel, message)
        with self._fallback_lock:
            callbacks = list(self._pubsub_callbacks.get(channel, []))
        for cb in callbacks:
            try:
                cb(message)
            except Exception:
                pass

    def subscribe(self, channel: str, callback: Callable[[str], None]) -> None:
        with self._fallback_lock:
            self._pubsub_callbacks.setdefault(channel, []).append(callback)
        if self._available and channel not in self._pubsub_callbacks:
            pubsub = self._redis.pubsub()
            pubsub.subscribe(**{channel: lambda m: callback(m["data"])})
            t = threading.Thread(target=pubsub.run_in_thread, daemon=True)
            t.start()

    # ── Task Queue operations ──────────────────────────────────

    def enqueue(self, queue: str, task_data: Dict) -> None:
        payload = json.dumps(task_data, default=str)
        if self._available:
            self._redis.lpush(queue, payload)

    def dequeue(self, queue: str, timeout: int = 5) -> Optional[Dict]:
        if self._available:
            result = self._redis.brpop(queue, timeout=timeout)
            if result:
                return json.loads(result[1])
        return None

    # ── Metrics operations ─────────────────────────────────────

    def counter_increment(self, key: str, amount: int = 1) -> None:
        if self._available:
            self._redis.incrby(key, amount)

    def counter_get(self, key: str) -> int:
        if self._available:
            val = self._redis.get(key)
            return int(val) if val else 0
        return 0


_redis_client: Optional[RedisClient] = None
_redis_lock = threading.Lock()


def get_redis() -> RedisClient:
    """Get or create the global Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        with _redis_lock:
            if _redis_client is None:
                _redis_client = RedisClient()
                _redis_client.connect()
    return _redis_client


def reset_redis() -> None:
    """Reset the Redis singleton (for testing)."""
    global _redis_client
    _redis_client = None
