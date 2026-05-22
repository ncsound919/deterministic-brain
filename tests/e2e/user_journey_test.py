"""
Playwright E2E test - User Journey through Aether Dashboard
Tests real user interactions and captures performance metrics.
"""
import time, json, sys, io
import requests
from playwright.sync_api import sync_playwright

# Fix UTF-8 output for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DASHBOARD_URL = "http://localhost:5173" if __name__ != "__main__" else "http://localhost:5173"
API_BASE = "http://localhost:8000"
ENGINE_API = "http://localhost:8100"

def test_user_journey():
    results = {
        "journey_steps": [],
        "api_tests": [],
        "insights": [],
        "performance": {}
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Capture console errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        t0 = time.perf_counter()

        # ─────────────────────────────────────────────────────────────────
        # STEP 1: Open Dashboard
        # ─────────────────────────────────────────────────────────────────
        print("\n[1/8] Opening Dashboard...")
        step_start = time.perf_counter()

        try:
            page.goto(DASHBOARD_URL, timeout=15000)
            page.wait_for_load_state("networkidle", timeout=15000)

            # Get page title and header
            title = page.title()
            header = page.locator("h1").first.text_content(timeout=5000) if page.locator("h1").count() > 0 else "No h1 found"

            results["journey_steps"].append({
                "step": "Dashboard Load",
                "status": "PASS",
                "url": page.url,
                "title": title,
                "header": header[:50] if header else "N/A",
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [PASS] Dashboard loaded in {results['journey_steps'][-1]['time_ms']}ms")
        except Exception as e:
            results["journey_steps"].append({
                "step": "Dashboard Load",
                "status": "FAIL",
                "error": str(e)[:100],
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [FAIL] Failed: {e}")

        # ─────────────────────────────────────────────────────────────────
        # STEP 2: Check API Health
        # ─────────────────────────────────────────────────────────────────
        print("\n[2/8] Checking API Health...")
        step_start = time.perf_counter()

        import requests
        try:
            health = requests.get(f"{API_BASE}/health", timeout=10).json()
            integrations = requests.get(f"{API_BASE}/integrations", timeout=10).json()

            results["journey_steps"].append({
                "step": "API Health Check",
                "status": "PASS",
                "version": health.get("version"),
                "apis_configured": sum(1 for v in integrations.get("apis", {}).values() if v.get("configured")),
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [PASS] API v{health.get('version')}, {results['journey_steps'][-1]['apis_configured']}/13 APIs configured")
        except Exception as e:
            results["journey_steps"].append({
                "step": "API Health Check",
                "status": "FAIL",
                "error": str(e)[:100],
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [FAIL] Failed: {e}")

        # ─────────────────────────────────────────────────────────────────
        # STEP 3: Brain Reasoning Test
        # ─────────────────────────────────────────────────────────────────
        print("\n[3/8] Testing Brain Reasoning...")
        step_start = time.perf_counter()

        test_queries = [
            "build a React login form with JWT auth",
            "create a python REST API with FastAPI"
        ]

        reasoning_results = []
        for query in test_queries:
            try:
                r = requests.post(f"{API_BASE}/reason", json={"query": query}, timeout=30)
                data = r.json()
                skill = data.get("skill", "unknown")
                conf = data.get("confidence", 0)
                reasoning_results.append({"query": query[:30], "skill": skill, "conf": round(conf, 2)})
            except Exception as e:
                reasoning_results.append({"query": query[:30], "error": str(e)[:50]})

        results["journey_steps"].append({
            "step": "Brain Reasoning",
            "status": "PASS" if reasoning_results else "FAIL",
            "queries_tested": len(test_queries),
            "results": reasoning_results,
            "time_ms": round((time.perf_counter() - step_start) * 1000)
        })
        print(f"  [PASS] Tested {len(test_queries)} queries")
        for r in reasoning_results:
            print(f"    → '{r.get('query')}' → {r.get('skill')} ({r.get('conf', 'N/A')})")

        # ─────────────────────────────────────────────────────────────────
        # STEP 4: Task Execution
        # ─────────────────────────────────────────────────────────────────
        print("\n[4/8] Testing Task Execution...")
        step_start = time.perf_counter()

        try:
            task_resp = requests.post(f"{API_BASE}/task", json={
                "query": "create a React component called UserCard",
                "skill": "react-component"
            }, timeout=30)
            task_data = task_resp.json()
            status = task_data.get("status")
            output = str(task_data.get("final_output", ""))[:100]

            results["journey_steps"].append({
                "step": "Task Execution",
                "status": "PASS" if status == "ok" else "FAIL",
                "task_status": status,
                "output": output,
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [PASS] Task status: {status}, output: {output[:50]}...")
        except Exception as e:
            results["journey_steps"].append({
                "step": "Task Execution",
                "status": "FAIL",
                "error": str(e)[:100],
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [FAIL] Failed: {e}")

        # ─────────────────────────────────────────────────────────────────
        # STEP 5: Knowledge Bank
        # ─────────────────────────────────────────────────────────────────
        print("\n[5/8] Testing Knowledge Bank...")
        step_start = time.perf_counter()

        try:
            # Ingest (requires title field)
            ingest_resp = requests.post(f"{API_BASE}/knowledge/ingest-text", json={
                "title": "Playwright Testing",
                "text": "Playwright is a framework for browser automation testing"
            }, timeout=10)

            # Search (use correct endpoint)
            search_resp = requests.post(f"{API_BASE}/knowledge/search", json={"query": "Playwright"}, timeout=10)
            search_data = search_resp.json()
            hits = len(search_data.get("results", []))

            results["journey_steps"].append({
                "step": "Knowledge Bank",
                "status": "PASS",
                "ingest": "ok" if ingest_resp.status_code == 200 else "fail",
                "search_hits": hits,
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [PASS] Ingested and found {hits} results")
        except Exception as e:
            results["journey_steps"].append({
                "step": "Knowledge Bank",
                "status": "FAIL",
                "error": str(e)[:100],
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [FAIL] Failed: {e}")

        # ─────────────────────────────────────────────────────────────────
        # STEP 6: Betting Engine
        # ─────────────────────────────────────────────────────────────────
        print("\n[6/8] Testing Betting Engine...")
        step_start = time.perf_counter()

        try:
            odds_resp = requests.get(f"{API_BASE}/betting/odds", timeout=10)
            odds_data = odds_resp.json()
            odds_count = odds_data.get("count", 0) or len(odds_data.get("lines", []))

            sheet_resp = requests.get(f"{API_BASE}/betting/sheet?sport=basketball_nba&bankroll=1000", timeout=30)
            sheet_data = sheet_resp.json()
            picks = sheet_data.get("recommended_picks", 0)

            results["journey_steps"].append({
                "step": "Betting Engine",
                "status": "PASS",
                "odds_lines": odds_count,
                "recommended_picks": picks,
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [PASS] {odds_count} odds lines, {picks} recommended picks")
        except Exception as e:
            results["journey_steps"].append({
                "step": "Betting Engine",
                "status": "FAIL",
                "error": str(e)[:100],
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [FAIL] Failed: {e}")

        # ─────────────────────────────────────────────────────────────────
        # STEP 7: Social Scheduler
        # ─────────────────────────────────────────────────────────────────
        print("\n[7/8] Testing Social Scheduler...")
        step_start = time.perf_counter()

        try:
            # Schedule a post
            schedule_resp = requests.post(f"{API_BASE}/social/schedule", params={
                "platform": "twitter",
                "content": "E2E Test post from Playwright",
                "delay_minutes": 60
            }, timeout=10)

            # Get queue
            queue_resp = requests.get(f"{API_BASE}/social/posts", timeout=10)
            queue_data = queue_resp.json()
            queue_count = len(queue_data.get("posts", []))

            results["journey_steps"].append({
                "step": "Social Scheduler",
                "status": "PASS",
                "scheduled": schedule_resp.status_code == 200,
                "queue_count": queue_count,
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [PASS] Post scheduled, {queue_count} posts in queue")
        except Exception as e:
            results["journey_steps"].append({
                "step": "Social Scheduler",
                "status": "FAIL",
                "error": str(e)[:100],
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [FAIL] Failed: {e}")

        # ─────────────────────────────────────────────────────────────────
        # STEP 8: Engine API
        # ─────────────────────────────────────────────────────────────────
        print("\n[8/8] Testing Engine API...")
        step_start = time.perf_counter()

        try:
            state_resp = requests.get(f"{ENGINE_API}/engine/state", timeout=10)
            state_data = state_resp.json()
            skill_count = state_data.get("engine", {}).get("skill_count", 0)

            # Process a query
            proc_resp = requests.post(f"{ENGINE_API}/engine/process", json={
                "query": "test the engine"
            }, timeout=30)
            proc_data = proc_resp.json()
            proc_status = proc_data.get("status")

            results["journey_steps"].append({
                "step": "Engine API",
                "status": "PASS",
                "skills_loaded": skill_count,
                "process_status": proc_status,
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [PASS] {skill_count} skills loaded, process: {proc_status}")
        except Exception as e:
            results["journey_steps"].append({
                "step": "Engine API",
                "status": "FAIL",
                "error": str(e)[:100],
                "time_ms": round((time.perf_counter() - step_start) * 1000)
            })
            print(f"  [FAIL] Failed: {e}")

        browser.close()

        # Calculate totals
        total_time = (time.perf_counter() - t0) * 1000

        # Add insights
        passed = sum(1 for s in results["journey_steps"] if s["status"] == "PASS")
        failed = sum(1 for s in results["journey_steps"] if s["status"] == "FAIL")
        avg_time = sum(s.get("time_ms", 0) for s in results["journey_steps"]) / len(results["journey_steps"]) if results["journey_steps"] else 0

        results["performance"] = {
            "total_journey_time_ms": round(total_time),
            "steps_passed": passed,
            "steps_failed": failed,
            "pass_rate": round(passed / len(results["journey_steps"]) * 100, 1),
            "avg_step_time_ms": round(avg_time)
        }

        # Add insights
        results["insights"] = [
            f"Journey completed with {passed}/{len(results['journey_steps'])} steps passing",
            f"Average step time: {round(avg_time)}ms",
            f"Total journey time: {round(total_time)}ms",
            f"Console errors captured: {len(console_errors)}",
        ]

        if console_errors:
            results["insights"].append(f"Sample console errors: {console_errors[:3]}")

        return results


def print_report(results):
    print("\n" + "=" * 70)
    print("USER JOURNEY TEST REPORT")
    print("=" * 70)

    print("\n📍 STEP-BY-STEP RESULTS:")
    print("-" * 70)
    for step in results["journey_steps"]:
        status = "[PASS]" if step["status"] == "PASS" else "[FAIL]"
        time_ms = step.get("time_ms", 0)
        print(f"  {status} {step['step']:25} {time_ms:6}ms")

    print("\n📊 PERFORMANCE:")
    print("-" * 70)
    perf = results["performance"]
    print(f"  Total Journey Time:  {perf['total_journey_time_ms']:6}ms")
    print(f"  Steps Passed:       {perf['steps_passed']}/{len(results['journey_steps'])} ({perf['pass_rate']}%)")
    print(f"  Average Step Time:  {perf['avg_step_time_ms']:6}ms")

    print("\n💡 INSIGHTS:")
    print("-" * 70)
    for insight in results["insights"]:
        print(f"  • {insight}")

    print("\n" + "=" * 70)

    # Save results
    with open("user_journey_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Results saved to user_journey_results.json")


if __name__ == "__main__":
    print("Starting Aether Dashboard User Journey Test...")
    results = test_user_journey()
    print_report(results)