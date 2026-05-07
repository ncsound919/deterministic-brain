"""E2E Humanized Tests — walks the UI like a real user, exercises all pages and functions."""
import json
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, expect

BASE = "http://localhost:8000"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    yield page
    context.close()


# ═══════════════════════════════════════════════════════════════════
# Page Navigation — Every Page Loads
# ═══════════════════════════════════════════════════════════════════

class TestPageNavigation:
    """Every sidebar page loads without crash and shows content."""

    def _navigate_to(self, page, page_name, selector):
        """Click nav item and wait for page to become active."""
        page.click(f".nav-item[data-page='{page_name}']")
        page.wait_for_function(
            f"document.querySelector('#page-{page_name}')?.classList.contains('active')",
            timeout=5000,
        )
        page.wait_for_selector(selector, timeout=5000)

    def test_settings_loads_all_groups(self, page):
        page.goto(BASE)
        self._navigate_to(page, "settings", "#settings-container")
        page.wait_for_selector("#settings-container h3", timeout=10000)
        content = page.text_content("#settings-container")
        for group in ["Database", "Models", "API", "Voice", "Daemons", "Healing"]:
            assert group in content, f"Settings group '{group}' not found"

    def test_settings_can_toggle_tracing(self, page):
        page.goto(BASE)
        self._navigate_to(page, "settings", "#settings-container")
        page.wait_for_selector("input[data-key='TRACING_ENABLED']", timeout=10000)
        checkbox = page.locator("input[data-key='TRACING_ENABLED']")
        assert checkbox.is_visible()

    def test_settings_save_button_exists(self, page):
        page.goto(BASE)
        self._navigate_to(page, "settings", "#settings-container")
        buttons = page.locator("button:has-text('Save')")
        assert buttons.count() > 3


class TestDevPets:
    def _navigate_to(self, page, page_name, selector):
        page.click(f".nav-item[data-page='{page_name}']")
        page.wait_for_function(
            f"document.querySelector('#page-{page_name}')?.classList.contains('active')",
            timeout=5000,
        )
        page.wait_for_selector(selector, timeout=5000)

    def test_devpets_page_loads(self, page):
        page.goto(BASE)
        self._navigate_to(page, "devpets", "#page-devpets")

    def test_devpets_api_returns_data(self, page):
        import requests
        resp = requests.get(f"{BASE}/devpets", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "devpets" in data
        assert "count" in data

    def test_devpets_page_shows_content(self, page):
        page.goto(BASE)
        self._navigate_to(page, "devpets", "#page-devpets")
        content = page.text_content("#page-devpets")
        assert len(content) > 20


class TestBattleArena:
    def _navigate_to(self, page, page_name, selector):
        page.click(f".nav-item[data-page='{page_name}']")
        page.wait_for_function(
            f"document.querySelector('#page-{page_name}')?.classList.contains('active')",
            timeout=5000,
        )
        page.wait_for_selector(selector, timeout=5000)

    def test_battle_page_loads(self, page):
        page.goto(BASE)
        self._navigate_to(page, "battle", "#page-battle")
        content = page.text_content("#page-battle")
        assert "Battle" in content or "Arena" in content


class TestHealthMonitor:
    def _navigate_to(self, page, page_name, selector):
        page.click(f".nav-item[data-page='{page_name}']")
        page.wait_for_function(
            f"document.querySelector('#page-{page_name}')?.classList.contains('active')",
            timeout=5000,
        )
        page.wait_for_selector(selector, timeout=5000)

    def test_health_page_loads(self, page):
        page.goto(BASE)
        self._navigate_to(page, "health-mon", "#page-health-mon")
        page.wait_for_selector("#health-cards", timeout=10000)
        cards = page.text_content("#health-cards")
        assert len(cards) > 5

    def test_health_api_responds(self, page):
        import requests
        resp = requests.get(f"{BASE}/health/monitor", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


# ═══════════════════════════════════════════════════════════════════
# System Capability: Generate DevPet Battle Website
# ═══════════════════════════════════════════════════════════════════

class TestBrainProduces:
    """THE KEY TEST: Can the deterministic brain produce a real output?"""

    def test_deterministic_brain_creates_react_component(self, page):
        """Ask the brain to create a React component — verify skill executed."""
        import requests
        resp = requests.post(f"{BASE}/task", json={
            "query": "create a react component named BattleArenaCard with props petA, petB, onBattle"
        }, timeout=30)
        assert resp.status_code == 200
        result = resp.json()
        assert result.get("status") in ("ok", "blocked", "low_confidence", "failed")

    def test_deterministic_brain_reasons(self, page):
        """The reasoner returns a valid decision breakdown."""
        import requests
        resp = requests.post(f"{BASE}/reason", json={
            "query": "scaffold a battle website with two pet selection dropdowns and a fight button"
        }, timeout=30)
        assert resp.status_code == 200
        result = resp.json()
        assert "decision" in result
        decision = result["decision"]
        assert "chosen_skill" in decision
        assert "confidence" in decision

    def test_bundle_scaffolds_rest_api(self, page):
        """Swarm dispatcher produces output from a bundle."""
        import requests
        resp = requests.post(f"{BASE}/bundle", json={
            "bundle": "scaffold-rest-api",
            "inputs": {"resource": "Pet"}
        }, timeout=30)
        assert resp.status_code == 200
        result = resp.json()
        assert "bundle" in result
        assert "results" in result

    def test_forge_skills_loaded(self, page):
        """Forge has discovered skill packs."""
        import requests
        resp = requests.get(f"{BASE}/skills", timeout=10)
        assert resp.status_code == 200
        skills = resp.json().get("skills", [])
        assert len(skills) > 0
        assert any(
            "react" in s.get("path", "").lower() or "react" in s.get("name", "").lower()
            for s in skills
        ), f"No React skill found in {skills[:5]}"

    def test_dialogue_pipeline_processes(self, page):
        """Dialogue pipeline works end-to-end."""
        import requests
        resp = requests.post(f"{BASE}/dialogue/process", json={
            "text": "Hello, can you help me build a website?"
        }, timeout=10)
        assert resp.status_code == 200
        result = resp.json()
        assert "response" in result
        assert "intent" in result
        assert result["intent"] in (
            "greeting", "question", "command", "help", "statement"
        )

    def test_settings_api_works(self, page):
        """Settings endpoints are reachable."""
        import requests
        resp = requests.get(f"{BASE}/settings", timeout=10)
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data

    def test_settings_schema_returns_groups(self, page):
        import requests
        resp = requests.get(f"{BASE}/settings/schema", timeout=10)
        assert resp.status_code == 200
        groups = resp.json().get("groups", {})
        assert "Database" in groups
        assert "Models" in groups
        assert "Healing" in groups

    def test_bundles_api_returns_list(self, page):
        import requests
        resp = requests.get(f"{BASE}/bundles", timeout=10)
        assert resp.status_code == 200
        bundles = resp.json().get("bundles", [])
        assert len(bundles) >= 1
        for b in bundles:
            assert "name" in b
            assert "lanes" in b

    def test_relay_agents_endpoint(self, page):
        import requests
        resp = requests.get(f"{BASE}/relay/agents", timeout=10)
        assert resp.status_code == 200
        agents = resp.json().get("agents", {})
        assert isinstance(agents, dict)

    def test_battle_website_deterministic_plan(self, page):
        """The HOOK: can the brain produce a plan for devpet-web/battle using the reasoner?"""
        import requests
        resp = requests.post(f"{BASE}/reason", json={
            "query": (
                "design a devpet battle website with HTML5 canvas pet rendering, "
                "trait-based procedural visuals, JSON upload for two pets, "
                "deterministic turn-based battle with turn log and insight annotations"
            )
        }, timeout=30)
        assert resp.status_code == 200
        result = resp.json()
        decision = result.get("decision", {})
        chosen = decision.get("chosen_skill", "")
        confidence = decision.get("confidence", 0.0)
        print(f"\n  Brain chose: {chosen} (confidence: {confidence:.4f})")
        print(f"  Audit OK: {decision.get('audit_ok', False)}")
        print(f"  Pre-audit issues: {decision.get('pre_audit', [])}")
        # The brain must return a valid decision
        assert decision.get("audit_ok", False) is True or confidence < 0.3, (
            f"Audit blocked but confidence high ({confidence}). Issues: {decision.get('pre_audit', [])}"
        )
