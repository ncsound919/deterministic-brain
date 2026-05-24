from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from ledger import get_cached_response, mark_response_seen

logger = logging.getLogger(__name__)


@dataclass
class AdapterCallResult:
    ok: bool
    status_code: int
    data: Any
    error: Optional[str] = None


class LRUCache:
    def __init__(self, maxsize: int = 512):
        self.maxsize = maxsize
        self._data: OrderedDict[str, Any] = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def set(self, key: str, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self.maxsize:
            self._data.popitem(last=False)


class BaseAdapter:
    def __init__(self, name: str, max_retries: int = 3, initial_backoff: float = 1.0, cache_size: int = 512):
        self.name = name
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self._cache = LRUCache(maxsize=cache_size)

    async def call_with_idempotency(
        self,
        idempotency_key: str,
        fn: Callable[[], Awaitable[AdapterCallResult]],
    ) -> AdapterCallResult:
        cached = self._cache.get(idempotency_key)
        if cached is not None:
            logger.info("%s: returning cached response from LRU for key=%s", self.name, idempotency_key)
            return cached

        persisted = get_cached_response(idempotency_key)
        if persisted is not None:
            logger.info("%s: returning cached response from Ledger for key=%s", self.name, idempotency_key)
            result = AdapterCallResult(
                ok=bool(persisted.get("ok", True)),
                status_code=int(persisted.get("status_code", 200)),
                data=persisted.get("data"),
                error=persisted.get("error"),
            )
            self._cache.set(idempotency_key, result)
            return result

        attempt = 0
        backoff = self.initial_backoff
        last_result: Optional[AdapterCallResult] = None

        while attempt <= self.max_retries:
            attempt += 1
            try:
                result = await fn()
                last_result = result
                if result.ok:
                    break
            except Exception as e:
                logger.warning("%s: call failed on attempt %s: %s", self.name, attempt, e)
                last_result = AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

            if attempt <= self.max_retries:
                await asyncio.sleep(backoff)
                backoff *= 2

        if last_result is None:
            last_result = AdapterCallResult(ok=False, status_code=0, data=None, error="no_result")

        persist_payload: Dict[str, Any] = {
            "ok": last_result.ok,
            "status_code": last_result.status_code,
            "data": last_result.data,
            "error": last_result.error,
        }
        mark_response_seen(idempotency_key, persist_payload)
        self._cache.set(idempotency_key, last_result)

        return last_result

    async def health(self) -> AdapterCallResult:
        raise NotImplementedError

    async def execute(
        self,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AdapterCallResult:
        """Execute a normalized adapter action.

        Each adapter can map generic Governor actions to the target system's
        concrete API and return a normalized AdapterCallResult.
        """
        raise NotImplementedError(f"{self.name} adapter does not support execute() for action='{action}'")

    @property
    def supported_actions(self) -> List[str]:
        return []
