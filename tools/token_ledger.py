"""Token savings ledger — tracks competitive advantage vs LLM API costs.

Every deterministic decision the brain makes instead of calling an LLM
saves real money. This tracks cumulative savings for the dashboard.

Two cost bases:
  - Fleet basis: DRAYMOND_COST_PER_1M_TOKENS (default $1.50/1M) — the fleet's
    actual LLM budget rate (opencode Go tier flavored), matching Draymond's
    cost.ts. This is the authoritative savings number.
  - GPT-4o equivalent: $0.0025/1K input, $0.01/1K output — the old "competitive
    advantage vs frontier" baseline, kept for backward compatibility.
"""

from __future__ import annotations
import json
import os
import time
from pathlib import Path
from typing import Dict


# Fleet cost basis — matches Draymond cost.ts ($1.50 per 1M tokens).
FLEET_COST_PER_1M = float(os.getenv("DRAYMOND_COST_PER_1M_TOKENS", "150")) / 1_000_000
# GPT-4o equivalent pricing (competitive baseline, kept for comparison).
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
    """Tracks cumulative token savings vs fleet LLM budget + GPT-4o equivalent."""

    def __init__(self, path: str = ".token_savings.json"):
        self.path = Path(path)
        self._data = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except Exception:
                pass
        return {
            "total_tokens": 0,
            "total_dollars": 0.0,          # fleet basis (authoritative)
            "gpt4o_dollars": 0.0,          # competitive baseline (comparison)
            "events": [],
            "since": time.time(),
        }

    def _save(self):
        self.path.parent.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    def record(self, decision_type: str, session_id: str = "") -> Dict:
        eq = LLM_EQUIVALENT.get(decision_type, {"input": 1000, "output": 200})
        tokens = eq["input"] + eq["output"]
        # Fleet LLM-budget dollars: the number that matters for ops.
        fleet_dollars = round(tokens / 1_000_000 * FLEET_COST_PER_1M, 8)
        # GPT-4o equivalent: the "vs frontier model" competitive baseline.
        gpt4o_dollars = round(
            (eq["input"] / 1000) * COST_PER_1K_INPUT +
            (eq["output"] / 1000) * COST_PER_1K_OUTPUT, 6
        )

        self._data["total_tokens"] += tokens
        self._data["total_dollars"] += fleet_dollars
        self._data["total_dollars"] = round(self._data["total_dollars"], 8)
        self._data["gpt4o_dollars"] += gpt4o_dollars
        self._data["gpt4o_dollars"] = round(self._data["gpt4o_dollars"], 6)
        self._data["events"].append({
            "type": decision_type,
            "tokens": tokens,
            "dollars": fleet_dollars,
            "gpt4o_dollars": gpt4o_dollars,
            "ts": time.time(),
            "session_id": session_id,
        })

        # Keep last 1000 events
        if len(self._data["events"]) > 1000:
            self._data["events"] = self._data["events"][-800:]

        # Batch save: only write to disk every 5 events or if manually triggered
        if len(self._data["events"]) % 5 == 0:
            self._save()

        return {
            "tokens_saved": tokens,
            "dollars_saved": fleet_dollars,
            "gpt4o_dollars_saved": gpt4o_dollars,
        }

    def record_fleet_savings(self, tokens: int, source: str = "brain_route",
                             session_id: str = "") -> Dict:
        """Record savings from an explicit deterministic routing decision.

        Used when Draymond's router skips a paid LLM call via the brain
        pre-route — tokens here are the LLM tokens that were NOT spent.
        """
        tokens = max(0, int(tokens))
        fleet_dollars = round(tokens / 1_000_000 * FLEET_COST_PER_1M, 8)
        self._data["total_tokens"] += tokens
        self._data["total_dollars"] += fleet_dollars
        self._data["total_dollars"] = round(self._data["total_dollars"], 8)
        self._data["events"].append({
            "type": source,
            "tokens": tokens,
            "dollars": fleet_dollars,
            "gpt4o_dollars": 0.0,
            "ts": time.time(),
            "session_id": session_id,
        })
        if len(self._data["events"]) % 5 == 0:
            self._save()
        return {"tokens_saved": tokens, "dollars_saved": fleet_dollars}

    def summary(self) -> Dict:
        return {
            "total_tokens": self._data["total_tokens"],
            "total_dollars": round(self._data["total_dollars"], 8),
            "total_decisions": len(self._data["events"]),
            "since": self._data["since"],
            "fleet_cost_basis": f"${float(os.getenv('DRAYMOND_COST_PER_1M_TOKENS', '150')) / 100:,.2f}/1M tokens",
            "fleet_savings": round(self._data["total_dollars"], 8),
            "equivalent_gpt4o_cost": round(self._data.get("gpt4o_dollars", 0.0), 6),
            "model_compared": "gpt-4o ($0.0025/1K input, $0.01/1K output)",
        }


# Singleton
token_ledger = TokenLedger()
