"""Tests for the token savings ledger (tools/token_ledger.py)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _fresh_ledger(tmp_path):
    from tools.token_ledger import TokenLedger

    return TokenLedger(path=str(tmp_path / "ledger.json"))


class TestTokenLedger:
    def test_record_tracks_tokens_and_both_cost_bases(self, tmp_path):
        led = _fresh_ledger(tmp_path)
        result = led.record("routing_decision")
        assert result["tokens_saved"] == 850  # 800 in + 50 out
        assert result["dollars_saved"] > 0
        assert result["gpt4o_dollars_saved"] > 0
        s = led.summary()
        assert s["total_decisions"] == 1
        assert s["total_tokens"] == 850
        assert "fleet_cost_basis" in s
        assert s["fleet_savings"] > 0

    def test_record_fleet_savings_explicit(self, tmp_path):
        led = _fresh_ledger(tmp_path)
        result = led.record_fleet_savings(512, source="brain_route")
        assert result["tokens_saved"] == 512
        assert result["dollars_saved"] > 0
        s = led.summary()
        assert s["total_tokens"] == 512
        assert s["total_decisions"] == 1

    def test_record_fleet_savings_ignores_negative(self, tmp_path):
        led = _fresh_ledger(tmp_path)
        result = led.record_fleet_savings(-100)
        assert result["tokens_saved"] == 0
        assert led.summary()["total_tokens"] == 0

    def test_summary_exposes_both_bases(self, tmp_path):
        led = _fresh_ledger(tmp_path)
        led.record("news_summarize")
        s = led.summary()
        assert "fleet_savings" in s
        assert "equivalent_gpt4o_cost" in s
        assert s["model_compared"].startswith("gpt-4o")

    def test_persists_to_disk(self, tmp_path):
        led = _fresh_ledger(tmp_path)
        for i in range(5):  # batch-save every 5 events
            led.record("routing_decision", session_id=f"s{i}")
        data = json.loads((tmp_path / "ledger.json").read_text())
        assert data["total_tokens"] > 0
        assert len(data["events"]) == 5

    def test_loads_existing_data(self, tmp_path):
        path = tmp_path / "ledger.json"
        path.write_text(json.dumps({"total_tokens": 100, "total_dollars": 0.5,
                                    "gpt4o_dollars": 1.0, "events": [], "since": 0}))
        from tools.token_ledger import TokenLedger

        led = TokenLedger(path=str(path))
        s = led.summary()
        assert s["total_tokens"] == 100
        assert s["fleet_savings"] == 0.5
