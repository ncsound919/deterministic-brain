from __future__ import annotations
from hashlib import sha256
from random import Random

def score_trends(signals: list, seed_key: str = 'default') -> list:
    seed = int(sha256(seed_key.encode()).hexdigest()[:8], 16)
    rng = Random(seed)
    scored = []
    for signal in signals:
        scored.append({'signal': signal, 'strength': round(0.6 + rng.random() * 0.39, 3), 'novel': rng.random() > 0.5})
    return sorted(scored, key=lambda x: -x['strength'])
