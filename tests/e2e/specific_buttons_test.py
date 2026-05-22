"""
SPECIFIC BUTTON TEST - Test the exact buttons user reported as broken
Quick Actions in Health section, and Scheduler buttons
"""
import time, json, sys, io, os
import requests
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DASHBOARD_URL = "http://localhost:5173"
API_BASE = "http://localhost:8000"

OUTPUT_DIR = "specific_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)

results = {"working": [], "broken": [], "details": []}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def save(page, name):
    page.screenshot(path=f"{OUTPUT_DIR}/{name}.png", full_page=True)


def test_specific_buttons():
    global results
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        
        # ═══════════════════════════════════════════════════════════════════════
        # Go to home/dashboard first
        # ═══════════════════════════════════════════════════════════════════════
        log("="*70)
        log("STEP 1: Go to Dashboard and find Health section")
        log("="*70)
        
        page.goto(DASHBOARD_URL, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        save(page, "01_home")
        
        # Look at page structure - what elements exist?
        log("\nAnalyzing page structure...")
        
        # Get all visible text content to understand the page
        body_text = page.locator("body").text_content()
        log(f"Page has content, length: {len(body_text)} chars")
        
        # Look for "Health" as text
        health_elements = page.locator("text=Health").all()
        log(f"Found {len(health_elements)} 'Health' text elements")
        
        # Click on Health
        for el in health_elements:
            try:
                tag = el.evaluate("el => el.tagName")
                log(f"  Health element: {tag}")
                if tag == "BUTTON":
                    el.click()
                    time.sleep(2)
                    save(page, "02_after_health_click")
                    log("  Clicked Health button")
                    break
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION: QUICK ACTIONS in Health
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("STEP 2: Find and test Quick Actions in Health section")
        log("="*70)
        
        # Look for quick action buttons - they might have specific text
        quick_action_texts = [
            "REFRESH STATUS",
            "CLEAR LOGS", 
            "RESET SYSTEM",
            "RUN DIAGNOSTICS",
            "CHECK CONNECTIONS",
            "TEST API",
            "SYNC DATA",
            "RELOAD",
            "CLEAR CACHE"
        ]
        
        for action_text in quick_action_texts:
            try:
                # Try different case combinations
                for case in [action_text.upper(), action_text, action_text.title()]:
                    btn = page.locator(f"button:has-text('{case}')").first
                    if btn.is_visible():
                        log(f"  FOUND: '{case}'")
                        save(page, f"03_before_{case.replace(' ', '_')}")
                        try:
                            btn.click()
                            time.sleep(2)
                            save(page, f"03_after_{case.replace(' ', '_')}")
                            results["working"].append(f"Quick Action: {case}")
                            log(f"    ✓ Clicked successfully")
                        except Exception as e:
                            results["broken"].append(f"Quick Action: {case} - {str(e)[:60]}")
                            log(f"    ✗ FAILED: {str(e)[:60]}")
                        break
            except:
                pass
        
        # Also look for any buttons with icon-like content (SVG, etc)
        log("\n  Looking for any action buttons in Health...")
        all_buttons = page.locator("button").all()
        log(f"  Total buttons on page: {len(all_buttons)}")
        
        for i, btn in enumerate(all_buttons):
            try:
                text = btn.text_content().strip()[:30]
                if text:
                    log(f"    Button {i}: '{text}'")
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION: SCHEDULER
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("STEP 3: Test Scheduler buttons")
        log("="*70)
        
        # Navigate to Scheduler - try various ways
        scheduler_ways = [
            "button:has-text('Scheduler')",
            "a:has-text('Scheduler')",
            "[class*='scheduler']"
        ]
        
        for way in scheduler_ways:
            try:
                el = page.locator(way).first
                if el.is_visible():
                    el.click()
                    time.sleep(2)
                    save(page, "04_scheduler")
                    log(f"  Navigated to Scheduler via {way}")
                    break
            except:
                pass
        
        # Now test specific scheduler buttons
        scheduler_buttons_to_test = [
            "ADD CRON",
            "RUN DUE",
            "RUN ALL",
            "PAUSE ALL",
            "RESUME ALL",
            "CLEAR COMPLETED",
            "DELETE SELECTED",
            "EDIT",
            "DELETE",
            "TOGGLE",
            "ENABLE",
            "DISABLE"
        ]
        
        log("  Testing scheduler buttons:")
        
        # First see what buttons exist
        scheduler_page_buttons = page.locator("button").all()
        log(f"  Buttons on scheduler page: {len(scheduler_page_buttons)}")
        
        for btn in scheduler_page_buttons:
            try:
                text = btn.text_content().strip()[:25]
                if text:
                    log(f"    - {text}")
            except:
                pass
        
        # Test each
        for btn_text in scheduler_buttons_to_test:
            for case in [btn_text.upper(), btn_text.title()]:
                try:
                    btn = page.locator(f"button:has-text('{case}')").first
                    if btn.is_visible():
                        log(f"  Testing: '{case}'")
                        save(page, f"05_before_{case.replace(' ', '_')}")
                        
                        btn.click()
                        time.sleep(2)
                        save(page, f"05_after_{case.replace(' ', '_')}")
                        
                        results["working"].append(f"Scheduler: {case}")
                        log(f"    ✓ OK")
                        break
                except Exception as e:
                    results["broken"].append(f"Scheduler: {case} - {str(e)[:60]}")
                    log(f"    ✗ {str(e)[:60]}")
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION: INPUT FIELDS THAT SHOULD WORK
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("STEP 4: Test input fields in Scheduler")
        log("="*70)
        
        # Get all inputs
        inputs = page.locator("input").all()
        log(f"  Input fields: {len(inputs)}")
        
        for i, inp in enumerate(inputs):
            try:
                placeholder = inp.get_attribute("placeholder") or ""
                log(f"    Input {i}: placeholder='{placeholder}'")
                
                if placeholder:
                    # Try to interact
                    inp.click()
                    inp.fill("test_value")
                    time.sleep(0.5)
                    results["working"].append(f"Input: {placeholder}")
                    log(f"      ✓ Filled")
            except Exception as e:
                results["broken"].append(f"Input {i}: {str(e)[:40]}")
                log(f"      ✗ {str(e)[:40]}")
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION: CHECK API BACKEND
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("STEP 5: Test API endpoints directly (verify backend works)")
        log("="*70)
        
        api_tests = [
            ("/scheduler/tasks", "GET", None),
            ("/scheduler/tasks", "POST", {"task": "test", "cron": "* * * * *", "skill": "test"}),
            ("/scheduler/run-due", "POST", None),
            ("/health", "GET", None),
        ]
        
        for endpoint, method, data in api_tests:
            try:
                if method == "GET":
                    r = requests.get(f"{API_BASE}{endpoint}", timeout=10)
                else:
                    r = requests.post(f"{API_BASE}{endpoint}", json=data, timeout=10)
                
                status = r.status_code
                if status == 200:
                    results["working"].append(f"API: {method} {endpoint}")
                    log(f"  ✓ {method} {endpoint} = {status}")
                else:
                    results["broken"].append(f"API: {method} {endpoint} = {status}")
                    log(f"  ✗ {method} {endpoint} = {status}")
            except Exception as e:
                results["broken"].append(f"API: {endpoint} - {str(e)[:40]}")
                log(f"  ✗ {method} {endpoint}: {str(e)[:40]}")
        
        # ═══════════════════════════════════════════════════════════════════════
        # FINAL SUMMARY
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("FINAL RESULTS")
        log("="*70)
        
        log(f"\n✓ WORKING ({len(results['working'])}):")
        for item in results["working"]:
            log(f"  - {item}")
        
        log(f"\n✗ BROKEN ({len(results['broken'])}):")
        for item in results["broken"]:
            log(f"  - {item[:100]}")
        
        # Save
        with open("specific_test_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        
        log(f"\nScreenshots saved to: {OUTPUT_DIR}/")
        
        browser.close()


if __name__ == "__main__":
    print("="*70)
    print("TESTING: Quick Actions, Scheduler, and Input Fields")
    print("Browser is VISIBLE")
    print("="*70)
    test_specific_buttons()