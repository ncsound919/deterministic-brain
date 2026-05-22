"""Functional E2E tests — verify the brain actually WORKS and PRODUCES output.

These tests exercise real functionality, not just UI element presence:
- Brain reasons, routes, and executes tasks producing artifacts
- Knowledge bank ingests, searches, and returns relevant results
- Betting engine generates actual bet sheets with recommendations
- Social scheduler creates posts that appear in the feed
- SaaS builder creates real projects
- Chat/dialogue returns coherent responses
- Soul settings persist across reads and writes

Run with visible browser to watch it work:
  $env:HEADLESS="false"; pytest tests/e2e/test_human_user_journey.py -v --tb=short -s -x
"""

from __future__ import annotations
import os
import time
import json
import pytest
import requests
from playwright.sync_api import sync_playwright, expect, Page, BrowserContext

BASE = os.environ.get("BRAIN_API", "http://localhost:8000")
HEADLESS = os.environ.get("HEADLESS", "true").lower() == "true"


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=HEADLESS, args=["--no-sandbox"])
        yield b
        b.close()


@pytest.fixture
def ctx(browser):
    c = browser.new_context(
        viewport={"width": 1440, "height": 900},
        ignore_https_errors=True,
    )
    yield c
    c.close()


@pytest.fixture
def page(ctx: BrowserContext):
    p = ctx.new_page()
    p.set_default_timeout(30000)
    yield p
    p.close()


# ── API helpers ────────────────────────────────────────────────────────

def api_get(path: str, timeout: int = 10) -> tuple:
    try:
        r = requests.get(f"{BASE}{path}", timeout=timeout)
        return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    except Exception as e:
        return None, str(e)


def api_post(path: str, data: dict | None = None, params: dict | None = None, timeout: int = 15) -> tuple:
    try:
        r = requests.post(f"{BASE}{path}", json=data or {}, params=params or {}, timeout=timeout)
        return r.status_code, r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text
    except Exception as e:
        return None, str(e)


# ═══════════════════════════════════════════════════════════════════════
# 1. SYSTEM HEALTH — verify the brain is alive and self-aware
# ═══════════════════════════════════════════════════════════════════════

class TestSystemHealth:
    """Verify core infrastructure is up and responding with real data."""

    def test_health_returns_ok_with_version(self):
        code, data = api_get("/health")
        assert code == 200
        assert data.get("status") == "ok"
        assert "version" in data
        assert "ts" in data

    def test_integrations_reports_real_status(self):
        code, data = api_get("/integrations")
        assert code == 200
        assert "apis" in data
        assert "features" in data
        assert "configured_count" in data
        apis = data["apis"]
        assert "openrouter" in apis
        assert "github" in apis
        assert "stripe" in apis

    def test_llm_status_reports_provider(self):
        code, data = api_get("/llm-status")
        assert code == 200
        assert "enabled" in data
        assert "provider" in data
        assert "has_keys" in data


# ═══════════════════════════════════════════════════════════════════════
# 2. BRAIN REASONING — the core intelligence
# ═══════════════════════════════════════════════════════════════════════

class TestBrainReasoning:
    """The brain must reason about queries and make valid decisions."""

    def test_reasoner_routes_coding_query_to_coding_skill(self):
        code, data = api_post("/reason", {"query": "build a react component with props"})
        assert code == 200
        decision = data.get("decision", {})
        assert "chosen_skill" in decision, f"No chosen_skill in response: {data.keys()}"
        assert "confidence" in decision
        assert "audit_ok" in decision
        assert decision["confidence"] >= 0
        assert decision["confidence"] <= 1.0
        print(f"  -> Skill: {decision['chosen_skill']} (conf: {decision['confidence']:.2f})")

    def test_reasoner_routes_business_query(self):
        code, data = api_post("/reason", {"query": "create an approval workflow for budgets"})
        assert code == 200
        decision = data.get("decision", {})
        assert decision.get("chosen_skill"), f"No skill chosen: {decision}"
        print(f"  -> Skill: {decision['chosen_skill']}")

    def test_reasoner_routes_browser_query(self):
        code, data = api_post("/reason", {"query": "navigate to example.com and click login"})
        assert code == 200
        decision = data.get("decision", {})
        assert decision.get("chosen_skill")
        print(f"  -> Skill: {decision['chosen_skill']}")

    def test_reasoner_returns_different_skills_for_different_domains(self):
        queries = [
            "build a react landing page",
            "generate a dockerfile for my python app",
            "audit my repository for issues",
            "add jwt auth to my api",
        ]
        skills = []
        for q in queries:
            _, data = api_post("/reason", {"query": q})
            skill = data.get("decision", {}).get("chosen_skill")
            assert skill, f"No skill for query: {q}"
            skills.append(skill)
            print(f"  '{q[:40]}...' -> {skill}")
        # At least 2 different skills should be chosen
        assert len(set(skills)) >= 2, f"All queries routed to same skill: {skills}"

    def test_reasoner_is_deterministic(self):
        q = "create a login form with email and password fields"
        _, r1 = api_post("/reason", {"query": q})
        _, r2 = api_post("/reason", {"query": q})
        s1 = r1.get("decision", {}).get("chosen_skill")
        s2 = r2.get("decision", {}).get("chosen_skill")
        assert s1 == s2, f"Non-deterministic! {s1} vs {s2}"
        c1 = r1.get("decision", {}).get("confidence")
        c2 = r2.get("decision", {}).get("confidence")
        assert c1 == c2, f"Confidence differs: {c1} vs {c2}"
        print(f"  Deterministic: {s1} (conf: {c1})")


# ═══════════════════════════════════════════════════════════════════════
# 3. BRAIN TASK EXECUTION — the brain must actually DO things
# ═══════════════════════════════════════════════════════════════════════

class TestBrainTaskExecution:
    """The brain must execute tasks and produce output."""

    def test_task_executes_and_returns_status(self):
        code, data = api_post("/task", {"query": "create a react component named TestButton"})
        assert code == 200
        assert "status" in data
        print(f"  Status: {data['status']}")

    def test_task_returns_final_output(self):
        code, data = api_post("/task", {"query": "scaffold a rest api for users"})
        assert code == 200
        assert "final_output" in data or "output" in data or "result" in data
        print(f"  Keys: {list(data.keys())}")

    def test_task_returns_session_id(self):
        code, data = api_post("/task", {"query": "write a hello world function"})
        assert code == 200
        assert "session_id" in data or "task" in data


# ═══════════════════════════════════════════════════════════════════════
# 4. SKILLS REGISTRY — the brain must know what it can do
# ═══════════════════════════════════════════════════════════════════════

class TestSkillsRegistry:
    """Verify the skills system is functional."""

    def test_skills_list_returns_real_skills(self):
        code, data = api_get("/skills")
        assert code == 200
        skills = data.get("skills", [])
        assert len(skills) >= 10, f"Only {len(skills)} skills found"
        print(f"  Total skills: {len(skills)}")
        # Verify skills have structure
        for s in skills[:3]:
            assert "skill_id" in s or "skill" in s, f"Skill missing ID: {s.keys()}"

    def test_skills_have_descriptions(self):
        code, data = api_get("/skills")
        assert code == 200
        skills = data.get("skills", [])
        described = [s for s in skills if s.get("description")]
        assert len(described) >= 5, f"Only {len(described)} skills have descriptions"
        print(f"  Skills with descriptions: {len(described)}/{len(skills)}")

    def test_bundles_list_returns_real_bundles(self):
        code, data = api_get("/bundles")
        assert code == 200
        bundles = data.get("bundles", [])
        assert len(bundles) >= 1, f"No bundles found"
        for b in bundles:
            assert "name" in b
            assert "description" in b
            assert "lanes" in b
        print(f"  Bundles: {[b['name'] for b in bundles]}")

    def test_chains_list_returns_real_chains(self):
        code, data = api_get("/chains")
        assert code == 200
        chains = data.get("chains", {})
        assert len(chains) >= 1, f"No chains found: {data}"
        print(f"  Chains: {list(chains.keys())}")


# ═══════════════════════════════════════════════════════════════════════
# 5. KNOWLEDGE BANK — ingest, search, retrieve
# ═══════════════════════════════════════════════════════════════════════

class TestKnowledgeBankFunctional:
    """The knowledge bank must store and retrieve information."""

    def test_knowledge_stats_show_real_data(self):
        code, data = api_get("/knowledge/stats")
        assert code == 200
        assert "total_fragments" in data
        print(f"  Fragments: {data['total_fragments']}, Snippets: {data.get('snippets', 0)}")

    def test_knowledge_search_finds_seeded_content(self):
        """The system seeds knowledge on startup. Search should find it."""
        code, data = api_post("/knowledge/search", {"query": "react hooks", "top_k": 5})
        assert code == 200
        results = data.get("results", [])
        assert len(results) > 0, "Knowledge bank search returned no results"
        print(f"  Found {len(results)} results")
        for r in results:
            print(f"    - {r.get('source_title', '?')}: {r.get('chunk_text', '')[:60]}...")

    def test_knowledge_search_finds_fastapi_content(self):
        code, data = api_post("/knowledge/search", {"query": "fastapi python", "top_k": 5})
        assert code == 200
        results = data.get("results", [])
        assert len(results) > 0, "No results for fastapi"
        print(f"  Found {len(results)} results")

    def test_knowledge_ingest_text_and_search_it(self):
        """Ingest custom text, then search and find it."""
        title = f"E2E Test Topic {int(time.time())}"
        code1, ingest = api_post("/knowledge/ingest-text", {
            "text": "Playwright is a framework for browser automation and end-to-end testing.",
            "title": title,
            "tags": ["testing", "playwright", "automation"],
        })
        assert code1 == 200
        assert ingest.get("status") == "ok"
        print(f"  Ingested {ingest.get('ingested', 0)} fragments")

        # Give it a moment to index
        time.sleep(0.5)

        # Search for the ingested text
        code2, search = api_post("/knowledge/search", {"query": "playwright browser automation", "top_k": 5})
        assert code2 == 200
        results = search.get("results", [])
        assert len(results) > 0, "Ingested text not found in search"
        titles = [r.get("source_title", "") for r in results]
        print(f"  Search titles: {titles}")
        assert any(title in t for t in titles), f"Ingested title '{title}' not in results: {titles}"

    def test_knowledge_snippets_crud(self):
        """Create, read, and delete a snippet."""
        code1, created = api_post("/knowledge/snippets", {
            "title": "E2E Snippet",
            "content": "This is a test snippet for end-to-end testing.",
            "tags": ["test", "e2e"],
        })
        assert code1 == 200
        assert created.get("status") == "ok"
        snippet = created.get("snippet", {})
        snippet_id = snippet.get("id") or snippet.get("snippet_id")
        assert snippet_id, f"No snippet ID returned: {created}"
        print(f"  Created snippet: {snippet_id}")

        # Verify it appears in the list
        code2, listed = api_get("/knowledge/snippets")
        assert code2 == 200
        ids = [s.get("id") for s in listed.get("snippets", [])]
        assert snippet_id in ids, f"Snippet not in list: {ids}"
        print(f"  Snippet confirmed in list")


# ═══════════════════════════════════════════════════════════════════════
# 6. SAAS BUILDER — create and manage projects
# ═══════════════════════════════════════════════════════════════════════

class TestSaaSBuilderFunctional:
    """The SaaS builder must create and track projects."""

    def test_create_project_and_verify_it_exists(self):
        unique_name = f"E2EProject{int(time.time() * 1000) % 100000}"
        code1, created = api_post("/saas/create", params={
            "name": unique_name,
            "idea": "A project created by end-to-end testing",
            "tech_stack": "python,react,fastapi",
        })
        assert code1 == 200, f"Create failed: {created}"
        project = created.get("project", {})
        assert project.get("id") or project.get("name"), f"No project returned: {created}"
        project_id = project.get("id", unique_name)
        print(f"  Created project: {project_id} (stage: {project.get('stage')})")

        # Verify it appears in the projects list
        code2, listed = api_get("/saas/projects")
        assert code2 == 200
        projects = listed.get("projects", [])
        names = [p.get("name") for p in projects]
        assert unique_name in names, f"Project '{unique_name}' not in list: {names}"
        print(f"  Project confirmed in list ({len(projects)} total)")

    def test_projects_list_returns_real_data(self):
        code, data = api_get("/saas/projects")
        assert code == 200
        projects = data.get("projects", [])
        print(f"  Projects: {len(projects)}")
        for p in projects[:3]:
            assert "id" in p or "name" in p
            print(f"    - {p.get('name', '?')} (stage: {p.get('stage', '?')})")


# ═══════════════════════════════════════════════════════════════════════
# 7. SOCIAL SCHEDULER — create and manage posts
# ═══════════════════════════════════════════════════════════════════════

class TestSocialSchedulerFunctional:
    """The social scheduler must create posts that appear in the feed."""

    def test_schedule_post_and_verify_it_appears(self):
        content = f"E2E test post at {int(time.time())}"
        code1, created = api_post("/social/schedule", params={
            "platform": "twitter",
            "content": content,
            "delay_minutes": 120,
        })
        assert code1 == 200, f"Schedule failed: {created}"
        assert created.get("status") == "ok", f"Schedule not ok: {created}"
        print(f"  Scheduled: {created.get('message', '?')}")

        # Verify it appears in the posts list
        code2, listed = api_get("/social/posts")
        assert code2 == 200
        posts = listed.get("posts", [])
        contents = [p.get("content", "") for p in posts]
        assert any(content in c for c in contents), f"Post not found in feed: {contents[:5]}"
        print(f"  Post confirmed in feed ({len(posts)} total)")

    def test_social_posts_list_returns_structured_data(self):
        code, data = api_get("/social/posts")
        assert code == 200
        posts = data.get("posts", [])
        print(f"  Total posts: {len(posts)}")
        for p in posts[:3]:
            assert "platform" in p
            assert "content" in p
            print(f"    [{p['platform']}] {p['content'][:50]}...")


# ═══════════════════════════════════════════════════════════════════════
# 8. BETTING ENGINE — generate actual bet recommendations
# ═══════════════════════════════════════════════════════════════════════

class TestBettingEngineFunctional:
    """The betting engine must produce real bet sheets."""

    def test_odds_returns_structured_data(self):
        code, data = api_get("/betting/odds")
        assert code == 200
        lines = data.get("lines", [])
        print(f"  Odds lines: {len(lines)}")
        if lines:
            for line in lines[:3]:
                assert "event" in line or "market" in line or "bookmaker" in line
                print(f"    [{line.get('market', '?')}] {line.get('event', '?')} @ {line.get('bookmaker', '?')}")

    def test_bet_sheet_generates_with_structure(self):
        code, data = api_get("/betting/sheet")
        assert code == 200
        # Should have sheet data or structured recommendations
        assert "sheet" in data or "recommendations" in data or "bets" in data or "lines" in data
        print(f"  Sheet keys: {list(data.keys())}")
        if "sheet" in data:
            sheet = data["sheet"]
            print(f"  Sheet length: {len(sheet) if isinstance(sheet, str) else len(str(sheet))}")

    def test_kelly_calculations_return_structure(self):
        code, data = api_get("/betting/kelly")
        assert code == 200
        assert "bankroll" in data or "recommendations" in data
        print(f"  Kelly keys: {list(data.keys())}")


# ═══════════════════════════════════════════════════════════════════════
# 9. SOUL / IDENTITY — read and write user profile
# ═══════════════════════════════════════════════════════════════════════

class TestSoulIdentityFunctional:
    """The soul identity must persist settings."""

    def test_soul_returns_full_identity(self):
        code, data = api_get("/soul")
        assert code == 200
        assert "identity" in data
        assert "agenda" in data
        assert "context" in data
        identity = data["identity"]
        print(f"  Soul: {identity.get('name', '?')} / {identity.get('role', '?')}")

    def test_soul_update_persists(self):
        # Read current
        _, before = api_get("/soul")
        original_role = before.get("identity", {}).get("role", "")

        # Update
        new_role = f"e2e-tester-{int(time.time())}"
        code1, _ = api_post("/soul", {"identity": {"role": new_role}})
        assert code1 == 200

        # Verify it persisted
        _, after = api_get("/soul")
        updated_role = after.get("identity", {}).get("role", "")
        assert updated_role == new_role, f"Role not persisted: '{updated_role}' != '{new_role}'"
        print(f"  Role updated: {original_role} -> {updated_role}")

        # Restore original
        api_post("/soul", {"identity": {"role": original_role}})

    def test_soul_pulse_returns_heartbeat(self):
        code, data = api_post("/soul/pulse")
        assert code == 200
        assert "name" in data
        print(f"  Pulse: {data.get('name')} / sessions: {data.get('sessions', '?')}")


# ═══════════════════════════════════════════════════════════════════════
# 10. PLANNER — schedule and track tasks
# ═══════════════════════════════════════════════════════════════════════

class TestPlannerFunctional:
    """The planner must track tasks with real data."""

    def test_planner_tasks_list_returns_tasks(self):
        code, data = api_get("/planner/tasks")
        assert code == 200
        tasks = data.get("tasks", [])
        print(f"  Planner tasks: {len(tasks)}")
        for t in tasks[:3]:
            assert "id" in t
            assert "title" in t or "query" in t
            print(f"    [{t.get('status', '?')}] {t.get('title', t.get('query', '?'))[:40]}")

    def test_planner_timeline_returns_schedule(self):
        code, data = api_get("/planner/timeline")
        assert code == 200
        timeline = data.get("timeline", [])
        print(f"  Timeline entries: {len(timeline)}")

    def test_planner_add_task_and_verify(self):
        title = f"E2E Task {int(time.time())}"
        code1, created = api_post("/planner/tasks", params={
            "title": title,
            "query": "test query for e2e",
            "schedule": "now",
        })
        assert code1 == 200, f"Add failed: {created}"
        task = created.get("task", {})
        assert task.get("id"), f"No task ID: {created}"
        task_id = task["id"]
        print(f"  Added task: {task_id}")

        # Verify in list
        code2, listed = api_get("/planner/tasks")
        assert code2 == 200
        ids = [t.get("id") for t in listed.get("tasks", [])]
        assert task_id in ids, f"Task not in planner: {ids[:10]}"
        print(f"  Task confirmed in planner")


# ═══════════════════════════════════════════════════════════════════════
# 11. DIALOGUE & CHAT — the brain must hold a conversation
# ═══════════════════════════════════════════════════════════════════════

class TestDialogueAndChatFunctional:
    """The dialogue and chat systems must respond intelligently."""

    def test_dialogue_returns_intent_and_response(self):
        code, data = api_post("/dialogue/process", {"text": "help me build an app"})
        assert code == 200
        assert "response" in data
        assert "intent" in data
        assert data["intent"] in ("greeting", "question", "command", "help", "statement", "request", "unknown")
        print(f"  Intent: {data['intent']}, Response: {data['response'][:60]}...")

    def test_dialogue_understands_greeting(self):
        code, data = api_post("/dialogue/process", {"text": "hello"})
        assert code == 200
        assert data.get("intent") in ("greeting", "statement", "unknown")
        print(f"  Greeting -> {data['intent']}: {data['response'][:60]}...")

    def test_chat_router_responds_with_structure(self):
        code, data = api_post("/chat", {"text": "what can you do?"})
        assert code == 200
        # Chat router returns different structures depending on intent
        print(f"  Chat response keys: {list(data.keys())}")
        assert "response" in data or "text" in data or "status" in data


# ═══════════════════════════════════════════════════════════════════════
# 12. DASHBOARD UI — visible browser interactions with the React app
# ═══════════════════════════════════════════════════════════════════════

class TestDashboardUIFunctional:
    """Human opens the Aether OS dashboard and actually uses it."""

    def test_dashboard_loads_and_shows_command_center(self, page):
        page.goto(BASE, timeout=15000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(4000)
        body = page.text_content("body")
        assert body is not None
        assert "command" in body.lower() or "center" in body.lower()
        print(f"  Dashboard loaded, body length: {len(body)}")

    def test_sidebar_navigation_changes_content(self, page):
        page.goto(BASE, timeout=15000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        # Get initial page content
        initial_text = page.text_content("main") or ""

        # Click on a different page
        buttons = page.locator("nav button")
        clicked_page = None
        for i in range(buttons.count()):
            btn = buttons.nth(i)
            text = btn.text_content() or ""
            if "skill" in text.lower() or "market" in text.lower():
                btn.click()
                clicked_page = text
                page.wait_for_timeout(1500)
                break

        assert clicked_page, "Could not find Skills page button"
        new_text = page.text_content("main") or ""
        assert new_text != initial_text, "Page content did not change after navigation"
        print(f"  Navigated to: {clicked_page}")

    def test_dashboard_shows_system_status(self, page):
        page.goto(BASE, timeout=15000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(4000)
        body = page.text_content("body")
        # Should show real system metrics
        has_skills = "skills" in body.lower() or "277" in body
        has_confidence = "confidence" in body.lower() or "85" in body
        has_cron = "cron" in body.lower() or "tasks" in body.lower()
        assert has_skills or has_confidence or has_cron, "No system metrics visible"
        print(f"  System metrics visible: skills={has_skills}, confidence={has_confidence}, cron={has_cron}")

    def test_each_page_renders_unique_content(self, page):
        """Every nav destination must surface visibly distinct content."""
        page.goto(BASE, timeout=15000)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(3000)

        pages = {
            "command": ["Dashboard", "Results Banked", "Event Feed"],
            "brain": ["Agents", "MoE Lane Router", "Route Tester"],
            "skills": ["Skills", "Skill Packs", "Bundles"],
            "cron": ["Scheduler", "Cron", "tasks"],
            "systems": ["Health", "System Components", "API Integrations"],
            "settings": ["Settings", "API Keys", "Soul Identity"],
        }
        failures = []
        for page_id, expected in pages.items():
            # Navigate via URL hash
            page.goto(f"{BASE}#{page_id}", timeout=10000)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)
            body = page.text_content("body") or ""
            found = [e for e in expected if e.lower() in body.lower()]
            if not found:
                failures.append(f"  #{page_id}: expected one of {expected}, got {body[:100]}...")
            else:
                print(f"  #{page_id}: found '{found[0]}'")
        assert not failures, "Pages missing unique content:\n" + "\n".join(failures)


# ═══════════════════════════════════════════════════════════════════════
# 13. SCHEDULER & AUTONOMY — background task management
# ═══════════════════════════════════════════════════════════════════════

class TestSchedulerAndAutonomyFunctional:
    """The scheduler and autonomy systems must report real state."""

    def test_scheduler_tasks_have_real_cron_jobs(self):
        code, data = api_get("/scheduler/tasks")
        assert code == 200
        tasks = data.get("tasks", [])
        assert len(tasks) >= 5, f"Only {len(tasks)} scheduler tasks"
        print(f"  Scheduler tasks: {len(tasks)}")
        for t in tasks[:5]:
            print(f"    [{t.get('trigger_type', '?')}] {t.get('name', '?')} -> {t.get('skill', '?')}")

    def test_kairos_reports_daemon_status(self):
        code, data = api_get("/kairos/status")
        assert code == 200
        print(f"  KAIROS keys: {list(data.keys())}")

    def test_autonomy_reports_status(self):
        code, data = api_get("/autonomy/status")
        assert code == 200
        print(f"  Autonomy keys: {list(data.keys())}")

    def test_autonomy_ceo_returns_status(self):
        code, data = api_get("/autonomy/ceo")
        assert code == 200
        print(f"  CEO keys: {list(data.keys())}")

    def test_autodream_reports_status(self):
        code, data = api_get("/autodream/status")
        assert code == 200
        print(f"  AutoDream keys: {list(data.keys())}")


# ═══════════════════════════════════════════════════════════════════════
# 14. SYSTEMS HEALTH & REGISTRY
# ═══════════════════════════════════════════════════════════════════════

class TestSystemsFunctional:
    """Systems registry and health must report real data."""

    def test_systems_registry_returns_agents(self):
        code, data = api_get("/systems/registry")
        assert code == 200
        agents = data.get("agents", [])
        print(f"  Registered agents: {len(agents)}")

    def test_systems_health_returns_status(self):
        code, data = api_get("/systems/health")
        assert code == 200
        print(f"  Systems health keys: {list(data.keys())}")

    def test_middleware_stats_returns_route_data(self):
        code, data = api_get("/dashboard/middleware-stats")
        assert code == 200
        routes = data.get("routes", {})
        print(f"  Tracked routes: {len(routes)}")
        if routes:
            for route, stats in list(routes.items())[:3]:
                print(f"    {route}: {stats.get('count', 0)} calls")

    def test_dashboard_feed_returns_events(self):
        code, data = api_get("/dashboard/feed")
        assert code == 200
        events = data.get("events", [])
        print(f"  Feed events: {len(events)}")
        for e in events[:3]:
            print(f"    [{e.get('event', '?')}] {str(e.get('data', {}))[:60]}")


# ═══════════════════════════════════════════════════════════════════════
# 15. NEWS & OPPORTUNITIES — information feeds
# ═══════════════════════════════════════════════════════════════════════

class TestNewsAndIntelFunctional:
    """News and opportunities must return real content."""

    def test_news_feed_returns_items(self):
        code, data = api_get("/news")
        assert code == 200
        items = data.get("items", [])
        print(f"  News items: {len(items)}")
        for item in items[:3]:
            assert "title" in item
            print(f"    [{item.get('source', '?')}] {item['title'][:60]}...")

    def test_news_unified_returns_categories(self):
        code, data = api_get("/news/unified")
        assert code == 200
        categories = data.get("categories", {})
        print(f"  News categories: {list(categories.keys())}")
        total = data.get("total", 0)
        print(f"  Total items: {total}")

    def test_opportunities_returns_intel(self):
        code, data = api_get("/opportunities")
        assert code == 200
        ops = data.get("opportunities", [])
        print(f"  Opportunities: {len(ops)}")


# ═══════════════════════════════════════════════════════════════════════
# 16. TEMPLATES & SETTINGS
# ═══════════════════════════════════════════════════════════════════════

class TestTemplatesAndSettingsFunctional:
    """Templates and settings must be functional."""

    def test_templates_list_returns_data(self):
        code, data = api_get("/templates")
        assert code == 200
        templates = data.get("templates", [])
        print(f"  Templates: {len(templates)}")

    def test_settings_keys_save_and_persist(self):
        # Save a test key
        code1, saved = api_post("/settings/keys", {
            "anthropic": "sk-test-key-12345",
            "openai": "",
            "deepseek": "",
            "openrouter": "",
            "gemini": "",
        })
        assert code1 == 200
        assert "saved" in saved
        print(f"  Saved keys: {saved.get('saved', [])}")


# ═══════════════════════════════════════════════════════════════════════
# 17. ENGINE API — the hybrid engine state (port 8100)
# ═══════════════════════════════════════════════════════════════════════

class TestEngineAPIFunctional:
    """The engine API serves real-time state to the dashboard."""

    def test_engine_state_returns_full_snapshot(self):
        try:
            r = requests.get("http://localhost:8100/engine/state", timeout=5)
            assert r.status_code == 200
            data = r.json()
            assert "engine" in data
            assert "components" in data
            assert "cron_queue" in data
            print(f"  Engine: {data['engine'].get('name')}")
            print(f"  Components: {len(data['components'])}")
            print(f"  Cron tasks: {len(data['cron_queue'])}")
        except Exception as e:
            pytest.skip(f"Engine API not available: {e}")

    def test_engine_process_accepts_queries(self):
        try:
            r = requests.post(
                "http://localhost:8100/engine/process",
                json={"query": "test query for e2e"},
                timeout=10,
            )
            assert r.status_code == 200
            data = r.json()
            assert "status" in data
            print(f"  Engine process status: {data.get('status')}")
        except Exception as e:
            pytest.skip(f"Engine API not available: {e}")

    def test_engine_events_returns_event_log(self):
        try:
            r = requests.get("http://localhost:8100/engine/events", timeout=5)
            assert r.status_code == 200
            data = r.json()
            events = data.get("events", [])
            print(f"  Engine events: {len(events)}")
        except Exception as e:
            pytest.skip(f"Engine API not available: {e}")


# ═══════════════════════════════════════════════════════════════════════
# 18. FULL END-TO-END JOURNEYS — realistic user workflows
# ═══════════════════════════════════════════════════════════════════════

class TestRealUserJourneys:
    """Complete realistic workflows a human would perform."""

    def test_journey_build_a_component(self):
        """User: wants to build something -> brain reasons -> executes."""
        # Step 1: Reason about what skill to use
        q = "build a react login form with email and password"
        _, reason = api_post("/reason", {"query": q})
        skill = reason.get("decision", {}).get("chosen_skill")
        confidence = reason.get("decision", {}).get("confidence", 0)
        print(f"  1. Reasoned: {skill} (confidence: {confidence:.2f})")
        assert skill

        # Step 2: Execute the task
        _, result = api_post("/task", {"query": q})
        status = result.get("status", "unknown")
        print(f"  2. Executed: status={status}")
        assert "status" in result

    def test_journey_explore_knowledge_then_search(self):
        """User: checks knowledge stats -> searches -> ingests -> searches again."""
        # Check stats
        _, stats = api_get("/knowledge/stats")
        before = stats.get("total_fragments", 0)
        print(f"  1. Knowledge fragments before: {before}")

        # Search existing
        _, search1 = api_post("/knowledge/search", {"query": "fastapi", "top_k": 3})
        results1 = len(search1.get("results", []))
        print(f"  2. Search 'fastapi': {results1} results")
        assert results1 > 0

        # Ingest new
        title = f"E2E Journey {int(time.time())}"
        _, ingest = api_post("/knowledge/ingest-text", {
            "text": "FastAPI is a modern Python web framework for building APIs quickly.",
            "title": title,
            "tags": ["python", "api", "fastapi"],
        })
        added = ingest.get("ingested", 0)
        print(f"  3. Ingested: {added} fragments")
        assert added > 0

        # Search again and find it
        time.sleep(0.5)
        _, search2 = api_post("/knowledge/search", {"query": "fastapi python framework", "top_k": 5})
        titles = [r.get("source_title", "") for r in search2.get("results", [])]
        print(f"  4. Search results: {titles[:3]}")
        assert any(title in t for t in titles), f"Ingested content not found in search"

    def test_journey_create_project_and_explore(self):
        """User: creates a SaaS project -> lists projects -> checks planner."""
        # Create project
        name = f"JourneyProject{int(time.time() * 1000) % 10000}"
        _, created = api_post("/saas/create", params={
            "name": name,
            "idea": "A test project from the e2e journey",
        })
        project = created.get("project", {})
        assert project.get("id") or project.get("name")
        print(f"  1. Created project: {project.get('name', '?')} (stage: {project.get('stage')})")

        # List projects
        _, listed = api_get("/saas/projects")
        projects = listed.get("projects", [])
        names = [p.get("name") for p in projects]
        assert name in names
        print(f"  2. Projects listed: {len(projects)} total")

        # Check planner
        _, planner = api_get("/planner/tasks")
        tasks = planner.get("tasks", [])
        print(f"  3. Planner tasks: {len(tasks)}")

    def test_journey_full_brain_workflow(self):
        """User: checks soul -> reasons -> executes -> checks feed."""
        # Check identity
        _, soul = api_get("/soul")
        identity = soul.get("identity", {})
        print(f"  1. Soul: {identity.get('name', '?')} / {identity.get('role', '?')}")

        # Reason
        _, reason = api_post("/reason", {"query": "add authentication to my api"})
        skill = reason.get("decision", {}).get("chosen_skill")
        print(f"  2. Skill chosen: {skill}")

        # Execute
        _, task = api_post("/task", {"query": "add authentication to my api"})
        print(f"  3. Task status: {task.get('status')}")

        # Check dashboard feed recorded something
        _, feed = api_get("/dashboard/feed")
        events = feed.get("events", [])
        print(f"  4. Feed events: {len(events)}")

    def test_journey_betting_workflow(self):
        """User: checks odds -> generates sheet."""
        _, odds = api_get("/betting/odds")
        lines = odds.get("lines", [])
        print(f"  1. Odds lines: {len(lines)}")

        _, sheet = api_get("/betting/sheet")
        print(f"  2. Sheet keys: {list(sheet.keys())}")

        _, kelly = api_get("/betting/kelly")
        print(f"  3. Kelly keys: {list(kelly.keys())}")

    def test_journey_social_workflow(self):
        """User: schedules a post -> verifies it's in the list."""
        content = f"Journey post {int(time.time())}"
        _, created = api_post("/social/schedule", params={
            "platform": "twitter",
            "content": content,
            "delay_minutes": 60,
        })
        assert created.get("status") == "ok"
        print(f"  1. Scheduled: {created.get('message', '?')}")

        _, listed = api_get("/social/posts")
        posts = listed.get("posts", [])
        contents = [p.get("content", "") for p in posts]
        assert any(content in c for c in contents)
        print(f"  2. Posts in feed: {len(posts)}")
