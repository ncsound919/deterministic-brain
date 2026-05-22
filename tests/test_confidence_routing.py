"""Tests for orchestration/confidence_routing.py."""
from orchestration.confidence_routing import MultiLayerConfidenceRouter


class TestConfidenceRouter:
    def setup_method(self):
        self.router = MultiLayerConfidenceRouter(threshold=0.5)

    def test_register_route(self):
        self.router.register_route("test", primary_fn=lambda x: (x, 0.8), fallback_fn=lambda x: "fb")
        assert "test" in self.router.routes

    def test_execute_returns_primary_when_confident(self):
        self.router.register_route("high", primary_fn=lambda x: ("ok", 0.9), fallback_fn=lambda x: "fb")
        result = self.router.execute("high", "input")
        assert result.data == "ok"
        assert result.fallback_triggered is False

    def test_fallback_on_low_confidence(self):
        self.router.register_route("low", primary_fn=lambda x: ("ok", 0.1), fallback_fn=lambda x: "fb")
        result = self.router.execute("low", "input")
        assert result.data == "fb"
        assert result.fallback_triggered is True

    def test_fallback_on_primary_exception(self):
        def broken(_):
            raise ValueError("boom")
        self.router.register_route("broken", primary_fn=broken, fallback_fn=lambda x: "fb")
        result = self.router.execute("broken", "input")
        assert result.data == "fb"
        assert result.fallback_triggered is True

    def test_unknown_route_raises(self):
        try:
            self.router.execute("nonexistent", "x")
            assert False, "should have raised"
        except ValueError:
            pass

    def test_layer_scores_in_result(self):
        self.router.register_route("scores", primary_fn=lambda x: ("ok", 0.7), fallback_fn=lambda x: "fb")
        result = self.router.execute("scores", "input", semantic_score=0.8, evidence_score=0.6)
        assert result.layer_scores is not None
        assert "layer1" in result.layer_scores
        assert "layer2" in result.layer_scores
        assert "layer3" in result.layer_scores
        assert "final" in result.layer_scores

    def test_weights_used_in_result(self):
        self.router.register_route("w", primary_fn=lambda x: ("ok", 0.7), fallback_fn=lambda x: "fb")
        result = self.router.execute("w", "x")
        assert result.weights_used is not None
        assert "layer1" in result.weights_used

    def test_weight_adaptation(self):
        self.router.register_route("adapt", primary_fn=lambda x: ("ok", 0.1), fallback_fn=lambda x: "fb")
        for _ in range(10):
            self.router.execute("adapt", "x")
        stats = self.router._stats["adapt"]
        assert stats.layer1_weight < 0.6

    def test_status_summary_structure(self):
        self.router.register_route("s1", primary_fn=lambda x: (x, 0.8), fallback_fn=lambda x: "fb")
        self.router.execute("s1", "x")
        summary = self.router.status_summary()
        assert "routes" in summary
        assert "threshold" in summary
        assert "total_routes" in summary
        assert summary["total_routes"] >= 1

    def test_route_stats_list(self):
        self.router.register_route("rs", primary_fn=lambda x: (x, 0.8), fallback_fn=lambda x: "fb")
        self.router.execute("rs", "x")
        stats = self.router.route_stats()
        assert len(stats) >= 1
        entry = stats[0]
        assert "total_calls" in entry
        assert "fallback_rate" in entry
        assert "weights" in entry

    def test_semantic_evidence_scores_passed(self):
        self.router.register_route("se", primary_fn=lambda x: (x, 0.5), fallback_fn=lambda x: "fb")
        result = self.router.execute("se", "x", semantic_score=1.0, evidence_score=1.0)
        assert result.layer_scores["layer2"] == 1.0
        assert result.layer_scores["layer3"] == 1.0

    def test_default_semantic_evidence_when_not_provided(self):
        self.router.register_route("de", primary_fn=lambda x: (x, 0.5), fallback_fn=lambda x: "fb",
                                    semantic_fn=lambda x: 0.3, evidence_fn=lambda x: 0.2)
        result = self.router.execute("de", "x")
        assert result.layer_scores["layer2"] == 0.3
        assert result.layer_scores["layer3"] == 0.2

    def test_backward_compatible_alias(self):
        from orchestration.confidence_routing import ConfidenceRouter
        assert ConfidenceRouter is MultiLayerConfidenceRouter
