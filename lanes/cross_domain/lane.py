from __future__ import annotations
from lanes.cross_domain.evidence_fusion import fuse_evidence
from lanes.cross_domain.trend_scorer import score_trends

_DOMAIN_SIGNALS = {
    'ai': 'AI capability shifts are altering automation costs, product velocity, and competitive positioning.',
    'supply': 'Supply chain pressure is affecting delivery timelines, pricing, and inventory strategy.',
    'regulation': 'Regulatory changes are increasing compliance overhead and limiting certain product categories.',
    'finance': 'Capital market conditions are affecting investment timing and startup runway expectations.',
    'energy': 'Energy pricing volatility is influencing data center costs and hardware procurement cycles.',
    'labor': 'Labor market shifts are changing how organizations balance automation and human execution.',
    'climate': 'Climate risk is beginning to influence infrastructure location decisions and insurance costs.',
}

def _detect_signals(query: str) -> list:
    q = query.lower()
    detected = [v for k, v in _DOMAIN_SIGNALS.items() if k in q]
    if not detected:
        detected = list(_DOMAIN_SIGNALS.values())[:3]
    return detected

def run(state: dict) -> dict:
    signals = _detect_signals(state['query'])
    fusion = fuse_evidence(state.get('retrieved_contexts', []), signals)
    scored = score_trends(signals, seed_key=state.get('query', 'default'))
    top_signal = scored[0]['signal'] if scored else signals[0]
    synthesis = ('Cross-domain synthesis (signals=' + str(len(signals)) +
                 ', fusion_strength=' + str(fusion['fusion_strength']) + '): ' + '; '.join(signals))
    candidate = {'id': 'x1', 'kind': 'cross_domain', 'content': synthesis,
                 'signals': signals, 'trend_scores': scored, 'fusion': fusion}
    state['candidate_artifacts'] = [candidate]
    state['working_memory']['cross_domain_signals'] = signals
    state['working_memory']['fusion'] = fusion
    state['working_memory']['trend_scores'] = scored
    state['final_output'] = 'Leading signal: ' + top_signal + '\n\nFull synthesis: ' + synthesis
    state['output_mode'] = 'answer'
    state['confidence'] = min(1.0, fusion['fusion_strength'] + 0.5)
    state['history'].append({'lane': 'cross_domain', 'signals': len(signals), 'fusion_strength': fusion['fusion_strength']})
    return state
