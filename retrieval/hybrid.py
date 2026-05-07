from __future__ import annotations
import os
import hashlib
from typing import Any

# ---------------------------------------------------------------------------
# Optional backend imports — gracefully degrade if not installed
# ---------------------------------------------------------------------------
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue, SearchRequest
    _QDRANT_OK = True
except ImportError:
    _QDRANT_OK = False

try:
    from neo4j import GraphDatabase
    _NEO4J_OK = True
except ImportError:
    _NEO4J_OK = False

try:
    from tavily import TavilyClient
    _TAVILY_OK = True
except ImportError:
    _TAVILY_OK = False


# ---------------------------------------------------------------------------
# Client singletons — lazy, only created when env vars are present
# ---------------------------------------------------------------------------

def _qdrant_client() -> Any | None:
    url = os.getenv('QDRANT_URL')
    key = os.getenv('QDRANT_API_KEY')
    if _QDRANT_OK and url:
        return QdrantClient(url=url, api_key=key)
    return None


def _neo4j_driver() -> Any | None:
    uri = os.getenv('NEO4J_URI')
    user = os.getenv('NEO4J_USER', 'neo4j')
    pwd = os.getenv('NEO4J_PASSWORD', '')
    if _NEO4J_OK and uri:
        return GraphDatabase.driver(uri, auth=(user, pwd))
    return None


def _tavily_client() -> Any | None:
    key = os.getenv('TAVILY_API_KEY')
    if _TAVILY_OK and key:
        return TavilyClient(api_key=key)
    return None


# ---------------------------------------------------------------------------
# Lane → Qdrant collection mapping
# ---------------------------------------------------------------------------

_COLLECTION_MAP: dict[str, str] = {
    'coding': 'code_kb',
    'business_logic': 'policy_kb',
    'agent_brain': 'agent_kb',
    'tool_calling': 'tools_kb',
    'cross_domain': 'general_kb',
}

_TOP_K = int(os.getenv('RETRIEVAL_TOP_K', '5'))
_GRAPH_DEPTH = int(os.getenv('NEO4J_DEPTH', '1'))
_TAVILY_MAX = int(os.getenv('TAVILY_MAX_RESULTS', '3'))


# ---------------------------------------------------------------------------
# Embedding stub — replace with real model (e.g. sentence-transformers)
# ---------------------------------------------------------------------------

def _embed(text: str) -> list[float]:
    """Deterministic pseudo-embedding using SHA-256 bytes (128-dim).
    Replace with a real encoder (sentence-transformers, ONNX, etc.) when
    a model is available.  The interface contract is identical.
    """
    digest = hashlib.sha256(text.encode()).digest()  # 32 bytes
    # Repeat to reach 128 dims, normalise to [-1, 1]
    raw = list(digest * 4)
    norm = [((b / 127.5) - 1.0) for b in raw]
    return norm


# ---------------------------------------------------------------------------
# Qdrant vector search
# ---------------------------------------------------------------------------

def _qdrant_search(query: str, lane: str) -> list[dict]:
    client = _qdrant_client()
    if client is None:
        return []
    collection = _COLLECTION_MAP.get(lane, 'general_kb')
    try:
        vec = _embed(query)
        hits = client.search(
            collection_name=collection,
            query_vector=vec,
            limit=_TOP_K,
            with_payload=True,
        )
        results = []
        for h in hits:
            payload = h.payload or {}
            results.append({
                'source': 'qdrant',
                'id': str(h.id),
                'text': payload.get('text', payload.get('content', str(payload))),
                'score': round(float(h.score), 4),
                'metadata': {
                    'lane': lane,
                    'collection': collection,
                    **{k: v for k, v in payload.items() if k not in ('text', 'content')},
                },
            })
        return results
    except Exception as exc:  # noqa: BLE001
        return [{'source': 'qdrant_error', 'id': 'err', 'text': str(exc),
                 'score': 0.0, 'metadata': {'lane': lane}}]


# ---------------------------------------------------------------------------
# Neo4j graph expansion
# ---------------------------------------------------------------------------

def _neo4j_expand(node_ids: list[str], lane: str) -> list[dict]:
    driver = _neo4j_driver()
    if driver is None or not node_ids:
        return []
    results = []
    try:
        with driver.session() as session:
            for nid in node_ids[:3]:  # limit blast radius
                cypher = (
                    f'MATCH (n {{id: $nid}})-[*1..{_GRAPH_DEPTH}]-(m) '
                    'RETURN m.id AS mid, m.text AS text, m.label AS label LIMIT 5'
                )
                for rec in session.run(cypher, nid=nid):
                    results.append({
                        'source': 'neo4j',
                        'id': str(rec['mid']),
                        'text': rec.get('text', ''),
                        'score': 0.75,
                        'metadata': {'lane': lane, 'label': rec.get('label', '')},
                    })
    except Exception as exc:  # noqa: BLE001
        results.append({'source': 'neo4j_error', 'id': 'err', 'text': str(exc),
                        'score': 0.0, 'metadata': {'lane': lane}})
    finally:
        driver.close()
    return results


# ---------------------------------------------------------------------------
# Tavily web search (live knowledge fallback)
# ---------------------------------------------------------------------------

_TAVILY_LANES = {'cross_domain', 'agent_brain'}


def _tavily_search(query: str, lane: str) -> list[dict]:
    if lane not in _TAVILY_LANES:
        return []
    client = _tavily_client()
    if client is None:
        return []
    try:
        resp = client.search(query=query, max_results=_TAVILY_MAX, include_answer=False)
        results = []
        for r in resp.get('results', []):
            results.append({
                'source': 'tavily',
                'id': hashlib.md5(r.get('url', '').encode()).hexdigest()[:12],
                'text': r.get('content', r.get('snippet', '')),
                'score': round(float(r.get('score', 0.7)), 4),
                'metadata': {
                    'lane': lane,
                    'url': r.get('url', ''),
                    'title': r.get('title', ''),
                    'published_date': r.get('published_date', ''),
                },
            })
        return results
    except Exception as exc:  # noqa: BLE001
        return [{'source': 'tavily_error', 'id': 'err', 'text': str(exc),
                 'score': 0.0, 'metadata': {'lane': lane}}]


# ---------------------------------------------------------------------------
# Static fallback corpus (used when no backends are configured)
# ---------------------------------------------------------------------------

_STATIC_CORPUS: dict[str, list[dict]] = {
    'coding': [
        {'source': 'kb', 'id': 'c1', 'text': 'Python best practice: use type hints on all public functions.',
         'score': 0.91, 'metadata': {'lane': 'coding', 'tag': 'style'}},
        {'source': 'kb', 'id': 'c2', 'text': 'Write unit tests using pytest; aim for >80% branch coverage.',
         'score': 0.88, 'metadata': {'lane': 'coding', 'tag': 'testing'}},
    ],
    'business_logic': [
        {'source': 'kb', 'id': 'b1', 'text': 'All budget requests over $50k require CFO approval.',
         'score': 0.93, 'metadata': {'lane': 'business_logic', 'tag': 'approval'}},
        {'source': 'kb', 'id': 'b2', 'text': 'Compliance check: GDPR data retention max 24 months.',
         'score': 0.89, 'metadata': {'lane': 'business_logic', 'tag': 'compliance'}},
    ],
    'agent_brain': [
        {'source': 'kb', 'id': 'a1', 'text': 'Browser agent must never click unverified external links.',
         'score': 0.90, 'metadata': {'lane': 'agent_brain', 'tag': 'safety'}},
        {'source': 'kb', 'id': 'a2', 'text': 'All page navigation actions require policy pre-approval.',
         'score': 0.85, 'metadata': {'lane': 'agent_brain', 'tag': 'policy'}},
    ],
    'tool_calling': [
        {'source': 'kb', 'id': 't1', 'text': 'Tool schema must be validated before execution; reject on schema mismatch.',
         'score': 0.92, 'metadata': {'lane': 'tool_calling', 'tag': 'validation'}},
        {'source': 'kb', 'id': 't2', 'text': 'Log all tool invocations with timestamp and result status.',
         'score': 0.86, 'metadata': {'lane': 'tool_calling', 'tag': 'logging'}},
    ],
    'cross_domain': [
        {'source': 'kb', 'id': 'x1', 'text': 'Cross-domain synthesis requires evidence from at least 2 distinct sources.',
         'score': 0.88, 'metadata': {'lane': 'cross_domain', 'tag': 'fusion'}},
        {'source': 'graph', 'id': 'x2', 'text': 'Trend signals must be corroborated by independent data points.',
         'score': 0.84, 'metadata': {'lane': 'cross_domain', 'tag': 'validation'}},
    ],
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def retrieve(query: str, lane: str) -> list[dict]:
    """Hybrid retrieval: Qdrant (vector) + Neo4j (graph) + Tavily (web).

    Falls back to a static corpus when no backends are configured so the
    system can run fully offline during development.
    """
    qdrant_results = _qdrant_search(query, lane)
    graph_results: list[dict] = []
    if qdrant_results:
        kb_ids = [r['id'] for r in qdrant_results if r['source'] == 'qdrant']
        graph_results = _neo4j_expand(kb_ids, lane)
    tavily_results = _tavily_search(query, lane)

    all_results = qdrant_results + graph_results + tavily_results

    # Fall back to static corpus if backends returned nothing
    if not all_results:
        all_results = list(_STATIC_CORPUS.get(lane, _STATIC_CORPUS['cross_domain']))

    # Deduplicate by id, keep highest score
    seen: dict[str, dict] = {}
    for r in all_results:
        rid = r['id']
        if rid not in seen or r['score'] > seen[rid]['score']:
            seen[rid] = r

    # Sort by score descending, cap at top-k
    ordered = sorted(seen.values(), key=lambda x: -x['score'])
    return ordered[:_TOP_K]
