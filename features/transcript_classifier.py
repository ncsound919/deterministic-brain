from __future__ import annotations
"""
TRANSCRIPT_CLASSIFIER — Auto-mode permission classifier.

Analyses every incoming query and classifies it across three dimensions:
1. LANE       — which processing lane to route to
2. RISK       — LOW / MEDIUM / HIGH
3. MODE       — INTERACTIVE / AUTONOMOUS / SUPERVISED

The classifications are cached and stored in the session state so the
permission layer and lane selector can use them without re-querying.
"""
from __future__ import annotations
import json
from tools.llm.router import chat

_SYSTEM = """Classify this query across three dimensions. Return JSON only.
{
  "lane": "coding|business_logic|agent_brain|tool_calling|cross_domain",
  "risk": "LOW|MEDIUM|HIGH",
  "mode": "INTERACTIVE|AUTONOMOUS|SUPERVISED",
  "requires_approval": true|false,
  "reason": "one sentence"
}"""

_CACHE: dict[str, dict] = {}


def classify(query: str) -> dict:
    if query in _CACHE:
        return _CACHE[query]
    raw = chat(system=_SYSTEM, user=query, lane='tool_calling', max_tokens=256)
    try:
        clean = raw.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        result = json.loads(clean)
    except Exception:
        result = {
            'lane': 'cross_domain',
            'risk': 'MEDIUM',
            'mode': 'INTERACTIVE',
            'requires_approval': False,
            'reason': 'Classification parse failed; using safe defaults.',
        }
    _CACHE[query] = result
    return result


def clear_cache() -> None:
    _CACHE.clear()
