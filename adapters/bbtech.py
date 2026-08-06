"""BB-Tech Adapter — connects Deterministic Brain to BB-Tech's research pipeline.

Follows the existing adapter pattern (see adapters/aetherdesk.py, adapters/openhub.py).
Ships a ResearchExperiment contract through BB-Tech's daily research pipeline.

Two entry modes:
  1. Scheduled daily run → calls POST /api/v1/pipeline/run
  2. Ad-hoc research command → calls POST /api/v1/pipeline/run with filtered input
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
import asyncio

import httpx

from adapters.base import AdapterCallResult, BaseAdapter

# `workflows.research_experiment` ships in the separate BB-Tech project and is
# NOT vendored here. Fail-soft: the API server must boot without it, and the
# research_experiment action reports a clear error until it's installed.
try:  # pragma: no cover - depends on external repo
    from workflows.research_experiment import (
        ResearchExperiment, ExperimentStatus, ExperimentEntryMode, ResearchInput,
    )
    _WORKFLOWS_OK = True
except ImportError:
    _WORKFLOWS_OK = False

    @dataclass
    class ResearchInput:
        """Fallback contract (fields derived from adapter usage)."""
        target_type: str = "product"
        target_ids: list = field(default_factory=list)
        days_back: int = 1

    class _EntryModeValue:
        def __init__(self, value: str):
            self.value = value

    class ExperimentEntryMode:
        ADHOC = _EntryModeValue("adhoc")
        SCHEDULED = _EntryModeValue("scheduled")

    class ExperimentStatus:
        COMPLETED = "completed"
        FAILED = "failed"
        PENDING = "pending"

    class ResearchExperiment:
        """Fallback contract so the adapter imports; runtime use is blocked."""
        def __init__(self, experiment_id: str = "", entry_mode=None, input=None, **kwargs):
            self.experiment_id = experiment_id
            self.entry_mode = entry_mode or ExperimentEntryMode.ADHOC
            self.input = input or ResearchInput()
            self.result_summary: Optional[dict] = None
            self.error: Optional[str] = None
            self.status = ExperimentStatus.PENDING
            self.completed_at: Optional[str] = None
            self.updated_at: Optional[str] = None
            self._provenance: list = []

        def add_provenance(self, hop: str, action: str, metadata: Optional[dict] = None):
            self._provenance.append({"hop": hop, "action": action, "metadata": metadata or {}})

logger = logging.getLogger(__name__)

BBTECH_DEFAULTS = {
    "base_url": "http://127.0.0.1:8005",
    "api_key": "pipeline-key-dev",
    "timeout": 30.0,
    "poll_interval": 5.0,
}


@dataclass
class PipelineSummary:
    run_id: str = ""
    stage: str = ""
    experiments_run: int = 0
    experiments_passed: int = 0
    experiments_failed: int = 0
    products_scanned: int = 0
    archetype_distribution: dict = field(default_factory=dict)
    quality_pass_rate: float = 0.0
    errors: list[str] = field(default_factory=list)


class BBTechAdapter(BaseAdapter):
    def __init__(self, base_url: str = None, api_key: str = None, timeout: float = None):
        super().__init__(name="bb-tech")
        self.base_url = (base_url or BBTECH_DEFAULTS["base_url"]).rstrip("/")
        self.api_key = api_key or BBTECH_DEFAULTS["api_key"]
        self.timeout = timeout or BBTECH_DEFAULTS["timeout"]

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
        )

    async def health(self) -> AdapterCallResult:
        try:
            async with self._client() as client:
                resp = await client.get("/health")
                data = resp.json()
                return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)
        except Exception as e:
            return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

    async def execute(self, action: str, payload: Optional[dict] = None, context: Optional[dict] = None) -> AdapterCallResult:
        payload = payload or {}
        if action in ("research_experiment", "pipeline", "run_pipeline"):
            if not _WORKFLOWS_OK:
                return AdapterCallResult(
                    ok=False, status_code=0, data=None,
                    error="workflows.research_experiment not installed — it ships in the BB-Tech project.",
                )
            try:
                from workflows.research_experiment import ResearchInput
            except ImportError as exc:  # pragma: no cover - defensive
                return AdapterCallResult(ok=False, status_code=0, data=None, error=str(exc))

            input_ = ResearchInput(
                target_type=payload.get("target_type", "product"),
                target_ids=payload.get("target_ids", []),
                days_back=payload.get("days_back", 1),
            )
            return await self.run_pipeline(input_)

        if action in ("status", "pipeline_status"):
            return await self.get_pipeline_status()

        if action in ("latest_run", "pipeline_runs"):
            return await self.get_latest_pipeline_run()

        if action in ("quality_criteria", "criteria"):
            return await self.get_quality_criteria()

        raise NotImplementedError(f"BBTechAdapter does not support action '{action}'")

    async def run_pipeline(self, input_: ResearchInput = None) -> AdapterCallResult:
        """Trigger BB-Tech's daily research pipeline.

        For scheduled runs: send empty POST to run full cycle.
        For ad-hoc: send filtered payload.
        """
        async with self._client() as client:
            payload = {}
            if input_:
                payload = input_.__dict__
            resp = await client.post("/api/v1/pipeline/run", json=payload)
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    async def get_pipeline_status(self) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.get("/api/v1/pipeline/status")
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    async def get_latest_pipeline_run(self) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.get("/api/v1/pipeline/runs?limit=1")
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    async def get_archetypes(self) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.get("/api/v1/pipeline/archetypes")
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    async def get_quality_criteria(self) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.get("/api/v1/pipeline/criteria")
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    async def run_experiment(
        self, experiment: ResearchExperiment, idempotency_key: str = "",
    ) -> ResearchExperiment:
        """Run a single experiment through BB-Tech and return the completed contract.

        Orchestrates the full lifecycle:
          1. Log provenance (DBrain dispatched)
          2. Call run_pipeline
          3. Poll for completion
          4. Fetch results
          5. Log provenance (BB-Tech processed)
        """
        experiment.add_provenance(hop="deterministic-brain", action="dispatch_to_bbtech")

        async def _execute() -> AdapterCallResult:
            async with self._client() as client:
                payload = {
                    "experiment_id": experiment.experiment_id,
                    "entry_mode": experiment.entry_mode.value,
                    "input": experiment.input.__dict__,
                }
                return await self.call_with_idempotency(
                    idempotency_key or f"exp-{experiment.experiment_id}",
                    lambda: self._do_run_experiment(client, payload),
                )

        result = await _execute()
        if result.ok:
            experiment.result_summary = result.data or {}
            experiment.add_provenance(hop="bb-tech", action="pipeline_completed")
            experiment.status = ExperimentStatus.COMPLETED
        else:
            experiment.error = result.error
            experiment.status = ExperimentStatus.FAILED
            experiment.add_provenance(hop="bb-tech", action="pipeline_failed", metadata={"error": result.error})

        experiment.completed_at = datetime.utcnow().isoformat()
        experiment.updated_at = experiment.completed_at
        return experiment

    async def _do_run_experiment(self, client, payload: dict) -> AdapterCallResult:
        resp = await client.post("/api/v1/pipeline/run", json=payload)
        return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=resp.json() if resp.is_success else None)

    async def get_experiment_results(self, run_id: str) -> AdapterCallResult:
        async with self._client() as client:
            resp = await client.get(f"/api/v1/pipeline/runs?limit=5")
            data = resp.json() if resp.is_success else None
            return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)

    def to_pipeline_summary(self, result: AdapterCallResult) -> PipelineSummary:
        if not result.ok or not result.data:
            return PipelineSummary()
        d = result.data
        return PipelineSummary(
            run_id=d.get("run_id", ""),
            stage=d.get("stage", ""),
            experiments_run=d.get("experiments_run", 0),
            experiments_passed=d.get("experiments_passed", 0),
            experiments_failed=d.get("experiments_failed", 0),
            products_scanned=d.get("products_scanned", 0),
            archetype_distribution=d.get("archetype_distribution", {}),
            quality_pass_rate=d.get("quality_pass_rate", 0.0),
            errors=d.get("errors", []),
        )
