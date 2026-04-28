from __future__ import annotations
"""
Observability, checkpointing, and replay for the deterministic brain.

Checkpoints are persisted as JSON files in CHECKPOINT_DIR.
Each run produces a trace keyed by session_id that can be replayed.
"""
import json
import os
import time
from pathlib import Path
from typing import Any

_CHECKPOINT_DIR = Path(os.getenv('CHECKPOINT_DIR', '.checkpoints'))
_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)

_ENABLED = os.getenv('TRACING_ENABLED', 'true').lower() != 'false'


# ---------------------------------------------------------------------------
# Low-level storage
# ---------------------------------------------------------------------------

def _session_dir(session_id: str) -> Path:
    d = _CHECKPOINT_DIR / session_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def checkpoint_state(node_name: str, state: dict) -> None:
    """Persist a state snapshot after `node_name` executes."""
    if not _ENABLED:
        return
    session_id = state.get('session_id', 'unknown')
    d = _session_dir(session_id)
    ts = int(time.time() * 1000)
    path = d / f'{ts:016d}_{node_name}.json'
    snapshot = {
        'node': node_name,
        'timestamp_ms': ts,
        'session_id': session_id,
        'lane': state.get('lane', ''),
        'status': state.get('status', ''),
        'confidence': state.get('confidence', 0.0),
        'retrieved_count': len(state.get('retrieved_contexts', [])),
        'candidate_count': len(state.get('candidate_artifacts', [])),
        'verification_count': len(state.get('verification_results', [])),
        'history_len': len(state.get('history', [])),
        'final_output_preview': str(state.get('final_output', ''))[:200],
        'derived_facts': state.get('working_memory', {}).get('derived_facts', []),
        'logic_trace': state.get('working_memory', {}).get('logic_trace', []),
        'mcts_tree': state.get('working_memory', {}).get('mcts_tree', {}),
    }
    try:
        path.write_text(json.dumps(snapshot, default=str, indent=2))
    except Exception:  # noqa: BLE001
        pass  # Never let tracing crash the main pipeline


# ---------------------------------------------------------------------------
# Trace retrieval
# ---------------------------------------------------------------------------

def get_trace(session_id: str) -> dict:
    """Reconstruct the full trace for a session from persisted checkpoints."""
    d = _session_dir(session_id)
    checkpoints = []
    for p in sorted(d.glob('*.json')):
        try:
            checkpoints.append(json.loads(p.read_text()))
        except Exception:  # noqa: BLE001
            pass
    return {
        'session_id': session_id,
        'checkpoints': checkpoints,
        'node_sequence': [c['node'] for c in checkpoints],
        'total_nodes': len(checkpoints),
    }


def list_sessions() -> list[str]:
    """Return all session IDs that have saved checkpoints."""
    if not _CHECKPOINT_DIR.exists():
        return []
    return [d.name for d in sorted(_CHECKPOINT_DIR.iterdir()) if d.is_dir()]


# ---------------------------------------------------------------------------
# Structured event logger
# ---------------------------------------------------------------------------

def log_event(event_type: str, data: dict[str, Any]) -> None:
    """Emit a structured log line to stdout (easily captured by log aggregators)."""
    if not _ENABLED:
        return
    record = {
        'ts': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'event': event_type,
        **data,
    }
    print(json.dumps(record, default=str))


# ---------------------------------------------------------------------------
# Replay support
# ---------------------------------------------------------------------------

def replay_from(session_id: str, from_node: str) -> dict | None:
    """Load the last checkpoint before `from_node` to reconstruct state.

    Returns the snapshot dict or None if not found.
    Note: full replay requires re-invoking the LangGraph app with
    the restored state.  This function provides the state recovery part.
    """
    trace = get_trace(session_id)
    target: dict | None = None
    for chk in trace['checkpoints']:
        if chk['node'] == from_node:
            break
        target = chk
    return target
