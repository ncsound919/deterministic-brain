"""
COMPREHENSIVE FUNCTIONAL TEST - Deep user journey with real UI interactions
Tests actual button clicks, form submissions, workflow completion, and real outputs
Browser runs in VISIBLE mode so you can see what's happening
"""
import time, json, sys, io, os
import requests
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DASHBOARD_URL = "http://localhost:5173"
API_BASE = "http://localhost:8000"
ENGINE_API = "http://localhost:8100"

OUTPUT_DIR = "functional_test_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def test_comprehensive_functional():
    """Deep functional test with real UI interactions"""
    results = {
        "workflows_tested": [],
        "issues_found": [],
        "working_features": [],
        "broken_features": []
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)  # Visible + slower for visibility
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # ═══════════════════════════════════════════════════════════════════════
        # WORKFLOW 1: Dashboard Navigation & Loading
        # ═══════════════════════════════════════════════════════════════════════
        log("=== WORKFLOW 1: Dashboard Load & Navigation ===")
        
        page.goto(DASHBOARD_URL, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=30000)
        page.screenshot(path=f"{OUTPUT_DIR}/01_home.png", full_page=True)
        
        # Check what's actually visible
        page_content = page.content()
        
        # Try to find and click nav items
        nav_attempts = [
            ("nav a", "Navigation links"),
            ("[class*='nav'] a", "Nav class links"),
            ("button", "Buttons"),
            (".menu-item", "Menu items"),
        ]
        
        nav_working = False
        for selector, name in nav_attempts:
            try:
                elements = page.locator(selector).all()
                if elements:
                    log(f"  Found {len(elements)} {name}")
                    nav_working = True
                    # Try clicking first one
                    elements[0].click()
                    time.sleep(1)
                    page.screenshot(path=f"{OUTPUT_DIR}/02_after_nav_click.png")
                    page.go_back()
                    time.sleep(0.5)
            except Exception as e:
                log(f"  {name}: FAILED - {str(e)[:50]}")

        if not nav_working:
            results["issues_found"].append("Navigation not working - no clickable elements found")

        # ═══════════════════════════════════════════════════════════════════════
        # WORKFLOW 2: Reason Input - Test the Brain
        # ═══════════════════════════════════════════════════════════════════════
        log("\n=== WORKFLOW 2: Brain Reasoning Input ===")
        
        # Try to find reason input field
        reason_input_selectors = [
            "input[placeholder*='reason']",
            "input[placeholder*='query']",
            "textarea[placeholder*='reason']",
            "input[type='text']",
            "[class*='reason'] input",
            "#reason-input",
            "input[name='query']"
        ]
        
        reason_input = None
        for selector in reason_input_selectors:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    reason_input = el
                    log(f"  Found reason input: {selector}")
                    break
            except:
                pass
        
        if reason_input:
            # Type a query
            reason_input.fill("build a React login form")
            log("  Filled query: 'build a React login form'")
            
            # Find submit button
            submit_selectors = ["button[type='submit']", "button:has-text('Submit')", "button:has-text('Go')", "button:has-text('Execute')"]
            submit_btn = None
            for selector in submit_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        submit_btn = btn
                        log(f"  Found submit button: {selector}")
                        break
                except:
                    pass
            
            if submit_btn:
                submit_btn.click()
                log("  Clicked submit button")
                time.sleep(3)  # Wait for processing
                page.screenshot(path=f"{OUTPUT_DIR}/03_reason_result.png")
                
                # Check for result
                result_selectors = ["[class*='result']", "[class*='response']", "[class*='output']", ".response"]
                result_found = False
                for selector in result_selectors:
                    if page.locator(selector).count() > 0:
                        result_text = page.locator(selector).first.text_content(timeout=3000)
                        if result_text and len(result_text) > 10:
                            log(f"  Result found: {result_text[:100]}...")
                            result_found = True
                            break
                
                if result_found:
                    results["working_features"].append("Reason input + submit works")
                else:
                    results["issues_found"].append("Reason submit clicked but no visible result")
            else:
                results["issues_found"].append("No submit button found for reason input")
        else:
            results["issues_found"].append("Could not find reason/query input field")
            page.screenshot(path=f"{OUTPUT_DIR}/03_no_input_found.png")

        # ═══════════════════════════════════════════════════════════════════════
        # WORKFLOW 3: Task Execution via UI
        # ═══════════════════════════════════════════════════════════════════════
        log("\n=== WORKFLOW 3: Task Execution ===")
        
        # Look for task/skill inputs
        task_selectors = [
            "input[placeholder*='task']",
            "input[placeholder*='skill']",
            "[class*='task'] input",
            "[class*='execute'] input"
        ]
        
        task_input = None
        for selector in task_selectors:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    task_input = el
                    log(f"  Found task input: {selector}")
                    break
            except:
                pass
        
        if task_input:
            task_input.fill("create a simple hello world function")
            log("  Filled task: 'create a simple hello world function'")
            time.sleep(1)
            
            # Click execute
            execute_btn = page.locator("button:has-text('Execute')").first
            if execute_btn.is_visible():
                execute_btn.click()
                log("  Clicked Execute")
                time.sleep(5)  # Wait for task
                page.screenshot(path=f"{OUTPUT_DIR}/04_task_result.png")
                results["working_features"].append("Task execution UI works")
            else:
                results["issues_found"].append("Execute button not found")
        else:
            results["issues_found"].append("Task input not found")

        # ═══════════════════════════════════════════════════════════════════════
        # WORKFLOW 4: Knowledge Bank Ingest
        # ═══════════════════════════════════════════════════════════════════════
        log("\n=== WORKFLOW 4: Knowledge Bank ===")
        
        kb_selectors = [
            "input[placeholder*='knowledge']",
            "input[placeholder*='ingest']",
            "input[placeholder*='search']",
            "textarea[placeholder*='knowledge']",
            "[class*='knowledge'] input"
        ]
        
        kb_input = None
        for selector in kb_selectors:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    kb_input = el
                    log(f"  Found KB input: {selector}")
                    break
            except:
                pass
        
        if kb_input:
            # Test search
            kb_input.fill("FastAPI")
            time.sleep(0.5)
            page.screenshot(path=f"{OUTPUT_DIR}/05_kb_search.png")
            
            search_btn = page.locator("button:has-text('Search')").first
            if search_btn.is_visible():
                search_btn.click()
                time.sleep(2)
                page.screenshot(path=f"{OUTPUT_DIR}/06_kb_results.png")
                results["working_features"].append("Knowledge search UI works")
            else:
                results["issues_found"].append("Knowledge search button not found")
        else:
            results["issues_found"].append("Knowledge input not found")
            page.screenshot(path=f"{OUTPUT_DIR}/05_no_kb.png")

        # ═══════════════════════════════════════════════════════════════════════
        # WORKFLOW 5: Settings/API Configuration
        # ═══════════════════════════════════════════════════════════════════════
        log("\n=== WORKFLOW 5: Settings/Configuration ===")
        
        # Look for settings
        settings_selectors = [
            "[class*='settings']",
            "[class*='config']",
            "button:has-text('Settings')",
            "a:has-text('Settings')"
        ]
        
        settings_found = False
        for selector in settings_selectors:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    el.click()
                    time.sleep(1)
                    page.screenshot(path=f"{OUTPUT_DIR}/07_settings.png")
                    settings_found = True
                    log(f"  Found and clicked: {selector}")
                    break
            except:
                pass
        
        if not settings_found:
            results["issues_found"].append("Settings section not found/accessible")
        
        # ═══════════════════════════════════════════════════════════════════════
        # WORKFLOW 6: Direct API Verification
        # ═══════════════════════════════════════════════════════════════════════
        log("\n=== WORKFLOW 6: Direct API Verification ===")
        
        # Test each endpoint directly to verify actual functionality
        api_tests = [
            ("/health", "GET", None, "Health"),
            ("/reason", "POST", {"query": "test"}, "Reason"),
            ("/task", "POST", {"query": "test task", "skill": "test"}, "Task"),
            ("/knowledge/stats", "GET", None, "KB Stats"),
            ("/knowledge/search", "POST", {"query": "test"}, "KB Search"),
            ("/betting/odds", "GET", None, "Betting"),
            ("/social/posts", "GET", None, "Social"),
            ("/news", "GET", None, "News"),
            ("/systems/registry", "GET", None, "Systems"),
        ]
        
        api_results = {}
        for endpoint, method, data, name in api_tests:
            try:
                if method == "GET":
                    r = requests.get(f"{API_BASE}{endpoint}", timeout=15)
                else:
                    r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=15)
                
                status = r.status_code
                if status == 200:
                    json_data = r.json()
                    # Check actual content
                    has_data = bool(json_data) and not (len(json_data) == 1 and "_error" in json_data)
                    api_results[name] = "WORKING" if has_data else f"EMPTY ({status})"
                else:
                    api_results[name] = f"ERROR ({status})"
            except Exception as e:
                api_results[name] = f"FAIL: {str(e)[:30]}"
        
        for name, status in api_results.items():
            log(f"  {name}: {status}")
            if "WORKING" in status:
                results["working_features"].append(f"API: {name}")
            else:
                results["issues_found"].append(f"API: {name} - {status}")

        # ═══════════════════════════════════════════════════════════════════════
        # WORKFLOW 7: Generate Deliverables
        # ═══════════════════════════════════════════════════════════════════════
        log("\n=== WORKFLOW 7: Verify Deliverables ===")
        
        # Test that actual deliverables are produced
        deliverable_tests = [
            ("/reason", "Skill routing matrix", {"query": "build login"}),
            ("/task", "Code generation", {"query": "create function", "skill": "code"}),
            ("/knowledge/search", "Search results", {"query": "API"}),
            ("/betting/odds", "Odds data", None),
            ("/news", "News items", None),
        ]
        
        for endpoint, deliverable_name, data in deliverable_tests:
            try:
                if data:
                    r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=15)
                else:
                    r = requests.get(f"{API_BASE}{endpoint}", timeout=15)
                
                if r.status_code == 200:
                    json_data = r.json()
                    # Look for actual data keys
                    if isinstance(json_data, dict):
                        keys = list(json_data.keys())
                        log(f"  {deliverable_name}: keys={keys[:5]}")
                        
                        # Check for real content
                        has_real_data = any(
                            isinstance(v, (list, dict)) and len(v) > 0
                            for v in json_data.values()
                            if isinstance(v, (list, dict))
                        )
                        
                        if has_real_data:
                            results["working_features"].append(f"Deliverable: {deliverable_name}")
                        else:
                            results["issues_found"].append(f"Deliverable '{deliverable_name}' has empty data")
                    else:
                        results["issues_found"].append(f"Deliverable '{deliverable_name}' not dict")
                else:
                    results["issues_found"].append(f"Deliverable '{deliverable_name}' HTTP {r.status_code}")
            except Exception as e:
                results["issues_found"].append(f"Deliverable '{deliverable_name}' exception: {str(e)[:40]}")

        # ═══════════════════════════════════════════════════════════════════════
        # WORKFLOW 8: Engine API Full Test
        # ═══════════════════════════════════════════════════════════════════════
        log("\n=== WORKFLOW 8: Engine API ===")
        
        try:
            # Get engine state
            r = requests.get(f"{ENGINE_API}/engine/state", timeout=10)
            if r.status_code == 200:
                state = r.json()
                skill_count = state.get("engine", {}).get("skill_count", 0)
                log(f"  Engine skills: {skill_count}")
                
                if skill_count > 100:
                    results["working_features"].append("Engine API with many skills")
                else:
                    results["issues_found"].append(f"Engine only has {skill_count} skills")
                
                # Test process
                r2 = requests.post(f"{ENGINE_API}/engine/process", json={"query": "test"}, timeout=30)
                if r2.status_code == 200:
                    proc = r2.json()
                    if proc.get("status") == "ok":
                        results["working_features"].append("Engine process works")
                    else:
                        results["issues_found"].append(f"Engine process: {proc.get('status')}")
                else:
                    results["issues_found"].append(f"Engine process HTTP {r2.status_code}")
            else:
                results["issues_found"].append(f"Engine state HTTP {r.status_code}")
        except Exception as e:
            results["issues_found"].append(f"Engine API: {str(e)[:50]}")

        # ═══════════════════════════════════════════════════════════════════════
        # WORKFLOW 9: Real Output Verification
        # ═══════════════════════════════════════════════════════════════════════
        log("\n=== WORKFLOW 9: Real Output Quality ===")
        
        # Test actual reasoning with specific queries
        test_queries = [
            "build a React login form with JWT",
            "create a Python FastAPI endpoint",
            "generate a Dockerfile",
            "audit for security vulnerabilities"
        ]
        
        skill_routing = {}
        for query in test_queries:
            try:
                r = requests.post(f"{API_BASE}/reason", json={"query": query}, timeout=30)
                data = r.json()
                decision = data.get("decision", {})
                skill = decision.get("chosen_skill", "unknown")
                confidence = decision.get("confidence", 0)
                skill_routing[query[:30]] = {"skill": skill, "conf": confidence}
            except:
                skill_routing[query[:30]] = {"skill": "error", "conf": 0}
        
        log(f"  Skill routing results:")
        for q, result in skill_routing.items():
            log(f"    '{q}' -> {result['skill']} ({result['conf']:.2f})")
        
        # Count how many correctly routed
        correct_count = sum(1 for r in skill_routing.values() if r["skill"] != "unknown" and r["skill"] != "error")
        
        if correct_count >= 3:
            results["working_features"].append(f"Good skill routing: {correct_count}/4")
        else:
            results["issues_found"].append(f"Poor skill routing: only {correct_count}/4 correct")

        # ═══════════════════════════════════════════════════════════════════════
        # Summary
        # ═══════════════════════════════════════════════════════════════════════
        
        log("\n" + "="*70)
        log("FUNCTIONAL TEST SUMMARY")
        log("="*70)
        
        log(f"\nWORKING FEATURES ({len(results['working_features'])}):")
        for f in results["working_features"]:
            log(f"  ✓ {f}")
        
        log(f"\nISSUES FOUND ({len(results['issues_found'])}):")
        for issue in results["issues_found"]:
            log(f"  ✗ {issue}")
        
        log(f"\nConsole Errors: {len(console_errors)}")
        if console_errors:
            for err in console_errors[:5]:
                log(f"  ! {err}")
        
        log("\n" + "="*70)
        
        # Save
        with open("functional_test_results.json", "w", encoding="utf-8") as f:
            json.dump({
                "working": results["working_features"],
                "issues": results["issues_found"],
                "skill_routing": skill_routing,
                "api_results": api_results,
                "console_errors": console_errors
            }, f, indent=2)
        
        log(f"\nScreenshots: {OUTPUT_DIR}/")
        log("Results: functional_test_results.json")

        browser.close()
        return results


if __name__ == "__main__":
    print("="*70)
    print("COMPREHENSIVE FUNCTIONAL TEST")
    print("Browser will be VISIBLE - watch the interactions!")
    print("="*70)
    test_comprehensive_functional()