"""Playwright Benchmark Suite — measures all pages, APIs, and reasoning performance.

Generates a benchmark.json report for tracking system progress over time.
Uses the healing system to adjust skills based on benchmark findings.
"""

import json
import time
import statistics
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pytest
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
BENCHMARK_FILE = Path(".benchmark_report.json")


class BenchmarkReport:
    """Collects and saves benchmark metrics."""

    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "version": "2.5.0",
            "skills_loaded": 0,
            "pages": {},
            "apis": {},
            "reasoning": {},
            "summary": {},
        }

    def record_page(self, name: str, load_ms: float, status: str):
        self.metrics["pages"][name] = {
            "load_ms": round(load_ms, 1),
            "status": status,
        }

    def record_api(self, endpoint: str, ms: float, status_code: int, payload_size: int = 0):
        self.metrics["apis"][endpoint] = {
            "ms": round(ms, 1),
            "status": status_code,
            "size_bytes": payload_size,
        }

    def record_reasoning(self, query: str, chosen_skill: str, confidence: float, ms: float):
        self.metrics["reasoning"][query[:50]] = {
            "chosen_skill": chosen_skill,
            "confidence": round(confidence, 4),
            "ms": round(ms, 1),
        }

    def finalize(self, skills_count: int):
        elapsed = time.time() - self.start_time
        pages = self.metrics["pages"]
        apis = self.metrics["apis"]

        page_times = [v["load_ms"] for v in pages.values() if v["load_ms"] > 0]
        api_times = [v["ms"] for v in apis.values() if v["ms"] > 0]

        self.metrics["summary"] = {
            "total_benchmark_ms": round(elapsed * 1000, 1),
            "skills_loaded": skills_count,
            "pages_tested": len(pages),
            "pages_ok": sum(1 for v in pages.values() if v["status"] == "ok"),
            "pages_failed": sum(1 for v in pages.values() if v["status"] != "ok"),
            "apis_tested": len(apis),
            "avg_page_load_ms": round(statistics.mean(page_times), 1) if page_times else 0,
            "avg_api_ms": round(statistics.mean(api_times), 1) if api_times else 0,
            "p50_api_ms": round(statistics.median(api_times), 1) if api_times else 0,
            "p95_api_ms": round(sorted(api_times)[int(len(api_times) * 0.95)], 1) if api_times else 0,
            "reasoning_queries": len(self.metrics["reasoning"]),
            "avg_confidence": round(
                statistics.mean([v["confidence"] for v in self.metrics["reasoning"].values()]),
                4,
            ) if self.metrics["reasoning"] else 0.0,
        }

    def save(self):
        """Write report and print summary."""
        BENCHMARK_FILE.write_text(json.dumps(self.metrics, indent=2))

        s = self.metrics["summary"]
        print(f"\n{'='*60}")
        print(f"  BENCHMARK COMPLETE")
        print(f"  Skills: {s['skills_loaded']}  Pages: {s['pages_ok']}/{s['pages_tested']} ok")
        print(f"  APIs: {s['apis_tested']}  avg_page: {s['avg_page_load_ms']}ms  avg_api: {s['avg_api_ms']}ms")
        print(f"  p50_api: {s['p50_api_ms']}ms  p95_api: {s['p95_api_ms']}ms")
        print(f"  Reasoning queries: {s['reasoning_queries']}  avg_confidence: {s['avg_confidence']}")
        print(f"  Report: {BENCHMARK_FILE.resolve()}")
        print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════════
# Fixture — shared browser + benchmark collector
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def report():
    return BenchmarkReport()


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


def _timed_get(endpoint: str, report: BenchmarkReport, label: str = None):
    """Time an API call and record metrics."""
    name = label or endpoint
    t0 = time.time()
    try:
        r = requests.get(f"{BASE}{endpoint}", timeout=15)
        ms = (time.time() - t0) * 1000
        size = len(r.content)
        report.record_api(name, ms, r.status_code, size)
        return r
    except Exception as e:
        ms = (time.time() - t0) * 1000
        report.record_api(name, ms, 0)
        raise


def _timed_post(endpoint: str, json_data: dict, report: BenchmarkReport, label: str = None):
    """Time a POST API call and record metrics."""
    name = label or endpoint
    t0 = time.time()
    try:
        r = requests.post(f"{BASE}{endpoint}", json=json_data, timeout=30)
        ms = (time.time() - t0) * 1000
        size = len(r.content)
        report.record_api(name, ms, r.status_code, size)
        return r
    except Exception as e:
        ms = (time.time() - t0) * 1000
        report.record_api(name, ms, 0)
        raise


# ═══════════════════════════════════════════════════════════════════
# API Benchmarks
# ═══════════════════════════════════════════════════════════════════

class TestAPIBenchmark:
    """Measure every API endpoint."""

    def test_skills_endpoint(self, report):
        r = _timed_get("/skills", report)
        assert r.status_code == 200
        data = r.json()
        report.metrics["skills_loaded"] = len(data.get("skills", []))
        assert len(data.get("skills", [])) >= 50, f"Only {len(data.get('skills', []))} skills"

    def test_health_endpoint(self, report):
        r = _timed_get("/health", report)
        assert r.status_code == 200

    def test_bundles_endpoint(self, report):
        r = _timed_get("/bundles", report)
        assert r.status_code == 200

    def test_settings_endpoint(self, report):
        r = _timed_get("/settings", report)
        assert r.status_code == 200

    def test_settings_schema_endpoint(self, report):
        r = _timed_get("/settings/schema", report)
        assert r.status_code == 200

    def test_devpets_endpoint(self, report):
        r = _timed_get("/devpets", report)
        assert r.status_code == 200

    def test_dashboard_feed(self, report):
        r = _timed_get("/dashboard/feed", report)
        assert r.status_code == 200

    def test_dashboard_stats(self, report):
        r = _timed_get("/dashboard/stats", report)
        assert r.status_code == 200

    def test_dashboard_audit(self, report):
        r = _timed_get("/dashboard/audit", report)
        assert r.status_code == 200

    def test_dashboard_middleware(self, report):
        r = _timed_get("/dashboard/middleware-stats", report)
        assert r.status_code == 200

    def test_relay_agents(self, report):
        r = _timed_get("/relay/agents", report)
        assert r.status_code == 200

    def test_health_monitor(self, report):
        r = _timed_get("/health/monitor", report)
        assert r.status_code == 200

    def test_health_skills(self, report):
        r = _timed_get("/health/skills", report)
        assert r.status_code == 200

    def test_health_heals(self, report):
        r = _timed_get("/health/heals", report)
        assert r.status_code == 200

    def test_autodream_status(self, report):
        r = _timed_get("/autodream/status", report)
        assert r.status_code == 200

    def test_evolution_report(self, report):
        r = _timed_get("/evolution/report", report)
        assert r.status_code in (200, 501)  # 501 = module not available

    def test_kairos_status(self, report):
        r = _timed_get("/kairos/status", report)
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Reasoning Benchmarks — test with diverse queries
# ═══════════════════════════════════════════════════════════════════

class TestReasoningBenchmark:
    """Test reasoning across diverse query domains using all 89 skills."""

    QUERIES = [
        ("create a react component for a user profile", "react"),
        ("build a REST API for orders", "rest"),
        ("analyze this code for security issues", "security"),
        ("generate a dockerfile", "docker"),
        ("fix a bug in the authentication module", "auth"),
        ("how do I deploy to vercel?", "deploy"),
        ("create a jupyter notebook", "notebook"),
        ("design a canvas visualization", "canvas"),
        ("write a pdf report", "pdf"),
        ("scaffold a CLI tool", "cli"),
        ("build a notion integration", "notion"),
        ("create a figma design system", "figma"),
    ]

    def test_reasoner_diverse_queries(self, report):
        """Run the reasoner against all 12 query domains."""
        for query, domain in self.QUERIES:
            t0 = time.time()
            try:
                r = requests.post(f"{BASE}/reason", json={"query": query}, timeout=20)
                ms = (time.time() - t0) * 1000
                d = r.json().get("decision", {})
                report.record_reasoning(
                    query,
                    d.get("chosen_skill", "?"),
                    d.get("confidence", 0.0),
                    ms,
                )
                report.record_api(f"/reason ({domain})", ms, r.status_code, len(r.content))
            except Exception as e:
                ms = (time.time() - t0) * 1000
                report.record_api(f"/reason ({domain})", ms, 0)

    def test_task_executes(self, report):
        """Run an actual task to verify skill execution pipeline."""
        t0 = time.time()
        r = requests.post(f"{BASE}/task", json={
            "query": "create a react component named UserCard"
        }, timeout=30)
        ms = (time.time() - t0) * 1000
        report.record_api("POST /task", ms, r.status_code, len(r.content))

    def test_bundle_executes(self, report):
        """Run a bundle dispatch."""
        t0 = time.time()
        r = requests.post(f"{BASE}/bundle", json={
            "bundle": "scaffold-rest-api",
            "inputs": {"resource": "Products"},
        }, timeout=30)
        ms = (time.time() - t0) * 1000
        report.record_api("POST /bundle", ms, r.status_code, len(r.content))

    def test_dialogue_pipeline(self, report):
        """Test dialogue pipeline with voice intent routing."""
        t0 = time.time()
        r = requests.post(f"{BASE}/dialogue/process", json={
            "text": "Help me write a test for my REST API",
        }, timeout=15)
        ms = (time.time() - t0) * 1000
        report.record_api("POST /dialogue/process", ms, r.status_code, len(r.content))


# ═══════════════════════════════════════════════════════════════════
# UI Page Benchmarks — measure load times with Playwright
# ═══════════════════════════════════════════════════════════════════

class TestPageBenchmark:
    """Measure load time for every UI page."""

    PAGES = [
        ("dashboard", ".card-grid"),
        ("task", "input"),
        ("reason", "input"),
        ("bundles", "button"),
        ("devpets", "canvas"),
        ("battle", "select, button"),
        ("skills", "table"),
        ("kairos", ".card"),
        ("autodream", "button"),
        ("feed", "input"),
        ("audit", "table"),
        ("settings", "input"),
        ("health-mon", ".card"),
    ]

    def _nav_to(self, page, page_name):
        page.click(f".nav-item[data-page='{page_name}']")
        page.wait_for_function(
            f"document.querySelector('#page-{page_name}')?.classList.contains('active')",
            timeout=8000,
        )

    def test_all_pages_load(self, page, report):
        """Navigate to every page and measure load time."""
        page.goto(BASE)
        page.wait_for_selector(".card-grid", timeout=8000)

        for name, selector in self.PAGES:
            t0 = time.time()
            try:
                self._nav_to(page, name)
                # Wait for content
                page.wait_for_selector(selector, timeout=8000)
                ms = (time.time() - t0) * 1000
                report.record_page(name, ms, "ok")
            except Exception as e:
                ms = (time.time() - t0) * 1000
                report.record_page(name, ms, "failed")
                print(f"  Page {name}: {str(e)[:60]}")


# ═══════════════════════════════════════════════════════════════════
# DevPet Generation Benchmark
# ═══════════════════════════════════════════════════════════════════

class TestDevPetBenchmark:
    def test_generate_devpet(self, report):
        """Generate a DevPet from traces and measure time."""
        t0 = time.time()
        r = requests.post(f"{BASE}/devpets/generate", json={
            "pet_name": f"BenchmarkBot",
            "db_path": "traces.db",
        }, timeout=30)
        ms = (time.time() - t0) * 1000
        report.record_api("POST /devpets/generate", ms, r.status_code, len(r.content))
        if r.status_code == 200:
            data = r.json()
            assert "pet_name" in data
            print(f"  Generated pet: {data['pet_name']} (Lv.{data['level']})")
        else:
            print(f"  DevPet generate returned {r.status_code} (expected if no traces)")


# ═══════════════════════════════════════════════════════════════════
# Finalize + Heal
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module", autouse=True)
def finalize_report(report):
    """After all tests, save benchmark and apply healing."""
    yield
    report.finalize(report.metrics["skills_loaded"])
    report.save()

    # Apply healing based on findings
    try:
        from evolution.skill_evolver import SkillEvolver
        evolver = SkillEvolver()
        for query, data in report.metrics.get("reasoning", {}).items():
            if data["confidence"] < 0.2:
                evolver.track(data["chosen_skill"], False, data["ms"])
                print(f"  Heal: low confidence ({data['confidence']}) for {data['chosen_skill']}")
        evolved = evolver.evolve()
        if evolved:
            print(f"  Evolved {len(evolved)} skills based on benchmark")
    except ImportError:
        pass
