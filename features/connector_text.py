from __future__ import annotations
"""
CONNECTOR_TEXT — Connector text blocks.

Generates rich connector/transition text between reasoning blocks:
- Reasoning transitions ("Because of X, we now need to consider Y...")
- Summary connectors between lane outputs
- Narrative bridges between tool results

Used by the composer node to make multi-step outputs more coherent.
"""
from tools.llm.router import chat

_SYSTEM = (
    'Write a concise 1-2 sentence connector that bridges two reasoning blocks. '
    'Be natural, precise, and avoid filler phrases. '
    'Output only the connector text, nothing else.'
)


def connect(block_a: str, block_b: str, context: str = '') -> str:
    user_msg = (
        f'Block A: {block_a[:300]}\n'
        f'Block B: {block_b[:300]}\n'
        + (f'Context: {context[:200]}' if context else '')
    )
    return chat(system=_SYSTEM, user=user_msg, lane='cross_domain', max_tokens=128)


def narrate_steps(steps: list[str]) -> str:
    """Convert a list of execution steps into a flowing narrative."""
    if not steps:
        return ''
    if len(steps) == 1:
        return steps[0]
    connectors = []
    for i in range(len(steps) - 1):
        bridge = connect(steps[i], steps[i+1])
        connectors.append(steps[i])
        connectors.append(bridge)
    connectors.append(steps[-1])
    return '\n'.join(connectors)
