from __future__ import annotations
from hashlib import sha256
from random import Random

def rank_candidates(query: str, candidates: list) -> list:
    seed = int(sha256(query.encode()).hexdigest()[:16], 16)
    rng = Random(seed)
    scored = []
    for c in candidates:
        out = dict(c)
        out['score'] = round(0.8 + rng.random() * 0.19, 4)
        scored.append(out)
    return sorted(scored, key=lambda x: (-x['score'], x.get('id', '')))
