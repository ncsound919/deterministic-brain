"""Request logging middleware — tracks latency, payload size, error rates.

Feeds into MetricsCollector for bucketed histograms and sliding-window error
rates, plus the Dashboard event feed and EventBus for cross-system tracking.
"""

from __future__ import annotations
import time
import re
from typing import Dict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from orchestration.event_bus import event_bus
from tools.metrics import get_metrics


# In-memory stats (survives between requests but not restarts)
_route_stats: Dict[str, Dict] = {}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request to EventBus + MetricsCollector."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.time()
        route = _route_key(request)

        response = await call_next(request)

        elapsed_ms = (time.time() - start) * 1000
        status_code = response.status_code
        content_length = response.headers.get("content-length", "0")

        # Record to MetricsCollector
        get_metrics().record_request(route, elapsed_ms, status_code)

        # Persist to event bus
        event_bus.emit("http_request", route=route, method=request.method,
                       status=status_code, elapsed_ms=round(elapsed_ms, 1),
                       content_length=int(content_length or 0))

        # Update in-memory per-route stats with cap to prevent memory leak
        if route not in _route_stats:
            if len(_route_stats) >= 1000:
                first_key = next(iter(_route_stats))
                _route_stats.pop(first_key)
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
    path = re.sub(r"/[a-f0-9]{8,}", "/{id}", path)
    path = re.sub(r"/\d{4}-\d{2}-\d{2}", "/{date}", path)
    return f"{request.method} {path}"
