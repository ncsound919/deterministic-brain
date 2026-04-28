from __future__ import annotations
from schemas.state import ContextItem

def retrieve(query: str, lane: str) -> list:
    return [
        {'source': 'kb', 'id': 'ctx1', 'text': lane + ' context for: ' + query, 'score': 0.92, 'metadata': {'lane': lane}},
        {'source': 'graph', 'id': 'ctx2', 'text': lane + ' linked evidence', 'score': 0.87, 'metadata': {'lane': lane}},
    ]
