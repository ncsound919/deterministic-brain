"""UL2 Adapter — connects Deterministic Brain to UL2 community platform.

UL2 is a community platform for courses, marketplaces, and member education.
This adapter bridges DBrain's Governor routing to UL2's community features.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from adapters.base import AdapterCallResult, BaseAdapter

logger = logging.getLogger(__name__)


@dataclass
class CommunityMetrics:
    active_members: int = 0
    courses_published: int = 0
    marketplace_listings: int = 0
    daily_active_users: int = 0


@dataclass
class EducationStats:
    enrollments: int = 0
    completion_rate: float = 0.0
    avg_rating: float = 0.0


class UL2Adapter(BaseAdapter):
    def __init__(self, base_url: str, timeout: float = 30.0):
        super().__init__(name="ul2")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def health(self) -> AdapterCallResult:
        try:
            async with self._client() as client:
                resp = await client.get("/health")
                return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=resp.json() if resp.is_success else None)
        except Exception as e:
            return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

    async def execute(self, action: str, payload: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None) -> AdapterCallResult:
        payload = payload or {}
        try:
            if action in ("community_feature", "run_community_feature"):
                feature = payload.get("feature", "education")
                feature_payload = payload.get("payload", {"task": payload.get("task", ""), **(payload.get("context", {}) or {})})
                return await self.run_community_feature(feature=feature, payload=feature_payload)

            if action in ("community_metrics", "get_community_metrics", "metrics"):
                return await self.get_community_metrics()

            if action in ("education_stats", "get_education_stats"):
                return await self.get_education_stats()

            raise NotImplementedError(f"UL2Adapter does not support action '{action}'")
        except Exception as e:
            return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

    async def get_community_metrics(self) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.get("/api/community/metrics")
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    async def run_community_feature(self, feature: str, payload: dict = None) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.post(
                f"/api/community/{feature}/run",
                json=payload or {},
            )
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    async def get_education_stats(self) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.get("/api/education/stats")
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)
