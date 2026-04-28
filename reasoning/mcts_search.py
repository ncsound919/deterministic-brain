from __future__ import annotations
"""
MCTS-RAG (Monte Carlo Tree Search + Retrieval-Augmented Generation)

Implements a deterministic, seeded MCTS that ranks candidate artifacts
by exploring reasoning paths over retrieved contexts.  The RNG is seeded
from a hash of (query, session_id) so the same inputs always produce the
same ranking — full reproducibility.

Algorithm:
  Selection   — UCB1 with fixed C=1.41
  Expansion   — limited to BRANCH_FACTOR new context actions per node
  Simulation  — bounded rollout of depth MAX_DEPTH using plausibility score
  Backprop    — propagate simulation score up the tree
"""
from __future__ import annotations
import math
import hashlib
from dataclasses import dataclass, field
from random import Random
from typing import Any

# ---------------------------------------------------------------------------
# Hyper-parameters (all constant for determinism)
# ---------------------------------------------------------------------------
C_PARAM: float = 1.41        # UCB1 exploration constant
BRANCH_FACTOR: int = 3       # max children per node
MAX_DEPTH: int = 4           # max rollout depth
N_SIMULATIONS: int = 20      # simulations per candidate


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

@dataclass
class MCTSNode:
    node_id: str
    candidate: dict
    facts: list[dict]          # subset of retrieved contexts
    depth: int = 0
    visits: int = 0
    total_score: float = 0.0
    parent: 'MCTSNode | None' = field(default=None, repr=False)
    children: list['MCTSNode'] = field(default_factory=list, repr=False)

    @property
    def q(self) -> float:
        return self.total_score / self.visits if self.visits else 0.0

    def ucb1(self, parent_visits: int) -> float:
        if self.visits == 0:
            return float('inf')
        return self.q + C_PARAM * math.sqrt(math.log(parent_visits) / self.visits)


# ---------------------------------------------------------------------------
# Plausibility scorer (pure function of candidate + facts)
# ---------------------------------------------------------------------------

def _plausibility(candidate: dict, facts: list[dict], rng: Random) -> float:
    """Heuristic plausibility: avg fact score + content richness + small noise."""
    avg_fact = sum(f.get('score', 0.5) for f in facts) / max(len(facts), 1)
    content_len = len(str(candidate.get('content', '')))
    richness = min(content_len / 500, 1.0) * 0.2   # up to 0.2 bonus
    noise = rng.gauss(0, 0.01)                       # tiny calibration jitter
    return max(0.0, min(1.0, avg_fact * 0.8 + richness + noise))


# ---------------------------------------------------------------------------
# MCTSSearch class
# ---------------------------------------------------------------------------

class MCTSSearch:
    """Stateless MCTS ranker — all randomness is seeded from (query, session_id)."""

    def _seed(self, query: str, session_id: str) -> int:
        raw = f'{query}||{session_id}'.encode()
        return int(hashlib.sha256(raw).hexdigest()[:16], 16)

    def _select(self, node: MCTSNode) -> MCTSNode:
        """Traverse down selecting highest UCB1 child until unexpanded leaf."""
        while node.children:
            node = max(node.children, key=lambda c: c.ucb1(node.visits or 1))
        return node

    def _expand(self, node: MCTSNode, extra_facts: list[dict], rng: Random) -> MCTSNode:
        """Add up to BRANCH_FACTOR children with subsets of available facts."""
        if node.depth >= MAX_DEPTH:
            return node
        available = [f for f in extra_facts if f not in node.facts]
        # deterministic shuffle via our RNG
        shuffled = list(available)
        rng.shuffle(shuffled)
        for i in range(min(BRANCH_FACTOR, max(1, len(shuffled)))):
            subset = node.facts + (shuffled[i:i+1] if i < len(shuffled) else [])
            child = MCTSNode(
                node_id=f'{node.node_id}_c{i}',
                candidate=node.candidate,
                facts=subset,
                depth=node.depth + 1,
                parent=node,
            )
            node.children.append(child)
        return node.children[0] if node.children else node

    def _simulate(self, node: MCTSNode, rng: Random) -> float:
        """Bounded rollout: extend facts randomly, accumulate plausibility."""
        score = _plausibility(node.candidate, node.facts, rng)
        return score

    def _backprop(self, node: MCTSNode, score: float) -> None:
        cur: MCTSNode | None = node
        while cur is not None:
            cur.visits += 1
            cur.total_score += score
            cur = cur.parent

    def _run_mcts(self, root: MCTSNode, extra_facts: list[dict], rng: Random) -> MCTSNode:
        """Run N_SIMULATIONS iterations, return root (with populated subtree)."""
        for _ in range(N_SIMULATIONS):
            leaf = self._select(root)
            if leaf.visits > 0 and leaf.depth < MAX_DEPTH:
                leaf = self._expand(leaf, extra_facts, rng)
            score = self._simulate(leaf, rng)
            self._backprop(leaf, score)
        return root

    def rank(
        self,
        query: str,
        session_id: str,
        candidates: list[dict],
        contexts: list[dict],
    ) -> tuple[list[dict], dict]:
        """Rank candidates via MCTS.  Returns (ranked_candidates, tree_summary)."""
        rng = Random(self._seed(query, session_id))

        scored: list[tuple[float, dict]] = []
        tree_nodes_total = 0

        for i, cand in enumerate(candidates):
            # Each candidate gets its own MCTS tree rooted with an initial fact subset
            initial_facts = contexts[:2]  # start with top-2 contexts
            root = MCTSNode(
                node_id=f'root_{i}',
                candidate=cand,
                facts=initial_facts,
            )
            root = self._run_mcts(root, contexts, rng)
            final_score = root.q
            tree_nodes_total += sum(1 for _ in self._walk(root))
            scored.append((final_score, cand))

        # Sort by MCTS q-value descending, then by id for tie-breaking
        scored.sort(key=lambda x: (-x[0], x[1].get('id', '')))
        ranked = []
        for score, cand in scored:
            out = dict(cand)
            out['score'] = round(score, 4)
            out['mcts_ranked'] = True
            ranked.append(out)

        tree_summary = {
            'candidates_ranked': len(ranked),
            'simulations_per_candidate': N_SIMULATIONS,
            'total_nodes_explored': tree_nodes_total,
            'seed': self._seed(query, session_id),
            'top_score': ranked[0]['score'] if ranked else None,
        }
        return ranked, tree_summary

    def _walk(self, node: MCTSNode):
        yield node
        for child in node.children:
            yield from self._walk(child)


# ---------------------------------------------------------------------------
# Legacy shim
# ---------------------------------------------------------------------------

def rank_candidates(query: str, candidates: list) -> list:
    """Backward-compatible function wrapper."""
    ranked, _ = MCTSSearch().rank(query, query, candidates, [])
    return ranked
