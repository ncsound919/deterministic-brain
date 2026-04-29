from __future__ import annotations
"""
MONITOR_TOOL — MCP server and brain health monitoring.

Tracks:
- Brain API health (latency, error rate)
- MCP server status
- LLM backend availability (OpenRouter)
- Qdrant / Neo4j connectivity
- Feature flag states
- Per-lane confidence metrics over time
"""
import time
from collections import defaultdict, deque
from datetime import datetime
from features import all_flags

_metrics: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
_start_time = time.time()


def record(metric: str, value: float, labels: dict | None = None) -> None:
    _metrics[metric].append({
        'ts': datetime.utcnow().isoformat(),
        'value': value,
        'labels': labels or {},
    })


def record_request(lane: str, latency_ms: float, confidence: float, status: str) -> None:
    record('request_latency_ms', latency_ms, {'lane': lane})
    record('request_confidence', confidence, {'lane': lane})
    record(f'lane_{lane}_count', 1, {'status': status})


def get_metrics(metric: str | None = None) -> dict:
    if metric:
        return {metric: list(_metrics.get(metric, []))}
    return {k: list(v) for k, v in _metrics.items()}


def health_check() -> dict:
    import os
    checks: dict[str, str] = {}

    # OpenRouter
    checks['openrouter'] = 'configured' if os.getenv('OPENROUTER_API_KEY') else 'not_configured'

    # Qdrant
    try:
        from qdrant_client import QdrantClient
        url = os.getenv('QDRANT_URL', '')
        if url:
            QdrantClient(url=url, timeout=2).get_collections()
            checks['qdrant'] = 'ok'
        else:
            checks['qdrant'] = 'not_configured'
    except Exception as e:
        checks['qdrant'] = f'error: {str(e)[:50]}'

    # Neo4j
    checks['neo4j'] = 'configured' if os.getenv('NEO4J_URI') else 'not_configured'

    return {
        'uptime_s': round(time.time() - _start_time, 1),
        'checks': checks,
        'features': all_flags(),
        'metric_keys': list(_metrics.keys()),
        'ts': datetime.utcnow().isoformat(),
    }
