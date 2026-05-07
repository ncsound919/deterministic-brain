"""Token savings ledger — tracks competitive advantage vs LLM API costs.

Every deterministic decision the brain makes instead of calling an LLM
saves real money. This tracks cumulative savings for the dashboard.

GPT-4o pricing as baseline: $0.0025/1K input, $0.01/1K output.
"""

from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict


# Cost per 1K tokens (GPT-4o pricing for comparison)
COST_PER_1K_INPUT = 0.0025
COST_PER_1K_OUTPUT = 0.0100

# Average tokens an LLM would consume for each brain decision
LLM_EQUIVALENT = {
    "routing_decision":  {"input": 800,  "output": 50},
    "config_selection":  {"input": 1200, "output": 150},
    "code_scaffold":     {"input": 2000, "output": 800},
    "skill_discovery":   {"input": 3000, "output": 200},
    "betting_analysis":  {"input": 3000, "output": 400},
    "news_summarize":    {"input": 4000, "output": 600},
    "pre_audit":         {"input": 1500, "output": 100},
    "quantum_collapse":  {"input": 1000, "output": 150},
    "algebraic_solve":   {"input": 2000, "output": 300},
    "dialogue_process":  {"input": 500,  "output": 80},
    "email_notify":      {"input": 800,  "output": 150},
    "crm_operation":     {"input": 1200, "output": 200},
    "content_schedule":  {"input": 2000, "output": 400},
    "agent_orchestrate": {"input": 1500, "output": 200},
    "odds_fetch":        {"input": 1000, "output": 100},
    "market_data":       {"input": 800,  "output": 50},
}


class TokenLedger:
    """Tracks cumulative token savings vs GPT-4o equivalent."""

    def __init__(self, path: str = ".token_savings.json"):
        self.path = Path(path)
        self._data = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                pass
        return {"total_tokens": 0, "total_dollars": 0.0, "events": [], "since": time.time()}

    def _save(self):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    def record(self, decision_type: str, session_id: str = "") -> Dict:
        eq = LLM_EQUIVALENT.get(decision_type, {"input": 1000, "output": 200})
        tokens = eq["input"] + eq["output"]
        dollars = round(
            (eq["input"] / 1000) * COST_PER_1K_INPUT +
            (eq["output"] / 1000) * COST_PER_1K_OUTPUT, 6
        )

        self._data["total_tokens"] += tokens
        self._data["total_dollars"] += dollars
        self._data["total_dollars"] = round(self._data["total_dollars"], 6)
        self._data["events"].append({
            "type": decision_type,
            "tokens": tokens,
            "dollars": dollars,
            "ts": time.time(),
            "session_id": session_id,
        })

        # Keep last 1000 events
        if len(self._data["events"]) > 1000:
            self._data["events"] = self._data["events"][-500:]

        self._save()
        return {"tokens_saved": tokens, "dollars_saved": dollars}

    def summary(self) -> Dict:
        return {
            "total_tokens": self._data["total_tokens"],
            "total_dollars": round(self._data["total_dollars"], 6),
            "total_decisions": len(self._data["events"]),
            "since": self._data["since"],
            "equivalent_gpt4o_cost": round(self._data["total_dollars"], 6),
            "model_compared": "gpt-4o ($0.0025/1K input, $0.01/1K output)",
        }


# Singleton
token_ledger = TokenLedger()
