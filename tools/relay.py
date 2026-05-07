"""relay.py — replaces tap919-middleman as a lean Python agent relay.

Responsibilities (distilled from tap919-middleman docs):
  1. Sign outgoing agent requests with an HMAC-SHA256 signature
  2. Verify incoming signatures before forwarding to deterministic-brain
  3. Route named agents to their registered base URLs
  4. Forward the request and return the response
  5. Log every hop to traces.db

No Express, no Node, no separate service.
Runs inside the same FastAPI process as tools/relay.py endpoints,
or standalone: python -m tools.relay
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import time
import urllib.request
import urllib.error
from typing import Dict, Optional

from tools.tracing import log_event

# ── Config ───────────────────────────────────────────────────────────
SECRET_KEY = os.environ.get("RELAY_SECRET", "dca-relay-secret-change-me")

# Agent registry: name → base URL
# Override via RELAY_AGENTS env var as JSON string:
# RELAY_AGENTS='{"browser-harness": "http://localhost:8001"}'
_DEFAULT_AGENTS: Dict[str, str] = {
    "deterministic-brain": "http://localhost:8000",
    "browser-harness":     "http://localhost:8001",
    "repoforge":           "http://localhost:8002",
}

try:
    _AGENTS: Dict[str, str] = {
        **_DEFAULT_AGENTS,
        **json.loads(os.environ.get("RELAY_AGENTS", "{}")),
    }
except Exception:
    _AGENTS = dict(_DEFAULT_AGENTS)


# ── Signing ──────────────────────────────────────────────────────────

def _sign(payload: bytes, ts: str) -> str:
    """HMAC-SHA256(secret, timestamp + '.' + payload)"""
    msg = ts.encode() + b"." + payload
    return hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()


def sign_request(body: Dict) -> Dict:
    """Return body with added _sig and _ts fields."""
    ts      = str(int(time.time()))
    payload = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    sig     = _sign(payload, ts)
    return {**body, "_ts": ts, "_sig": sig}


def verify_request(body: Dict, max_age_s: int = 30) -> bool:
    """Return True if signature is valid and request is fresh."""
    ts  = body.get("_ts", "")
    sig = body.get("_sig", "")
    if not ts or not sig:
        return False
    # freshness check
    if abs(time.time() - int(ts)) > max_age_s:
        return False
    clean   = {k: v for k, v in body.items() if k not in ("_ts", "_sig")}
    payload = json.dumps(clean, separators=(",", ":"), sort_keys=True).encode()
    expected = _sign(payload, ts)
    return hmac.compare_digest(expected, sig)


# ── Routing + forwarding ───────────────────────────────────────────────

class AgentRelay:
    """
    Central relay point. External callers POST to /relay with:
      { "agent": "deterministic-brain", "path": "/task",
        "method": "POST", "body": {...} }

    The relay:
      1. Optionally verifies an inbound signature
      2. Looks up the agent's base URL
      3. Signs the outbound body
      4. Forwards via urllib (no extra deps)
      5. Returns the downstream response
      6. Logs the hop
    """

    def __init__(self, agents: Optional[Dict[str, str]] = None):
        self.agents = agents or _AGENTS

    def register(self, name: str, base_url: str) -> None:
        self.agents[name] = base_url.rstrip("/")

    def forward(
        self,
        agent:  str,
        path:   str,
        body:   Dict,
        method: str = "POST",
        verify_inbound: bool = False,
    ) -> Dict:
        base = self.agents.get(agent)
        if not base:
            return {"error": f"Unknown agent: '{agent}'"}

        if verify_inbound and not verify_request(body):
            return {"error": "Invalid or expired inbound signature"}

        # strip relay meta fields before forwarding
        clean_body = {k: v for k, v in body.items()
                      if k not in ("_ts", "_sig", "agent", "path", "method")}
        signed = sign_request(clean_body)

        url     = base.rstrip("/") + "/" + path.lstrip("/")
        payload = json.dumps(signed).encode()
        req     = urllib.request.Request(
            url, data=payload, method=method,
            headers={"Content-Type": "application/json"},
        )

        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_body = json.loads(resp.read().decode())
                elapsed   = round((time.perf_counter() - t0) * 1000)
                log_event("relay", {
                    "agent": agent, "path": path,
                    "status": "ok", "ms": elapsed,
                })
                return resp_body
        except urllib.error.HTTPError as exc:
            body_err = exc.read().decode(errors="ignore")
            log_event("relay", {"agent": agent, "path": path,
                                "status": "error", "code": exc.code})
            return {"error": f"HTTP {exc.code}", "detail": body_err}
        except Exception as exc:
            log_event("relay", {"agent": agent, "path": path,
                                "status": "error", "detail": str(exc)})
            return {"error": str(exc)}

    def broadcast(self, path: str, body: Dict) -> Dict:
        """Forward to ALL registered agents in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = {}
        with ThreadPoolExecutor(max_workers=len(self.agents)) as pool:
            futures = {
                pool.submit(self.forward, name, path, body): name
                for name in self.agents
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as exc:
                    results[name] = {"error": str(exc)}
        return results


# ── Singleton ───────────────────────────────────────────────────────────
relay = AgentRelay()


# ── Standalone CLI ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(description="DCA Agent Relay")
    parser.add_argument("--agent",  required=True, help="Agent name")
    parser.add_argument("--path",   default="/task")
    parser.add_argument("--body",   default="{}", help="JSON body")
    parser.add_argument("--method", default="POST")
    parser.add_argument("--list",   action="store_true", help="List agents")
    args = parser.parse_args()
    if args.list:
        for k, v in relay.agents.items():
            print(f"  {k:30s}  {v}")
        sys.exit(0)
    result = relay.forward(args.agent, args.path, json.loads(args.body), args.method)
    print(json.dumps(result, indent=2))
