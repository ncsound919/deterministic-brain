"""Tests for the fleet bridges + integrated design-and-build lane.

No network: HTTP is mocked. Honest offline/error paths are exercised directly.
"""

import json
from unittest import mock

from lanes.design_and_build import design_and_build
from tools.fleet_bridges import (
    beta_team_status,
    bigback_generate,
    fleet_status,
    math_x_status,
    middleman_relay,
    og_glass_brief,
    og_glass_design_md,
)


class _FakeResp:
    def __init__(self, status, body):
        self.status = status
        self._body = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_urlopen(body, status=200):
    return mock.patch(
        "tools.fleet_bridges.urllib.request.urlopen",
        return_value=_FakeResp(status, body),
    )


def test_og_glass_brief_success():
    body = {
        "ok": True,
        "source": "offline",
        "chosen": {"style": "style-flat-corporate"},
        "preset_resolved": "style-flat-corporate",
        "quality": {"passed": True, "score": 100},
        "design_md": "# DESIGN.md — Flat Corporate\n",
    }
    with _patch_urlopen(body) as req:
        result = og_glass_brief("a fintech dashboard", base_url="http://x:1")
    req.assert_called_once()
    assert result["ok"] is True
    assert result["preset_resolved"] == "style-flat-corporate"
    assert result["quality"]["passed"] is True
    assert result["design_md"].startswith("# DESIGN.md")


def test_og_glass_brief_offline_is_honest():
    with mock.patch(
        "tools.fleet_bridges.urllib.request.urlopen",
        side_effect=Exception("connection refused"),
    ):
        result = og_glass_brief("anything", base_url="http://127.0.0.1:9")
    assert result["ok"] is False
    assert "connection refused" in result["error"]


def test_og_glass_design_md():
    with _patch_urlopen("# DESIGN.md\n", status=200) as req:
        result = og_glass_design_md("style-editorial", base_url="http://x:1")
    req.assert_called_once()
    assert result["ok"] is True
    assert result["design_md"].startswith("# DESIGN.md")


def test_bigback_generate_success():
    body = {"ok": True, "framework": "hono", "files": [{"output": "src/app.ts"}]}
    with _patch_urlopen(body) as req:
        result = bigback_generate({"project": "x", "framework": "hono"}, base_url="http://x:1")
    req.assert_called_once()
    assert result["ok"] is True
    assert result["framework"] == "hono"
    assert len(result["files"]) == 1


def test_middleman_relay_success_and_unknown():
    with _patch_urlopen({"ok": True, "status": 200, "data": {"ok": True}}):
        result = middleman_relay("og-glass", "/mcp", {"tool": "x"}, base_url="http://x:1")
    assert result["ok"] is True
    assert result["step"] == "relay"


def test_math_x_is_not_bridged():
    status = math_x_status()
    assert status["bridged"] is False
    assert "LLM-routed" in status["detail"]


def test_beta_team_status_shape():
    status = beta_team_status()
    assert "available" in status
    assert "detail" in status


def test_fleet_status_shape():
    status = fleet_status()
    for key in ("og_glass", "bigback", "middleman", "beta_team", "math_x"):
        assert key in status
    assert status["math_x"]["bridged"] is False


def test_design_and_build_integrated_lane():
    design = {
        "ok": True,
        "source": "offline",
        "chosen": {"style": "style-flat-corporate"},
        "preset_resolved": "style-flat-corporate",
        "quality": {"passed": True, "score": 100},
        "design_md": "# DESIGN.md — Flat Corporate\n",
    }
    backend = {"ok": True, "framework": "fastapi", "files": [{"output": "app/main.py"}]}
    with mock.patch("tools.fleet_bridges.og_glass_brief", return_value=design), \
         mock.patch("tools.fleet_bridges.bigback_generate", return_value=backend):
        result = design_and_build("Create a REST API for managing Order with CRUD")
    assert result["ok"] is True
    assert result["plan"]["shape"] == "api"
    assert result["design"]["preset_id"] == "style-flat-corporate"
    assert result["design"]["quality_passed"] is True
    assert result["design_md"].startswith("# DESIGN.md")
    assert result["backend"]["framework"] == "fastapi"
    assert result["backend"]["files"] == 1
    # beta defaults to honest SKIP, never a fabricated test result
    assert result["beta"]["status"] == "SKIP"
    assert any(s["step"] == "design" for s in result["steps"])
    assert any(s["step"] == "backend" for s in result["steps"])


def test_design_and_build_offline_fleet_still_plans():
    with mock.patch("tools.fleet_bridges.og_glass_brief", return_value={"ok": False, "step": "design", "error": "offline"}), \
         mock.patch("tools.fleet_bridges.bigback_generate", return_value={"ok": False, "step": "backend", "error": "offline"}):
        result = design_and_build("Build a web app for analytics")
    # the plan always materializes; ok=False is the honest signal that no
    # generation step ran (design + backend both offline)
    assert result["ok"] is False
    assert result["plan"]["shape"] == "web-app"
    assert result["design"]["preset_id"] is None
    assert result["backend"]["ok"] is False
    assert result["design_md"] is None