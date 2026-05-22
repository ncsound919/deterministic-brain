"""Read from the tracing database to reconstruct and replay full brain execution sessions."""

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Generator


@dataclass
class NodeSnapshot:
    node_name: str
    timestamp: float
    state_snapshot: Dict
    delta_from_previous: Dict


@dataclass
class ReplaySession:
    session_id: str
    nodes: List[NodeSnapshot]
    start_time: float
    end_time: float
    outcome: str


class SessionReplayEngine:
    """Replay full brain execution from checkpoint traces.

    Reads checkpoint:* events from the tracing database (tools.tracing)
    and reconstructs ordered node execution sequences.
    """

    def __init__(self):
        self._trace_fn = None

    def _get_trace(self):
        """Lazy import to avoid circular deps."""
        if self._trace_fn is None:
            from tools.tracing import get_trace
            self._trace_fn = get_trace
        return self._trace_fn

    def capture_session(self, session_id: str) -> Optional[ReplaySession]:
        """Load all checkpoints for a session and build a ReplaySession.

        Returns None if no checkpoints found for the session.
        """
        get_trace = self._get_trace()
        events = get_trace(session_id)
        if not events:
            return None

        checkpoints = [e for e in events if e["event"].startswith("checkpoint:")]
        if not checkpoints:
            return None

        nodes = []
        prev_snapshot: Dict = {}
        for ev in checkpoints:
            node_name = ev["event"].replace("checkpoint:", "", 1)
            snapshot = ev.get("data", {})
            delta = self._compute_delta(prev_snapshot, snapshot)
            nodes.append(NodeSnapshot(
                node_name=node_name,
                timestamp=ev.get("ts", 0),
                state_snapshot=snapshot,
                delta_from_previous=delta,
            ))
            prev_snapshot = snapshot

        first_node = nodes[0] if nodes else None
        last_node = nodes[-1] if nodes else None

        return ReplaySession(
            session_id=session_id,
            nodes=nodes,
            start_time=first_node.timestamp if first_node else 0,
            end_time=last_node.timestamp if last_node else 0,
            outcome=last_node.state_snapshot.get("status", "unknown") if last_node else "unknown",
        )

    def replay(self, session_id: str, step: bool = False) -> Generator[Dict, None, None]:
        """Yield each node's state snapshot in order.

        If step=True, yields one node at a time (for REPL step-through).
        Otherwise yields all nodes.
        """
        session = self.capture_session(session_id)
        if not session:
            yield {"error": f"Session not found: {session_id}"}
            return

        for node in session.nodes:
            yield {
                "node": node.node_name,
                "timestamp": node.timestamp,
                "state": node.state_snapshot,
                "delta": node.delta_from_previous,
            }
            if step:
                inp = input(f"  [{node.node_name}] Press Enter for next node (q to quit): ")
                if inp.strip().lower() == "q":
                    break

    def describe(self, session: ReplaySession) -> Dict:
        """Return a human-readable summary of a replayed session."""
        node_names = [n.node_name for n in session.nodes]
        return {
            "session_id": session.session_id,
            "duration_s": round(session.end_time - session.start_time, 2),
            "nodes_visited": len(session.nodes),
            "node_sequence": node_names,
            "outcome": session.outcome,
            "start_time": time.strftime("%H:%M:%S", time.localtime(session.start_time)),
            "start_time_ts": session.start_time,
            "end_time": time.strftime("%H:%M:%S", time.localtime(session.end_time)),
            "end_time_ts": session.end_time,
        }

    def list_sessions(self, limit: int = 20) -> List[Dict]:
        """List sessions with checkpoints, newest first."""
        from tools.tracing import list_sessions as _list_sessions
        all_sessions = _list_sessions()
        sessions_with_data = []
        for sid in all_sessions:
            session = self.capture_session(sid)
            if session:
                sessions_with_data.append(self.describe(session))
        sessions_with_data.sort(key=lambda s: s.get("start_time_ts", 0), reverse=True)
        return sessions_with_data[:limit]

    @staticmethod
    def _compute_delta(prev: Dict, curr: Dict) -> Dict:
        """Compute what changed between two state snapshots."""
        delta = {}
        all_keys = set(list(prev.keys()) + list(curr.keys()))
        for k in all_keys:
            pv = prev.get(k)
            cv = curr.get(k)
            if pv != cv:
                delta[k] = {"before": pv, "after": cv}
        return delta


_replay_engine: Optional[SessionReplayEngine] = None


def get_replay_engine() -> SessionReplayEngine:
    global _replay_engine
    if _replay_engine is None:
        _replay_engine = SessionReplayEngine()
    return _replay_engine
