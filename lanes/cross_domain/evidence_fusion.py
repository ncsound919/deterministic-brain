from __future__ import annotations

def fuse_evidence(contexts: list, signals: list) -> dict:
    sources = list({c.get('source', 'unknown') for c in contexts})
    return {
        'sources': sources, 'signal_count': len(signals),
        'fusion_strength': min(1.0, round(len(signals) * 0.15 + len(sources) * 0.1, 3)),
        'fused_signals': signals,
    }
