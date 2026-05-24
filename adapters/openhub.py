from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from adapters.base import AdapterCallResult, BaseAdapter

logger = logging.getLogger(__name__)


@dataclass
class PipelineSummary:
    active_pipelines: int
    completed_today: int
    failed_today: int
    queue_depth: int
    last_pipeline_ts: Optional[datetime] = None


@dataclass
class VelocityReport:
    commits_today: int
    deploys_today: int
    tests_passed: int
    tests_failed: int
    pipelines_completed: int
    avg_pipeline_duration_seconds: float = 0.0


@dataclass
class PipelineResult:
    pipeline_id: str
    status: str
    files_generated: List[str] = field(default_factory=list)


class OpenHubAdapter(BaseAdapter):
    def __init__(self, base_url: str, ws_port: int = 3001, timeout: float = 30.0):
        super().__init__(name="openhub")
        self.base_url = base_url.rstrip("/")
        self.ws_port = ws_port
        self.timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def health(self) -> AdapterCallResult:
        try:
            async with self._client() as client:
                resp = await client.get("/api/health")
                ok = resp.status_code < 500
                data = resp.json()
                return AdapterCallResult(ok=ok, status_code=resp.status_code, data=data)
        except Exception as e:
            return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

    async def execute(self, action: str, payload: Optional[Dict[str, Any]] = None, context: Optional[Dict[str, Any]] = None) -> AdapterCallResult:
        payload = payload or {}
        try:
            if action in ("pipeline", "run_pipeline", "trigger_pipeline"):
                spec = payload.get("spec", payload.get("task", ""))
                idempotency_key = payload.get("idempotency_key", "")
                result = await self.trigger_pipeline(spec=spec, idempotency_key=idempotency_key)
                return AdapterCallResult(ok=True, status_code=200, data={
                    "pipeline_id": result.pipeline_id,
                    "status": result.status,
                    "files_generated": result.files_generated,
                })

            if action in ("velocity", "project_velocity"):
                since = payload.get("since")
                if isinstance(since, str):
                    try:
                        since = datetime.fromisoformat(since)
                    except Exception:
                        since = datetime.utcnow()
                if since is None:
                    since = datetime.utcnow()
                report = await self.get_project_velocity(since)
                return AdapterCallResult(ok=True, status_code=200, data={
                    "commits_today": report.commits_today,
                    "deploys_today": report.deploys_today,
                    "tests_passed": report.tests_passed,
                    "tests_failed": report.tests_failed,
                    "pipelines_completed": report.pipelines_completed,
                    "avg_pipeline_duration_seconds": report.avg_pipeline_duration_seconds,
                })

            raise NotImplementedError(f"OpenHubAdapter does not support action '{action}'")
        except Exception as e:
            return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

    async def get_pipeline_status(self) -> PipelineSummary:
        async with self._client() as client:
            resp = await client.get("/api/pipeline/status")
            resp.raise_for_status()
            data = resp.json()
            return PipelineSummary(
                active_pipelines=data.get("active", 0),
                completed_today=data.get("completed_today", 0),
                failed_today=data.get("failed_today", 0),
                queue_depth=data.get("queue_depth", 0),
            )

    async def get_project_velocity(self, since: datetime) -> VelocityReport:
        async with self._client() as client:
            resp = await client.get(
                "/api/projects/velocity",
                params={"since": since.isoformat()},
            )
            resp.raise_for_status()
            data = resp.json()
            return VelocityReport(
                commits_today=data.get("commits", 0),
                deploys_today=data.get("deploys", 0),
                tests_passed=data.get("tests_passed", 0),
                tests_failed=data.get("tests_failed", 0),
                pipelines_completed=data.get("pipelines_completed", 0),
                avg_pipeline_duration_seconds=float(data.get("avg_duration_seconds", 0)),
            )

    async def trigger_pipeline(self, spec: str, idempotency_key: str) -> PipelineResult:
        async def _do_trigger() -> AdapterCallResult:
            async with self._client() as client:
                resp = await client.post(
                    "/api/pipeline/run",
                    json={"spec": spec},
                    headers={"X-Idempotency-Key": idempotency_key},
                )
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                ok = resp.status_code < 500
                return AdapterCallResult(ok=ok, status_code=resp.status_code, data=data)

        result = await self.call_with_idempotency(idempotency_key, _do_trigger)
        if not result.ok:
            raise RuntimeError(f"trigger_pipeline failed: {result.error or result.status_code}")

        data = result.data or {}
        return PipelineResult(
            pipeline_id=data.get("pipeline_id", ""),
            status=data.get("status", "unknown"),
            files_generated=data.get("files", []),
        )
