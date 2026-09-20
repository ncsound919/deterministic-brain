"""Recourse Adapter — connects Deterministic Brain to the Recourse engine.

Recourse (agents/recourse, canonical port 3050) is the fleet's autonomous
self-developing architecture OS: template-driven internal component building,
a versioned tool registry where every promoted version passed a real sandboxed
test suite, self-healing code repair, a recursive learner with property-based
gene evaluation, a dream engine, recursive-math loops, and a 7-layer Lego
composable ML engine.

Follows the existing adapter pattern (see adapters/bbtech.py,
adapters/aetherdesk.py). Fail-soft: every call is best-effort and returns an
AdapterCallResult; a down Recourse service never raises.

Actions supported (executed against real /api/recourse/* routes):
  status / health          -> GET  /api/recourse/status
  registry / list_tools    -> GET  /api/recourse/registry
  provenance               -> GET  /api/recourse/provenance
  templates / list_templates -> GET /api/recourse/templates
  verify                   -> POST /api/recourse/verify
  execute                  -> POST /api/recourse/execute
  repair / repair_single   -> POST /api/recourse/repair/single
  scan_heal                -> POST /api/recourse/repair/scan-heal
  build_component          -> POST /api/recourse/templates/build
  math_state               -> GET  /api/recourse/math/state
  math_step                -> POST /api/recourse/math/step
  lego_state               -> GET  /api/lego/state
  lego_assemble            -> POST /api/lego/assemble
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from adapters.base import AdapterCallResult, BaseAdapter

logger = logging.getLogger(__name__)

RECOURSE_DEFAULTS = {
    "base_url": "http://127.0.0.1:3050",
    "timeout": 30.0,
}


class RecourseAdapter(BaseAdapter):
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None):
        super().__init__(name="recourse")
        self.base_url = (base_url or RECOURSE_DEFAULTS["base_url"]).rstrip("/")
        self.timeout = timeout or RECOURSE_DEFAULTS["timeout"]

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )

    async def health(self) -> AdapterCallResult:
        return await self.get_status()

    async def execute(
        self,
        action: str,
        payload: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AdapterCallResult:
        payload = payload or {}
        try:
            if action in ("status", "health", "status_report"):
                return await self.get_status()

            if action in ("registry", "list_tools", "tool_registry"):
                return await self.get_registry()

            if action in ("provenance", "chain", "hash_chain"):
                return await self.get_provenance()

            if action in ("templates", "list_templates", "component_templates"):
                domain = payload.get("domain")
                params = {"domain": domain} if domain else {}
                return await self._get("/api/recourse/templates", params=params)

            if action in ("verify", "verify_code"):
                body = {
                    "domain": payload.get("domain", "coding"),
                    "sourceCode": payload.get("sourceCode") or payload.get("source_code", ""),
                    "testSuiteCode": payload.get("testSuiteCode") or payload.get("test_suite", ""),
                    "extra": payload.get("extra"),
                }
                return await self._post("/api/recourse/verify", body)

            if action in ("execute", "run_tool", "execute_tool"):
                body = {
                    "toolName": payload.get("toolName") or payload.get("tool_name"),
                    "sourceCode": payload.get("sourceCode") or payload.get("source_code"),
                    "functionName": payload.get("functionName") or payload.get("function_name"),
                    "args": payload.get("args", []),
                }
                return await self._post("/api/recourse/execute", body)

            if action in ("repair", "repair_single", "self_repair"):
                body = {
                    "toolName": payload.get("toolName") or payload.get("tool_name", "unknown"),
                    "brokenCode": payload.get("brokenCode") or payload.get("broken_code", ""),
                    "faultHint": payload.get("faultHint") or payload.get("fault_hint"),
                }
                return await self._post("/api/recourse/repair/single", body)

            if action in ("scan_heal", "scan_and_heal"):
                return await self._post("/api/recourse/repair/scan-heal", {})

            if action in ("build_component", "templates_build", "build"):
                body = {
                    "templateId": payload.get("templateId") or payload.get("template_id"),
                    "componentName": payload.get("componentName") or payload.get("component_name"),
                    "params": payload.get("params", {}),
                    "withSelfHealing": payload.get("withSelfHealing", True),
                    "domain": payload.get("domain"),
                }
                return await self._post("/api/recourse/templates/build", body)

            if action in ("math_state", "recursive_math_state"):
                return await self._get("/api/recourse/math/state")

            if action in ("math_step", "recursive_math_step"):
                return await self._post("/api/recourse/math/step", payload or {})

            if action in ("lego_state", "lego"):
                return await self._get("/api/lego/state")

            if action in ("lego_assemble", "assemble"):
                return await self._post("/api/lego/assemble", {})

            raise NotImplementedError(f"RecourseAdapter does not support action '{action}'")
        except Exception as e:  # pragma: no cover - defensive
            return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

    # ---- Helpers ---- #

    async def get_status(self) -> AdapterCallResult:
        return await self._get("/api/recourse/status")

    async def get_registry(self) -> AdapterCallResult:
        return await self._get("/api/recourse/registry")

    async def get_provenance(self) -> AdapterCallResult:
        return await self._get("/api/recourse/provenance")

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> AdapterCallResult:
        async with self._client() as client:
            try:
                resp = await client.get(path, params=params)
                data = resp.json() if resp.content else None
                return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)
            except Exception as e:
                logger.warning("Recourse GET %s failed: %s", path, e)
                return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))

    async def _post(self, path: str, body: Dict[str, Any]) -> AdapterCallResult:
        async with self._client() as client:
            try:
                resp = await client.post(path, json=body)
                data = resp.json() if resp.content else None
                return AdapterCallResult(ok=resp.is_success, status_code=resp.status_code, data=data)
            except Exception as e:
                logger.warning("Recourse POST %s failed: %s", path, e)
                return AdapterCallResult(ok=False, status_code=0, data=None, error=str(e))
