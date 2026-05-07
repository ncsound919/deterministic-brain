"""Request logging middleware — tracks latency, payload size, error rates.

Feeds into the Dashboard event feed and EventBus for cross-system tracking.
"""

from __future__ import annotations
import time
import json
from typing import Dict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from orchestration.event_bus import event_bus


# In-memory stats (survives between requests but not restarts)
_route_stats: Dict[str, Dict] = {}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request to the EventBus and tracks per-route stats."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.time()
        route = _route_key(request)

        response = await call_next(request)

        elapsed_ms = (time.time() - start) * 1000
        status_code = response.status_code
        content_length = response.headers.get("content-length", "0")

        # Persist to event bus
        event_bus.emit("http_request", route=route, method=request.method,
                       status=status_code, elapsed_ms=round(elapsed_ms, 1),
                       content_length=int(content_length or 0))

        # Update in-memory per-route stats
        if route not in _route_stats:
            _route_stats[route] = {"count": 0, "errors": 0, "total_ms": 0.0, "total_bytes": 0}
        stats = _route_stats[route]
        stats["count"] += 1
        stats["total_ms"] += elapsed_ms
        stats["total_bytes"] += int(content_length or 0)
        if status_code >= 400:
            stats["errors"] += 1

        return response


def get_route_stats() -> Dict:
    """Return per-route aggregated stats (for dashboard)."""
    result = {}
    for route, stats in _route_stats.items():
        count = stats["count"]
        result[route] = {
            "count": count,
            "errors": stats["errors"],
            "error_rate": round(stats["errors"] / max(count, 1), 4),
            "avg_latency_ms": round(stats["total_ms"] / max(count, 1), 1),
            "total_bytes": stats["total_bytes"],
        }
    return result


def _route_key(request: Request) -> str:
    """Normalize route patterns like /devpets/abc123 -> /devpets/{id}."""
    path = request.url.path.rstrip("/") or "/"
    # Simple heuristic: collapse UUID-like segments
    import re
    path = re.sub(r"/[a-f0-9]{8,}", "/{id}", path)
    path = re.sub(r"/\d{4}-\d{2}-\d{2}", "/{date}", path)
    return f"{request.method} {path}"
