"""Business-Logic-MCP bridge for the deterministic brain.

Spawns the enhanced Business-Logic-MCP server (v1.1, 37 tools) over stdio and
exposes the entity-facing + deterministic verification/codegen tools. Honest
contract: every call returns {ok, ...} from the server; a failed spawn or tool
call returns {ok: False, error: ...} — never a fabricated answer.

Set BUSINESS_LOGIC_MCP to the built server entry (dist/index.js) if it is not
at the default location.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

from tools.mcp_client import MCPClient

_DEFAULT_SERVER = r"C:\Users\User\Downloads\Uplift\05_Apps\Business-Logic-MCP\dist\index.js"


def _server_command() -> list[str]:
    entry = os.environ.get("BUSINESS_LOGIC_MCP", _DEFAULT_SERVER)
    if not Path(entry).is_file():
        # Fall back to the Skilltech clone if present; else report honestly.
        alt = Path(r"C:\Users\User\Downloads\Skilltech\Business-Logic-MCP\dist\index.js")
        if alt.is_file():
            entry = str(alt)
    return ["node", entry]


# One long-lived event loop (daemon thread) so the spawned BLMCP subprocess is
# not torn down between sync calls (asyncio.run would leak the transport).
_loop = asyncio.new_event_loop()
_thread = threading.Thread(target=_loop.run_forever, name="blmcp-loop", daemon=True)
_thread.start()


def _call(coro, timeout: float = 30.0) -> Any:
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=timeout)


class BusinessLogicBridge:
    def __init__(self) -> None:
        self.client = MCPClient(server_command=_server_command())
        self._connected = False

    async def _ensure_connected(self) -> bool:
        if not self._connected:
            self._connected = await self.client.connect()
        return self._connected

    async def call(self, tool: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not await self._ensure_connected():
            return {"ok": False, "error": "failed to connect to Business-Logic-MCP"}
        try:
            result = await self.client.call_tool(tool, arguments or {})
        except Exception as exc:  # pragma: no cover - transport failures
            return {"ok": False, "error": f"tool call failed: {exc}"}
        if isinstance(result, dict) and result.get("error"):
            return {"ok": False, "error": str(result["error"])}
        return {"ok": True, "tool": tool, "result": result}

    # -- entity-facing (v1.0) -------------------------------------------
    async def get_entity_rules(self, entity: str) -> Dict[str, Any]:
        return await self.call("get_entity_rules", {"entity": entity})

    async def get_footguns(self, entity: Optional[str] = None) -> Dict[str, Any]:
        return await self.call("get_footguns", {"entity": entity} if entity else {})

    async def get_cross_system_effects(self, operation: str) -> Dict[str, Any]:
        return await self.call("get_cross_system_effects", {"operation": operation})

    async def get_field_context(self, entity: str, field: str) -> Dict[str, Any]:
        return await self.call("get_field_context", {"entity": entity, "field": field})

    async def get_state_transitions(self, entity_field: str, current_state: Optional[str] = None) -> Dict[str, Any]:
        args: Dict[str, Any] = {"entity_field": entity_field}
        if current_state:
            args["current_state"] = current_state
        return await self.call("get_state_transitions", args)

    # -- deterministic verification + codegen (v1.1) ---------------------
    async def list_loaded_stores(self) -> Dict[str, Any]:
        return await self.call("list_loaded_stores")

    async def list_state_machines(self) -> Dict[str, Any]:
        return await self.call("list_state_machines")

    async def validate_transition(self, entity_field: str, from_: str, to: str) -> Dict[str, Any]:
        return await self.call("validate_transition", {"entity_field": entity_field, "from": from_, "to": to})

    async def validate_payload(self, entity: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self.call("validate_payload", {"entity": entity, "payload": payload})

    async def get_entity_schema(self, entity: str) -> Dict[str, Any]:
        return await self.call("get_entity_schema", {"entity": entity})

    async def get_entity_contract(self, entity: str) -> Dict[str, Any]:
        return await self.call("get_entity_contract", {"entity": entity})

    async def check_plan_footguns(self, plan: str, entity: Optional[str] = None) -> Dict[str, Any]:
        args: Dict[str, Any] = {"plan": plan}
        if entity:
            args["entity"] = entity
        return await self.call("check_plan_footguns", args)

    async def search_logic(self, query: str) -> Dict[str, Any]:
        return await self.call("search_logic", {"query": query})

    async def generate_transition_guard(self, entity_field: str) -> Dict[str, Any]:
        return await self.call("generate_transition_guard", {"entity_field": entity_field})


_bridge = BusinessLogicBridge()


def close() -> None:
    """Disconnect the BLMCP subprocess (call at shutdown)."""
    try:
        _call(_bridge.client.disconnect(), timeout=5)
    except Exception:
        pass


def biz_get_rules(entity: str) -> Dict[str, Any]:
    return _call(_bridge.get_entity_rules(entity))


def biz_get_footguns(entity: Optional[str] = None) -> Dict[str, Any]:
    return _call(_bridge.get_footguns(entity))


def biz_get_effects(operation: str) -> Dict[str, Any]:
    return _call(_bridge.get_cross_system_effects(operation))


def biz_validate_payload(entity: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return _call(_bridge.validate_payload(entity, payload))


def biz_validate_transition(entity_field: str, from_: str, to: str) -> Dict[str, Any]:
    return _call(_bridge.validate_transition(entity_field, from_, to))


def biz_entity_contract(entity: str) -> Dict[str, Any]:
    return _call(_bridge.get_entity_contract(entity))


def biz_check_plan_footguns(plan: str, entity: Optional[str] = None) -> Dict[str, Any]:
    return _call(_bridge.check_plan_footguns(plan, entity))


def biz_transition_guard(entity_field: str) -> Dict[str, Any]:
    return _call(_bridge.generate_transition_guard(entity_field))


def biz_entity_schema(entity: str) -> Dict[str, Any]:
    return _call(_bridge.get_entity_schema(entity))