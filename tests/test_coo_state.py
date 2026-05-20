"""Tests for the COO Brain State models."""
from __future__ import annotations

import pytest
from dataclasses import asdict
from pathlib import Path

from coo.state import (
    ProductConfig,
    PortfolioState,
    TelemetryEvent,
    TrafficLightZone,
    DecisionCard,
    Constitution,
    PROHIBITED_DIRS,
    DB_SCHEMA_VERSION,
)


class TestProductConfig:
    def test_defaults(self):
        p = ProductConfig(product_id="claw-protect", tier=1, name="Claw Protect")
        assert p.product_id == "claw-protect"
        assert p.tier == 1
        assert p.github_owner == "ncsound919"
        assert p.github_repo == "claw-protect"
        assert p.stripe_price_ids == []
        assert p.sentry_dsn == ""
        assert p.deploy_env == "staging"
        assert p.is_active is True
        assert p.base_priority == 50

    def test_serialization_roundtrip(self):
        p = ProductConfig(product_id="openhub", tier=1, name="OpenHub")
        p.github_repo = "OpenHub-main"
        d = asdict(p)
        assert d["product_id"] == "openhub"
        assert d["tier"] == 1


class TestPortfolioState:
    def test_new_portfolio_empty(self):
        state = PortfolioState()
        assert state.products == {}
        assert state.version == DB_SCHEMA_VERSION

    def test_register_product(self):
        state = PortfolioState()
        p = ProductConfig(product_id="claw-protect", tier=1, name="Claw Protect")
        state.register_product(p)
        assert "claw-protect" in state.products
        assert state.products["claw-protect"].name == "Claw Protect"

    def test_get_health_vector(self):
        state = PortfolioState()
        p = ProductConfig(product_id="claw-protect", tier=1, name="Claw Protect")
        state.register_product(p)
        hv = state.get_health_vector("claw-protect")
        assert hv is not None
        assert hv.healthy is True  # default
        assert hv.error_rate == 0.0

    def test_get_unknown_product_raises(self):
        state = PortfolioState()
        with pytest.raises(KeyError):
            state.get_health_vector("nonexistent")


class TestTrafficLightZone:
    def test_zone_from_severity(self):
        assert TrafficLightZone.from_event("exception", 0.05) == TrafficLightZone.YELLOW
        assert TrafficLightZone.from_event("exception", 0.9) == TrafficLightZone.RED
        assert TrafficLightZone.from_event("dependency_update", 0.0) == TrafficLightZone.GREEN
        assert TrafficLightZone.from_event("security_alert", 0.5) == TrafficLightZone.RED
        assert TrafficLightZone.from_event("cache_clear", 0.0) == TrafficLightZone.GREEN
        assert TrafficLightZone.from_event("build_failure", 0.0) == TrafficLightZone.YELLOW
        assert TrafficLightZone.from_event("data_exfiltration", 0.0) == TrafficLightZone.RED

    def test_zone_autoaction(self):
        assert TrafficLightZone.GREEN.autoaction is True
        assert TrafficLightZone.YELLOW.autoaction is False
        assert TrafficLightZone.RED.autoaction is False
        assert TrafficLightZone.YELLOW.human_required is True
        assert TrafficLightZone.RED.requires_immediate is True


class TestConstitution:
    def test_check_path_safe(self):
        c = Constitution()
        # Safe paths
        assert c.check_path("src/components/Button.tsx") is True
        assert c.check_path("tests/test_brain.py") is True
        assert c.check_path("config/.env.example") is True
        assert c.check_path("data/ceo_state.json") is True
        assert c.check_path("lane/coding/file.py") is True

    def test_check_path_prohibited(self):
        c = Constitution()
        # Prohibited paths
        assert c.check_path("auth/jwt.py") is False
        assert c.check_path("billing/stripe_client.py") is False
        assert c.check_path("legal/nda.py") is False
        assert c.check_path("security/keys.py") is False
        assert c.check_path("../etc/passwd") is False
        assert c.check_path("internal/secrets.json") is False

    def test_check_spending_never(self):
        c = Constitution()
        assert c.check_action("spend_money", {"amount": 100}) is False
        assert c.check_action("spend_money", {"amount": 1}) is False

    def test_check_action_customer_communication_scripted(self):
        c = Constitution()
        assert c.check_action("scripted_customer_email", {"template_id": "welcome"}) is True
        assert c.check_action("scripted_customer_email", {}) is False

    def test_check_action_merge_conditions(self):
        c = Constitution()
        # Prohibited dirs always block
        assert (
            c.check_action(
                "merge_pr",
                {"target": "main", "files": ["auth/jwt.py"]},
            )
            is False
        )
        # Staging is fine
        assert (
            c.check_action(
                "merge_pr",
                {"target": "staging", "files": ["src/app.py"]},
            )
            is True
        )

    def test_get_constitution_summary(self):
        c = Constitution()
        summary = c.get_summary()
        assert "billing" in summary["prohibited_dirs"]
        assert "spend_money" in summary["never_autonomous"]
        assert "scripted_customer_email" in summary["conditional_autonomy"]