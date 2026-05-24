from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from adapters.base import AdapterCallResult, BaseAdapter
from ledger import write_event

logger = logging.getLogger(__name__)


@dataclass
class CampaignConfig:
    profile_id: str
    max_concurrent: int
    delay_between_calls: float
    filter_status: str
    lead_limit: int
    tenant_id: str = "TENANT-001"


@dataclass
class CampaignStatus:
    id: str
    status: str
    leads_queued: int


@dataclass
class CallEvent:
    id: str
    tenant_id: str
    campaign_id: Optional[str]
    outcome: str
    ts: datetime
    metadata: Dict[str, Any]


@dataclass
class UsageReport:
    calls: int
    minutes: float
    cost: float


@dataclass
class CampaignStats:
    total_calls: int
    answered: int
    voicemail: int
    converted: int


class AetherDeskAdapter(BaseAdapter):
    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        super().__init__(name="aetherdesk")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    async def health(self) -> AdapterCallResult:
        async with self._client() as client:
            try:
                resp = await client.get("/api/v1/usage")
                ok = resp.status_code < 500
                return AdapterCallResult(ok=ok, status_code=resp.status_code, data=resp.json())
            except Exception as e:
                logger.warning("AetherDesk health check failed: %s", e)
                return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

    # ---- Stats / usage ---- #

    async def get_campaign_stats(self) -> CampaignStats:
        async with self._client() as client:
            resp = await client.get("/campaign/stats")
            resp.raise_for_status()
            data = resp.json()
            return CampaignStats(
                total_calls=data.get("total_calls", 0),
                answered=data.get("answered", 0),
                voicemail=data.get("voicemail", 0),
                converted=data.get("converted", 0),
            )

    async def get_usage_and_billing(self) -> UsageReport:
        async with self._client() as client:
            resp = await client.get("/api/v1/usage")
            resp.raise_for_status()
            usage = resp.json()
            return UsageReport(
                calls=usage.get("total_calls", 0),
                minutes=float(usage.get("total_minutes", 0.0)),
                cost=float(usage.get("total_cost", 0.0)),
            )

    async def get_call_outcomes(self, since: datetime) -> List[CallEvent]:
        async with self._client() as client:
            resp = await client.get(
                "/campaign/stats",
                params={"since": since.isoformat()},
            )
            resp.raise_for_status()
            data = resp.json()
            events: List[CallEvent] = []
            for raw in data.get("events", []):
                events.append(
                    CallEvent(
                        id=str(raw.get("id")),
                        tenant_id=str(raw.get("tenant_id")),
                        campaign_id=raw.get("campaign_id"),
                        outcome=str(raw.get("outcome")),
                        ts=datetime.fromisoformat(raw["ts"]),
                        metadata=raw.get("metadata") or {},
                    )
                )
            return events

    # ---- Campaign orchestration ---- #

    async def validate_lead_inventory(self, config: CampaignConfig) -> bool:
        async with self._client() as client:
            resp = await client.get(
                "/campaign/leads/summary",
                params={"profile_id": config.profile_id, "tenant_id": config.tenant_id},
            )
            resp.raise_for_status()
            data = resp.json()
            leads_available = int(data.get("leads_available", 0))
            return leads_available > 0

    async def launch_campaign(self, config: CampaignConfig, idempotency_key: str) -> CampaignStatus:
        async def _do_launch() -> AdapterCallResult:
            payload = {
                "profile_id": config.profile_id,
                "max_concurrent": config.max_concurrent,
                "delay_between_calls": config.delay_between_calls,
                "filter_status": config.filter_status,
                "lead_limit": config.lead_limit,
                "tenant_id": config.tenant_id,
            }
            async with self._client() as client:
                resp = await client.post(
                    "/campaign/launch",
                    json=payload,
                    headers={"X-Idempotency-Key": idempotency_key},
                )
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                ok = resp.status_code < 500
                return AdapterCallResult(ok=ok, status_code=resp.status_code, data=data)

        result = await self.call_with_idempotency(idempotency_key, _do_launch)
        if not result.ok:
            raise RuntimeError(f"launch_campaign failed: {result.error or result.status_code}")

        data = result.data or {}
        status = CampaignStatus(
            id=str(data.get("campaign_id", "")),
            status=str(data.get("status", "unknown")),
            leads_queued=int(data.get("leads_queued", 0)),
        )

        event = {
            "ts": datetime.utcnow().isoformat(),
            "correlation_id": data.get("correlation_id", idempotency_key),
            "type": "campaign_launch",
            "system": "aetherdesk",
            "data": {
                "campaign_id": status.id,
                "status": status.status,
                "leads_queued": status.leads_queued,
                "profile_id": config.profile_id,
                "tenant_id": config.tenant_id,
            },
        }
        write_event(event)

        return status
