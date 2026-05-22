from __future__ import annotations
"""
MCTS-RAG (Monte Carlo Tree Search + Retrieval-Augmented Generation)

Implements a deterministic, seeded MCTS that ranks candidate artifacts
by exploring reasoning paths over retrieved contexts.  The RNG is seeded
from a hash of (query, session_id) so the same inputs always produce the
same ranking — full reproducibility.

Parallelised across candidates using ThreadPoolExecutor for speed.
Each candidate builds an independent tree with its own seeded Random
so results are deterministic regardless of thread scheduling.

Algorithm:
  Selection   — UCB1 with fixed C=1.41
  Expansion   — limited to BRANCH_FACTOR new context actions per node
  Simulation  — bounded rollout of depth MAX_DEPTH using plausibility score
  Backprop    — propagate simulation score up the tree
"""
import math
import hashlib
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from random import Random

# ---------------------------------------------------------------------------
# Hyper-parameters (all constant for determinism)
# ---------------------------------------------------------------------------
C_PARAM: float = 1.41       # UCB1 exploration constant
BRANCH_FACTOR: int = 3       # max children per node
MAX_DEPTH: int = 4           # max rollout depth
N_SIMULATIONS: int = 20      # simulations per candidate
N_WORKERS: int = min(4, (os.cpu_count() or 2))  # parallel workers


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
    """Stateless MCTS ranker — all randomness is seeded from (query, session_id).
    
    Parallelises tree construction across candidates using ThreadPoolExecutor.
    Each candidate receives a deterministic sub-seed so results are identical
    regardless of thread scheduling.
    """

    def __init__(self, n_workers: int = N_WORKERS):
        self.n_workers = min(n_workers, (os.cpu_count() or 2))

    def _seed(self, query: str, session_id: str) -> int:
        raw = f'{query}||{session_id}'.encode()
        return int(hashlib.sha256(raw).hexdigest()[:16], 16)

    @staticmethod
    def _select(node: MCTSNode) -> MCTSNode:
        """Traverse down selecting highest UCB1 child until unexpanded leaf."""
        while node.children:
            node = max(node.children, key=lambda c: c.ucb1(node.visits or 1))
        return node

    @staticmethod
    def _expand(node: MCTSNode, extra_facts: list[dict], rng: Random) -> MCTSNode:
        """Add up to BRANCH_FACTOR children with subsets of available facts."""
        if node.depth >= MAX_DEPTH:
            return node
        available = [f for f in extra_facts if f not in node.facts]
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

    @staticmethod
    def _simulate(node: MCTSNode, rng: Random) -> float:
        """Bounded rollout: extend facts randomly, accumulate plausibility."""
        return _plausibility(node.candidate, node.facts, rng)

    @staticmethod
    def _backprop(node: MCTSNode, score: float) -> None:
        cur: MCTSNode | None = node
        while cur is not None:
            cur.visits += 1
            cur.total_score += score
            cur = cur.parent

    @staticmethod
    def _run_mcts(root: MCTSNode, extra_facts: list[dict], rng: Random) -> MCTSNode:
        """Run N_SIMULATIONS iterations, return root (with populated subtree)."""
        for _ in range(N_SIMULATIONS):
            leaf = MCTSSearch._select(root)
            if leaf.visits > 0 and leaf.depth < MAX_DEPTH:
                leaf = MCTSSearch._expand(leaf, extra_facts, rng)
            score = MCTSSearch._simulate(leaf, rng)
            MCTSSearch._backprop(leaf, score)
        return root

    @staticmethod
    def _evaluate_candidate(index: int, seed: int, cand: dict,
                             contexts: list[dict]) -> tuple[int, float, dict, int]:
        """Evaluate a single candidate (runs in a thread worker).
        
        Returns (index, score, candidate, node_count) for deterministic ordering.
        """
        sub_seed = int(hashlib.sha256(f'{seed}:{index}'.encode()).hexdigest()[:16], 16)
        rng = Random(sub_seed)
        initial_facts = contexts[:2]
        root = MCTSNode(
            node_id=f'root_{index}',
            candidate=cand,
            facts=initial_facts,
        )
        MCTSSearch._run_mcts(root, contexts, rng)
        final_score = root.q
        node_count = sum(1 for _ in MCTSSearch._walk(root))
        return index, final_score, cand, node_count

    @staticmethod
    def _walk(node: MCTSNode):
        yield node
        for child in node.children:
            yield from MCTSSearch._walk(child)

    def rank(
        self,
        query: str,
        session_id: str,
        candidates: list[dict],
        contexts: list[dict],
    ) -> tuple[list[dict], dict]:
        """Rank candidates via parallel MCTS.  Returns (ranked_candidates, tree_summary)."""
        seed = self._seed(query, session_id)
        n_candidates = len(candidates)
        n_workers = min(self.n_workers, n_candidates) if n_candidates > 0 else 1

        scored: list[tuple[float, dict]] = []
        tree_nodes_total = 0

        if n_workers <= 1 or n_candidates <= 1:
            for i, cand in enumerate(candidates):
                _, score, cand_out, cnt = self._evaluate_candidate(i, seed, cand, contexts)
                tree_nodes_total += cnt
                scored.append((score, cand_out))
        else:
            with ThreadPoolExecutor(max_workers=n_workers) as executor:
                futures = [
                    executor.submit(self._evaluate_candidate, i, seed, cand, contexts)
                    for i, cand in enumerate(candidates)
                ]
                results = []
                for future in as_completed(futures):
                    results.append(future.result())
                results.sort(key=lambda r: r[0])  # deterministic: sort by index
                for _idx, score, cand_out, cnt in results:
                    tree_nodes_total += cnt
                    scored.append((score, cand_out))

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
            'seed': seed,
            'top_score': ranked[0]['score'] if ranked else None,
        }
        return ranked, tree_summary


# ---------------------------------------------------------------------------
# Legacy shim
# ---------------------------------------------------------------------------

def rank_candidates(query: str, candidates: list) -> list:
    """Backward-compatible function wrapper."""
    ranked, _ = MCTSSearch().rank(query, query, candidates, [])
    return ranked
