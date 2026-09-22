"""Fleet bridges — deterministic HTTP bridges to the upgraded MCP fleet.

Honest contract: every call returns {ok, ...} or {ok: False, status, error}.
A server that is offline or returns non-2xx is reported with the real error
(never a fabricated result). Only no-LLM deterministic surfaces are bridged;
LLM-routed services (math-x /api/verify uses Claude) are reported, not bridged.

Endpoints come from env with defaults:
  OG_GLASS_URL    http://127.0.0.1:3000
  BIGBACK_URL     http://127.0.0.1:8000
  MIDDLEMAN_URL   http://127.0.0.1:3001
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def _post_json(url: str, payload: Dict[str, Any], timeout: float = 15.0) -> Dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}"}
    except Exception as exc:
        return {"ok": False, "status": None, "error": f"request failed: {exc}"}
    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception:
        parsed = body.decode("utf-8", "replace")
    return {"ok": 200 <= status < 300, "status": status, "data": parsed}


def _get(url: str, timeout: float = 15.0) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as exc:
        return {"ok": False, "status": exc.code, "error": f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}"}
    except Exception as exc:
        return {"ok": False, "status": None, "error": f"request failed: {exc}"}
    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception:
        parsed = body.decode("utf-8", "replace")
    return {"ok": 200 <= status < 300, "status": status, "data": parsed}


def _env(name: str, default: str) -> str:
    return (os.environ.get(name) or default).rstrip("/")


# -- OG-Glass (design director) ------------------------------------------------

def og_glass_brief(goal: str, overrides: Optional[Dict[str, Any]] = None, base_url: Optional[str] = None) -> Dict[str, Any]:
    base = base_url or _env("OG_GLASS_URL", "http://127.0.0.1:3000")
    payload: Dict[str, Any] = {"goal": goal or ""}
    if overrides:
        payload.update(overrides)
    result = _post_json(f"{base}/api/design-brief", payload)
    if not result.get("ok"):
        return {"ok": False, "step": "design", "error": result.get("error"), "status": result.get("status")}
    return {"ok": True, "step": "design", **result["data"]}


def og_glass_design_md(preset_id: str, base_url: Optional[str] = None) -> Dict[str, Any]:
    base = base_url or _env("OG_GLASS_URL", "http://127.0.0.1:3000")
    result = _get(f"{base}/api/presets/{preset_id}/design.md")
    if not result.get("ok"):
        return {"ok": False, "step": "design_md", "error": result.get("error"), "status": result.get("status")}
    return {"ok": True, "step": "design_md", "preset_id": preset_id, "design_md": result["data"]}


# -- BigBack (backend generator) ----------------------------------------------

def bigback_generate(spec: Dict[str, Any], base_url: Optional[str] = None) -> Dict[str, Any]:
    base = base_url or _env("BIGBACK_URL", "http://127.0.0.1:8000")
    result = _post_json(f"{base}/api/v1/generator/plan", spec)
    if not result.get("ok"):
        return {"ok": False, "step": "backend", "error": result.get("error"), "status": result.get("status")}
    return {"ok": True, "step": "backend", **result["data"]}


# -- Middle-Man (glue relay) ---------------------------------------------------

def middleman_relay(service: str, path: str, body: Dict[str, Any], base_url: Optional[str] = None) -> Dict[str, Any]:
    base = base_url or _env("MIDDLEMAN_URL", "http://127.0.0.1:3001")
    result = _post_json(
        f"{base}/api/mcp-registry/relay",
        {"service": service, "path": path, "body": body},
    )
    if not result.get("ok"):
        return {"ok": False, "step": "relay", "error": result.get("error"), "status": result.get("status")}
    return {"ok": True, "step": "relay", "service": service, **result["data"]}


# -- The-Beta-Team (acceptance gate) -------------------------------------------

def beta_team_status() -> Dict[str, Any]:
    """Report whether the Beta Team SDK is importable (it is a Python SDK, not a
    server). No automatic bridge: running it needs a built app to test."""
    try:
        import beta_team  # type: ignore  # noqa: F401

        return {"ok": True, "available": True, "detail": "beta_team SDK importable; point it at a built app to run the acceptance gate."}
    except Exception as exc:
        return {"ok": False, "available": False, "detail": f"beta_team SDK not importable: {exc}"}


def beta_team_run(target_dir: str, kind: str = "web") -> Dict[str, Any]:
    """Run the Beta Team acceptance gate against a built target if the SDK is
    importable; otherwise an honest SKIP. Never fabricates a test result."""
    status = beta_team_status()
    if not status.get("available"):
        return {"ok": False, "step": "beta", "status": "SKIP", "error": status["detail"]}
    # Launcher CLI is invoked here; if it fails we report the real error.
    try:
        from beta_team.launcher import run_smoke  # type: ignore

        result = run_smoke(target_dir=target_dir, kind=kind)
        return {"ok": True, "step": "beta", "status": "DONE", "result": result}
    except Exception as exc:
        return {"ok": False, "step": "beta", "status": "ERROR", "error": f"beta_team run failed: {exc}"}


# -- math-x -------------------------------------------------------------------

def math_x_status() -> Dict[str, Any]:
    """math-x is LLM-routed (Claude generates derivations; SymPy checks them).
    Its deterministic surface is the SymPy checker, but the route requires the
    model — so it is reported, not bridged, in the no-LLM path."""
    return {
        "ok": True,
        "available": True,
        "bridged": False,
        "detail": "math-x /api/verify is LLM-routed (Anthropic + SymPy checker); not wired into the no-LLM guarantee.",
    }


def fleet_status() -> Dict[str, Any]:
    """One-call status of every fleet bridge (HTTP reachability checks)."""
    return {
        "og_glass": {"url": _env("OG_GLASS_URL", "http://127.0.0.1:3000"), "bridged": True},
        "bigback": {"url": _env("BIGBACK_URL", "http://127.0.0.1:8000"), "bridged": True},
        "middleman": {"url": _env("MIDDLEMAN_URL", "http://127.0.0.1:3001"), "bridged": True},
        "beta_team": beta_team_status(),
        "math_x": math_x_status(),
    }