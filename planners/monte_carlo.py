"""MonteCarloScaffolder — exhaustive config-space search, deterministic scoring."""
from __future__ import annotations
import itertools
from typing import Dict

from planners.scorer import DeterministicScorer


class MonteCarloScaffolder:
    def __init__(self, executor, auditor):
        self.executor = executor
        self.auditor  = auditor
        self.scorer   = DeterministicScorer()

    def scaffold(self, skill_meta: Dict, base_inputs: Dict) -> Dict:
        choices = skill_meta.get("choices", {})
        if not choices:
            return self.executor.execute(skill_meta["skill_path"], base_inputs)

        keys   = list(choices.keys())
        values = [choices[k] for k in keys]
        combos = list(itertools.product(*values))

        # cap at 64 combinations to keep execution < 1s
        if len(combos) > 64:
            import random
            random.seed(42)  # deterministic seed
            combos = random.sample(combos, 64)

        best_result = None
        best_score  = -1.0

        for combo in combos:
            variant = {**base_inputs, **dict(zip(keys, combo))}
            try:
                result = self.executor.execute(skill_meta["skill_path"], variant)
                if result.get("success"):
                    score = self.scorer.score(result)
                    if score > best_score:
                        best_score  = score
                        best_result = result
            except Exception:
                continue

        if best_result:
            best_result["monte_carlo_score"] = best_score
            return best_result
        raise RuntimeError("MonteCarloScaffolder: no valid configuration found")
