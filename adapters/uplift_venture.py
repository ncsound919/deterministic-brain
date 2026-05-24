"""Uplift-Venture Adapter — connects Deterministic Brain to Uplift-Venture business OS.

Uplift-Venture is a business operations platform for workforce, staffing, and shift management.
This adapter bridges DBrain's Governor routing to Uplift-Venture's business modules.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from adapters.base import AdapterCallResult, BaseAdapter

logger = logging.getLogger(__name__)


@dataclass
class WorkforceSummary:
    active_shifts: int = 0
    open_requests: int = 0
    fulfillment_rate: float = 0.0
    total_workers: int = 0


@dataclass
class BusinessMetrics:
    revenue: float = 0.0
    active_contracts: int = 0
    pending_invoices: int = 0
    utilization_pct: float = 0.0


class UpliftVentureAdapter(BaseAdapter):
    def __init__(self, base_url: str, timeout: float = 30.0):
        super().__init__(name="uplift-venture")
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
            if action in ("business_module", "run_business_module"):
                module = payload.get("module", "workforce")
                module_payload = payload.get("payload", {"task": payload.get("task", ""), **(payload.get("context", {}) or {})})
                return await self.run_business_module(module=module, payload=module_payload)

            if action in ("workforce_status", "get_workforce_status"):
                return await self.get_workforce_status()

            if action in ("business_metrics", "get_business_metrics", "metrics"):
                return await self.get_business_metrics()

            raise NotImplementedError(f"UpliftVentureAdapter does not support action '{action}'")
        except Exception as e:
            return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

    async def get_workforce_status(self) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.get("/api/workforce/status")
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    async def get_business_metrics(self) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.get("/api/business/metrics")
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    async def run_business_module(self, module: str, payload: dict = None) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.post(
                f"/api/business/{module}/run",
                json=payload or {},
            )
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)
