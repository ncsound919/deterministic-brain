"""Real Estate Leads Lane — drive House Flip Studio's MCP tools.

Calls the House Flip Studio MCP endpoint (``/api/mcp``, JSON-RPC 2.0) to run an
autonomous distressed-property hunt and pull the scored leads back into the
brain. This lane is the bridge between the DCA swarm and the House Flip control
plane; it deliberately does NOT reimplement the search, scoring, or dossier
logic — House Flip already owns that, and duplicating it here would drift.

Configuration (environment):
  HOUSE_FLIP_API_URL      base URL of the House Flip Studio deployment
                          (default http://localhost:3000)
  HOUSE_FLIP_MCP_SECRET   bearer secret for /api/mcp (falls back to
                          HOUSE_FLIP_CRON_SECRET, then unauthenticated)
  HOUSE_FLIP_ORG_ID       default org id when the task omits one

Task inputs (``state['task']``):
  action                  "hunt" (default) | "list" | "dossier"
  org_id                  organization id (required for hunt/list)
  statewide               bool
  counties                list[str]
  max_total               int
  require_distress        bool
  max_purchase_price      number
  tier                    "hot" | "warm" | "cold"   (action="list")
  limit                   int                        (action="list")
  address, pin, deal_id   strings                    (action="dossier")

Honesty: the lane reports exactly what House Flip returned. When the endpoint
is unreachable, or the tool reports an error, the lane marks the run failed with
the real reason — it never fabricates a lead.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "http://localhost:3000"
DEFAULT_TIMEOUT = 180  # a statewide sweep can outlast the default 30s client cap

TOOL_FOR_ACTION = {
    "hunt": "hunt_leads",
    "list": "list_leads",
    "dossier": "build_dossier",
}


def _env_secret() -> str:
    return os.getenv("HOUSE_FLIP_MCP_SECRET") or os.getenv("HOUSE_FLIP_CRON_SECRET") or ""


def _resolve_base_url(task: Dict[str, Any]) -> str:
    url = task.get("house_flip_url") or os.getenv("HOUSE_FLIP_API_URL") or DEFAULT_BASE_URL
    return str(url).rstrip("/")


def _post_json(url: str, payload: Dict[str, Any], secret: str, timeout: int = DEFAULT_TIMEOUT) -> Dict[str, Any]:
    """POST a JSON body. Returns ``{"ok": bool, ...}`` and never raises on HTTP/network errors."""
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    body = json.dumps(payload).encode("utf-8")
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return {"ok": True, "status": resp.status, "data": json.loads(raw)}
    except HTTPError as e:
        return {"ok": False, "status": e.code, "error": f"HTTP {e.code}: {e.reason}"}
    except (URLError, TimeoutError, OSError) as e:
        return {"ok": False, "status": 0, "error": f"unreachable: {e}"}
    except json.JSONDecodeError:
        return {"ok": False, "status": 0, "error": "invalid JSON response"}


def call_tool(
    name: str,
    arguments: Dict[str, Any],
    base_url: str,
    secret: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Invoke a House Flip MCP tool. Returns ``{"ok", "data"}`` or ``{"ok": False, "error"}``."""
    rpc = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    resp = _post_json(f"{base_url}/api/mcp", rpc, secret, timeout)
    if not resp.get("ok"):
        return {"ok": False, "error": resp.get("error", "request failed")}

    envelope = resp.get("data") or {}
    if isinstance(envelope, dict) and envelope.get("error"):
        message = envelope["error"].get("message", "rpc error") if isinstance(envelope["error"], dict) else str(envelope["error"])
        return {"ok": False, "error": message}

    result = envelope.get("result") if isinstance(envelope, dict) else None
    if not isinstance(result, dict):
        return {"ok": False, "error": "malformed MCP result"}

    data = result.get("structuredContent")
    if data is None:
        data = _first_text(result)

    if result.get("isError"):
        return {"ok": False, "error": _as_error_text(data)}
    return {"ok": True, "data": data}


def _first_text(result: Dict[str, Any]) -> Any:
    content = result.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict):
            return first.get("text")
    return None


def _as_error_text(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("error"), str):
        return data["error"]
    if isinstance(data, str) and data:
        return data
    return "tool reported an error"


def _build_arguments(action: str, task: Dict[str, Any]) -> Dict[str, Any]:
    org_id = task.get("org_id") or os.getenv("HOUSE_FLIP_ORG_ID") or ""
    if action == "hunt":
        args: Dict[str, Any] = {"org_id": org_id}
        for key in ("statewide", "counties", "max_total", "require_distress", "max_purchase_price"):
            if task.get(key) is not None:
                args[key] = task[key]
        return args
    if action == "list":
        args = {"org_id": org_id}
        for key in ("tier", "limit"):
            if task.get(key) is not None:
                args[key] = task[key]
        return args
    # dossier
    args = {"address": task.get("address", "")}
    for key in ("pin", "deal_id", "min_assessed", "max_assessed"):
        if task.get(key) is not None:
            args[key] = task[key]
    return args


def _format_hunt(data: Dict[str, Any]) -> str:
    tiers = data.get("tiers") or {}
    summary = data.get("summary") or []
    warnings: List[str] = data.get("warnings") or []
    lines = [
        "# Distressed Property Hunt",
        "",
        f"Scanned: {data.get('scanned', 0)}",
        f"New leads: {data.get('newLeads', 0)}",
        f"Duplicates: {data.get('duplicates', 0)}",
        f"Filtered: {data.get('filtered', 0)}",
        f"Tiers: hot={tiers.get('hot', 0)} warm={tiers.get('warm', 0)} cold={tiers.get('cold', 0)}",
    ]
    reasons = data.get("filterReasons") or {}
    if reasons:
        lines.append("Filter reasons: " + ", ".join(f"{k}={v}" for k, v in reasons.items()))
    if summary:
        lines.append("")
        lines.append("## By county")
        for row in summary[:25]:
            lines.append(f"- {row.get('county', '?')}: {row.get('houses', 0)}")
    if warnings:
        lines.append("")
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")
    return "\n".join(lines)


def _format_list(data: Dict[str, Any]) -> str:
    leads = data.get("leads") or []
    lines = ["# Stored Leads", "", f"Count: {data.get('count', len(leads))}", ""]
    for lead in leads:
        lines.append(
            f"- [{str(lead.get('tier', '?')).upper()}] {lead.get('address', '?')} "
            f"(score {lead.get('attentionScore', '?')}, {lead.get('rating', '?')})"
        )
    if not leads:
        lines.append("No leads matched.")
    return "\n".join(lines)


def _format_dossier(data: Dict[str, Any]) -> str:
    sources = data.get("sources") or []
    lines = ["# Research Dossier", "", f"Address: {data.get('dealId', '')}", ""]
    for src in sources:
        lines.append(f"- {src.get('source', '?')}: {src.get('status', '?')}")
    return "\n".join(lines)


_FORMATTERS = {"hunt": _format_hunt, "list": _format_list, "dossier": _format_dossier}


def run(state: dict) -> dict:
    """Execute a House Flip action and fold the outcome into the brain state."""
    task: Dict[str, Any] = state.get("task", {}) or {}
    query = state.get("query", "")
    action = str(task.get("action") or "hunt").lower()
    if action not in TOOL_FOR_ACTION:
        action = "hunt"

    verification = state.setdefault("verification_results", [])
    history = state.setdefault("history", [])

    org_id = task.get("org_id") or os.getenv("HOUSE_FLIP_ORG_ID") or ""
    if action in ("hunt", "list") and not org_id:
        reason = "org_id is required (task.org_id or HOUSE_FLIP_ORG_ID)"
        return _finish(
            state,
            action,
            ok=False,
            reason=reason,
            report=f"# Real Estate Leads — {action}\n\nFailed: {reason}",
            verification=verification,
            history=history,
            confidence=0.1,
        )

    base_url = _resolve_base_url(task)
    secret = _env_secret()
    arguments = _build_arguments(action, task)
    result = call_tool(TOOL_FOR_ACTION[action], arguments, base_url, secret)

    if not result.get("ok"):
        return _finish(
            state,
            action,
            ok=False,
            reason=result.get("error", "tool failed"),
            report=f"# Real Estate Leads — {action}\n\nFailed: {result.get('error', 'tool failed')}",
            verification=verification,
            history=history,
            confidence=0.2,
        )

    data = result.get("data")
    if not isinstance(data, dict):
        data = {"raw": data}
    report = _FORMATTERS[action](data)

    # Confident only when the run produced something real. A hunt that scanned
    # but found nothing new is honest and lower-confidence, not a failure.
    if action == "hunt":
        confidence = 0.9 if data.get("newLeads", 0) > 0 else 0.55
    elif action == "list":
        confidence = 0.85 if data.get("count", 0) > 0 else 0.5
    else:
        confidence = 0.8

    return _finish(
        state,
        action,
        ok=True,
        reason="completed",
        report=report,
        verification=verification,
        history=history,
        confidence=confidence,
        data=data,
        query=query,
        org_id=org_id,
    )


def _finish(
    state: dict,
    action: str,
    *,
    ok: bool,
    reason: str,
    report: str,
    verification: list,
    history: list,
    confidence: float,
    data: Any = None,
    query: str = "",
    org_id: str = "",
) -> dict:
    artifact: Dict[str, Any] = {
        "id": f"house-flip-{action}",
        "kind": "report",
        "content": report,
    }
    if data is not None:
        artifact["data"] = data
    state["candidate_artifacts"] = [artifact]

    verification.append(
        {
            "stage": f"real_estate_{action}",
            "passed": ok,
            "reason": reason,
            "details": data if data is not None else {"error": reason},
        }
    )
    state["final_output"] = report
    state["output_mode"] = "text"
    state["confidence"] = confidence
    history.append({"lane": "real_estate_leads", "action": action, "ok": ok, "org_id": org_id, "query": query})
    return state
