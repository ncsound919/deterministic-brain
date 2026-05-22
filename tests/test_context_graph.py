"""Tests for reasoning/context_graph.py"""

import json
import time
from unittest.mock import patch

import pytest

from reasoning.context_graph import ContextGraph, DecisionNode


class TestRecordDecision:
    def test_creates_node_with_correct_fields(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path), max_nodes=100)
        graph.record_decision("s1", "skill_selection", {"matches": 0.9}, "accepted", "code_review", 0.85)
        assert len(graph._nodes) == 1
        n = graph._nodes[0]
        assert n.session_id == "s1"
        assert n.decision_type == "skill_selection"
        assert n.factors == {"matches": 0.9}
        assert n.outcome == "accepted"
        assert n.chosen == "code_review"
        assert n.confidence == 0.85
        assert isinstance(n.timestamp, float)

    def test_appends_multiple_nodes(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {"a": 1.0}, "accepted", "s1", 0.9)
        graph.record_decision("s2", "fallback", {"b": 2.0}, "rejected", "s2", 0.5)
        assert len(graph._nodes) == 2

    def test_factors_are_copied_not_referenced(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        original = {"score": 0.8}
        graph.record_decision("s1", "skill_selection", original, "accepted", "s1", 0.9)
        original["score"] = 0.0
        assert graph._nodes[0].factors == {"score": 0.8}


class TestWhyThisSkill:
    def test_returns_aggregated_weights(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {"matches": 0.8, "priority": 0.6}, "accepted", "code_review", 0.9)
        graph.record_decision("s2", "skill_selection", {"matches": 0.4, "priority": 0.2}, "accepted", "code_review", 0.7)
        result = graph.why_this_skill("test query", "code_review")
        assert result["skill_id"] == "code_review"
        assert result["sample_count"] == 2
        assert result["factor_weights"]["matches"] == 0.6
        assert result["factor_weights"]["priority"] == 0.4

    def test_ignores_rejected_outcomes(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {"matches": 0.9}, "rejected", "code_review", 0.3)
        result = graph.why_this_skill("test", "code_review")
        assert result["sample_count"] == 0
        assert result["factor_weights"] == {}

    def test_ignores_other_skills(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {"matches": 0.9}, "accepted", "other_skill", 0.9)
        result = graph.why_this_skill("test", "code_review")
        assert result["sample_count"] == 0

    def test_empty_graph_returns_default(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        result = graph.why_this_skill("anything", "nonexistent")
        assert result == {"skill_id": "nonexistent", "factor_weights": {}, "sample_count": 0}

    def test_missing_factors_handled(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {}, "accepted", "code_review", 0.9)
        graph.record_decision("s2", "skill_selection", {"matches": 0.5}, "accepted", "code_review", 0.8)
        result = graph.why_this_skill("test", "code_review")
        assert result["sample_count"] == 2
        assert "matches" in result["factor_weights"]
        assert result["factor_weights"]["matches"] == 0.25


class TestFailureAttribution:
    def test_returns_grouped_factors(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {"relevance": 0.2}, "rejected", "skill_a", 0.3)
        graph.record_decision("s1", "skill_selection", {"relevance": 0.1}, "fallback", "skill_b", 0.2)
        graph.record_decision("s1", "tool_call", {"confidence": 0.0}, "rejected", "tool_x", 0.1)
        result = graph.failure_attribution("s1")
        assert len(result) == 2
        by_type = {r["decision_type"]: r for r in result}
        assert "skill_selection" in by_type
        assert "tool_call" in by_type
        assert by_type["skill_selection"]["count"] == 2
        assert by_type["skill_selection"]["avg_confidence"] == 0.25

    def test_ignores_accepted_outcomes(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {"relevance": 0.9}, "accepted", "skill_a", 0.9)
        result = graph.failure_attribution("s1")
        assert result == []

    def test_no_matching_session_returns_empty(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {"x": 1.0}, "rejected", "s", 0.1)
        result = graph.failure_attribution("nonexistent_session")
        assert result == []

    def test_empty_graph_returns_empty_list(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        assert graph.failure_attribution("anything") == []


class TestPrune:
    def test_removes_oldest_nodes_when_limit_exceeded(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path), max_nodes=3)
        with patch.object(graph, "_prune", wraps=graph._prune) as spy:
            graph.record_decision("s1", "t", {}, "accepted", "a", 1.0)
            graph.record_decision("s2", "t", {}, "accepted", "b", 1.0)
            graph.record_decision("s3", "t", {}, "accepted", "c", 1.0)
            assert len(graph._nodes) == 3
            assert spy.call_count == 3
        graph.record_decision("s4", "t", {}, "accepted", "d", 1.0)
        assert len(graph._nodes) == 3
        assert graph._nodes[0].session_id == "s2"
        assert graph._nodes[-1].session_id == "s4"

    def test_prune_returns_pruned_count(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path), max_nodes=2)
        graph.record_decision("s1", "t", {}, "accepted", "a", 1.0)
        graph.record_decision("s2", "t", {}, "accepted", "b", 1.0)
        graph._nodes.append(
            DecisionNode("s3", 3.0, "t", {}, "accepted", "c", 1.0)
        )
        pruned = graph.prune()
        assert pruned == 1

    def test_no_prune_when_under_limit(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path), max_nodes=10)
        for i in range(5):
            graph.record_decision(f"s{i}", "t", {}, "accepted", "a", 1.0)
        pruned = graph.prune()
        assert pruned == 0
        assert len(graph._nodes) == 5

    def test_prune_during_load(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        for i in range(5):
            DecisionNode(session_id=f"s{i}", timestamp=float(i), decision_type="t", factors={}, outcome="accepted", chosen="a", confidence=1.0)
            with open(str(path), "a") as f:
                f.write(json.dumps({"session_id": f"s{i}", "timestamp": float(i), "decision_type": "t", "factors": {}, "outcome": "accepted", "chosen": "a", "confidence": 1.0}) + "\n")
        graph = ContextGraph(str(path), max_nodes=2)
        assert len(graph._nodes) == 2


class TestStatus:
    def test_returns_correct_summary(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {}, "accepted", "a", 0.9)
        graph.record_decision("s2", "skill_selection", {}, "rejected", "b", 0.3)
        graph.record_decision("s3", "tool_call", {}, "accepted", "c", 0.8)
        s = graph.status()
        assert s["total_nodes"] == 3
        assert s["max_nodes"] == 10000
        assert s["by_type"] == {"skill_selection": 2, "tool_call": 1}
        assert s["by_outcome"] == {"accepted": 2, "rejected": 1}
        assert s["path"] == str(path)

    def test_empty_graph_status(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        s = graph.status()
        assert s["total_nodes"] == 0
        assert s["by_type"] == {}
        assert s["by_outcome"] == {}


class TestPersistence:
    def test_round_trip_preserves_all_nodes(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path))
        graph.record_decision("s1", "skill_selection", {"a": 0.5}, "accepted", "skill_a", 0.9)
        graph.record_decision("s2", "fallback", {"b": 0.3}, "rejected", "skill_b", 0.4)
        del graph

        graph2 = ContextGraph(str(path))
        assert len(graph2._nodes) == 2
        assert graph2._nodes[0].session_id == "s1"
        assert graph2._nodes[0].decision_type == "skill_selection"
        assert graph2._nodes[0].chosen == "skill_a"
        assert graph2._nodes[0].factors == {"a": 0.5}
        assert graph2._nodes[0].outcome == "accepted"
        assert graph2._nodes[0].confidence == 0.9
        assert graph2._nodes[1].session_id == "s2"

    def test_isolation_between_instances(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        g1 = ContextGraph(str(path))
        g1.record_decision("s1", "skill_selection", {}, "accepted", "a", 1.0)
        g2 = ContextGraph(str(path))
        g2.record_decision("s2", "tool_call", {}, "rejected", "b", 0.5)
        g3 = ContextGraph(str(path))
        assert len(g3._nodes) == 2

    def test_corrupted_line_skipped(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        path.write_text(
            '{"session_id": "good", "timestamp": 1.0, "decision_type": "t", "factors": {}, "outcome": "accepted", "chosen": "a", "confidence": 1.0}\n'
            'not valid json\n'
            '{"session_id": "good2", "timestamp": 2.0, "decision_type": "t", "factors": {}, "outcome": "accepted", "chosen": "b", "confidence": 1.0}\n'
        )
        graph = ContextGraph(str(path))
        assert len(graph._nodes) == 2


class TestEdgeCases:
    def test_missing_path_file(self, tmp_path):
        path = tmp_path / "nonexistent" / "graph.jsonl"
        graph = ContextGraph(str(path))
        assert graph._nodes == []

    def test_max_nodes_zero(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path), max_nodes=0)
        graph.record_decision("s1", "t", {}, "accepted", "a", 1.0)
        assert len(graph._nodes) == 1

    def test_max_nodes_one(self, tmp_path):
        path = tmp_path / "graph.jsonl"
        graph = ContextGraph(str(path), max_nodes=1)
        graph.record_decision("s1", "t", {}, "accepted", "a", 1.0)
        graph.record_decision("s2", "t", {}, "accepted", "b", 1.0)
        assert len(graph._nodes) == 1
        assert graph._nodes[0].session_id == "s2"
