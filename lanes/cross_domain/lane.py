from __future__ import annotations
from tools.llm.router import chat
from lanes.cross_domain.evidence_fusion import fuse_evidence
from lanes.cross_domain.trend_scorer import score_trends

_SYSTEM = """You are a cross-domain strategic analyst with expertise spanning technology, business, regulation, energy, labor, and climate.
Given a set of domain signals and retrieved evidence, produce a high-quality analytical synthesis.
Structure your response as:
LEADING_SIGNAL: <the single most impactful signal>
KEY_INSIGHTS:
- <insight 1>
- <insight 2>
- <insight 3>
CROSS_DOMAIN_CONNECTIONS: <how the signals interact with each other>
CONFIDENCE: <LOW | MEDIUM | HIGH>
IMPLICATIONS: <2-3 actionable implications>"""

_DOMAIN_SIGNALS = {
    'ai':         'AI capability shifts are altering automation costs, product velocity, and competitive positioning.',
    'supply':     'Supply chain pressure is affecting delivery timelines, pricing, and inventory strategy.',
    'regulation': 'Regulatory changes are increasing compliance overhead and limiting certain product categories.',
    'finance':    'Capital market conditions are affecting investment timing and startup runway expectations.',
    'energy':     'Energy pricing volatility is influencing data center costs and hardware procurement cycles.',
    'labor':      'Labor market shifts are changing how organizations balance automation and human execution.',
    'climate':    'Climate risk is beginning to influence infrastructure location decisions and insurance costs.',
}

def _detect_signals(query: str) -> list:
    q = query.lower()
    detected = [v for k, v in _DOMAIN_SIGNALS.items() if k in q]
    return detected if detected else list(_DOMAIN_SIGNALS.values())[:3]

def run(state: dict) -> dict:
    signals = _detect_signals(state['query'])
    fusion  = fuse_evidence(state.get('retrieved_contexts', []), signals)
    scored  = score_trends(signals, seed_key=state.get('query', 'default'))

    evidence_block = '\n'.join(f'  - {c.get("text", "")[:120]}' for c in state.get('retrieved_contexts', [])[:5])
    signals_block  = '\n'.join(f'  - {s}' for s in signals)
    user_msg = (
        f"Query: {state['query']}\n\n"
        f"Detected domain signals:\n{signals_block}\n\n"
        f"Retrieved evidence:\n{evidence_block if evidence_block else '  (none retrieved)'}\n\n"
        f"Fusion strength: {fusion['fusion_strength']}\n\n"
        "Produce the cross-domain synthesis."
    )

    synthesis = chat(system=_SYSTEM, user=user_msg, lane='cross_domain')

    top_signal = scored[0]['signal'] if scored else signals[0]
    candidate = {'id': 'x1', 'kind': 'cross_domain', 'content': synthesis,
                 'signals': signals, 'trend_scores': scored, 'fusion': fusion}
    state['candidate_artifacts'] = [candidate]
    state['working_memory']['cross_domain_signals'] = signals
    state['working_memory']['fusion'] = fusion
    state['working_memory']['trend_scores'] = scored
    state['final_output'] = synthesis
    state['output_mode'] = 'answer'
    state['confidence'] = min(1.0, fusion['fusion_strength'] + 0.5)
    state['history'].append({'lane': 'cross_domain', 'signals': len(signals),
                             'fusion_strength': fusion['fusion_strength'],
                             'llm_backend': 'gemini_via_openrouter'})
    return state
