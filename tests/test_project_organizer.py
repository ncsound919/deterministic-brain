"""Tests for the deterministic project organizer + organize-and-code lane."""

from lanes.organize_and_code import _mentioned_entities, organize_and_code
from planners.project_organizer import detect_shape, goal_exports, organize_goal, project_name, render_plan_markdown


def test_shape_detection():
    assert detect_shape("Build a full stack app with react and express") == "full-stack"
    assert detect_shape("Create a REST API with CRUD for users") == "api"
    assert detect_shape("Build a React dashboard") == "web-app"
    assert detect_shape("A python package for math") == "python-pkg"
    assert detect_shape("do the thing") == "generic"
    assert detect_shape("anything", requested="cli") == "cli"


def test_project_name_and_exports():
    assert project_name("Create lib/math.js exporting add") == "math"
    assert project_name("Build a CLI tool called widgetizer") == "widgetizer"
    assert project_name("Create a REST API with CRUD for users") == "users"
    assert goal_exports("exporting add(a,b) and sub(a,b)") == ["add", "sub"]


def test_organize_goal_is_deterministic():
    a = organize_goal("Create a REST API for managing orders with CRUD")
    b = organize_goal("Create a REST API for managing orders with CRUD")
    assert a == b
    assert a["shape"] == "api"
    assert "src/routes" in a["directories"]
    assert a["tasks"][0]["phase"] == "plan"
    assert a["tasks"][-1]["phase"] == "verify"


def test_render_plan_markdown():
    plan = organize_goal("Build a React dashboard for analytics")
    md = render_plan_markdown(plan)
    assert md.startswith("# Project Plan —")
    assert "## Layout" in md and "## Tasks" in md
    assert "**verify**" in md


def test_mentioned_entities():
    assert _mentioned_entities("Implement CRUD for Order and Invoice") == ["Order", "Invoice"]
    assert _mentioned_entities("just a web app") == []


def test_organize_and_code_lane_plan_and_contracts():
    result = organize_and_code("Create a REST API for managing Order with CRUD")
    assert result["ok"] is True
    assert result["plan"]["shape"] == "api"
    assert "Order" in result["contracts"]
    # BLMCP is spawned via the bridge; if it cannot run in this env the
    # contract must be an honest error, never a fabricated pass.
    contract = result["contracts"]["Order"]
    assert "ok" in contract
    assert "error" in contract or "result" in contract


def test_organize_and_code_without_entities():
    result = organize_and_code("Build a generic helper library")
    assert result["ok"] is True
    assert result["contracts"] == {"_note": "no entity-like names detected in the goal"}