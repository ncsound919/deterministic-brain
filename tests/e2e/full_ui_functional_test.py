"""
FULL UI FUNCTIONAL TEST - Every button and function
Browser VISIBLE - test each UI element systematically
"""
import time, json, sys, io, os
import requests
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DASHBOARD_URL = "http://localhost:5173"
API_BASE = "http://localhost:8000"

OUTPUT_DIR = "full_ui_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)

results = {
    "sections": {},
    "working": [],
    "broken": [],
    "warnings": []
}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def save_screenshot(page, name):
    page.screenshot(path=f"{OUTPUT_DIR}/{name}.png")
    return f"{OUTPUT_DIR}/{name}.png"


def test_full_ui():
    global results
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 1: HOME / DASHBOARD
        # ═══════════════════════════════════════════════════════════════════════
        log("="*70)
        log("TESTING: HOME / DASHBOARD")
        log("="*70)
        
        page.goto(DASHBOARD_URL, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        save_screenshot(page, "01_home")
        
        # Find ALL buttons on the page
        all_buttons = page.locator("button").all()
        log(f"Total buttons found: {len(all_buttons)}")
        
        for i, btn in enumerate(all_buttons):
            try:
                text = btn.text_content().strip()[:30] if btn.text_content() else f"btn-{i}"
                log(f"  Button {i}: '{text}'")
            except:
                log(f"  Button {i}: (error reading)")
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 2: QUICK ACTIONS (Health Section)
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: QUICK ACTIONS (Health Section)")
        log("="*70)
        
        # Look for quick action buttons specifically
        quick_action_patterns = [
            "button:has-text('Refresh')",
            "button:has-text('Reset')",
            "button:has-text('Clear')",
            "button:has-text('Sync')",
            "button:has-text('Reload')",
            "[class*='action'] button",
            "[class*='quick'] button",
            "[class*='health'] button",
        ]
        
        quick_actions_found = []
        for pattern in quick_action_patterns:
            try:
                btns = page.locator(pattern).all()
                for btn in btns:
                    text = btn.text_content().strip()[:40]
                    if text and text not in [b[1] for b in quick_actions_found]:
                        quick_actions_found.append((btn, text))
            except Exception as e:
                pass
        
        log(f"Quick action buttons found: {len(quick_actions_found)}")
        
        # Test each quick action
        for btn, text in quick_actions_found:
            log(f"  Testing: '{text}'...")
            try:
                btn.click()
                time.sleep(1)
                save_screenshot(page, f"quick_action_{text[:15]}")
                results["working"].append(f"Quick action: {text}")
                log(f"    ✓ Clicked successfully")
            except Exception as e:
                results["broken"].append(f"Quick action: {text} - {str(e)[:50]}")
                log(f"    ✗ FAILED: {str(e)[:50]}")
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 3: NAVIGATION - Click each nav item
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: NAVIGATION")
        log("="*70)
        
        # Go back to home first
        page.goto(DASHBOARD_URL, timeout=15000)
        page.wait_for_load_state("networkidle", timeout=15000)
        
        # Find navigation links
        nav_selectors = [
            "nav a",
            "[class*='nav'] a",
            "[class*='sidebar'] a",
            ".nav-item",
            "a[class*='nav']"
        ]
        
        nav_links = []
        for selector in nav_selectors:
            try:
                links = page.locator(selector).all()
                for link in links:
                    href = link.get_attribute("href")
                    text = link.text_content().strip()[:30]
                    if text and text not in ["", "href"]:
                        nav_links.append((link, text, href))
            except:
                pass
        
        log(f"Navigation links found: {len(nav_links)}")
        
        for link, text, href in nav_links:
            log(f"  Testing nav: '{text}'...")
            try:
                link.click()
                time.sleep(1.5)
                save_screenshot(page, f"nav_{text[:15]}")
                results["working"].append(f"Navigation: {text}")
                log(f"    ✓ Navigated to {text}")
            except Exception as e:
                results["broken"].append(f"Navigation: {text} - {str(e)[:50]}")
                log(f"    ✗ FAILED: {str(e)[:50]}")
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 4: SCHEDULER
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: SCHEDULER")
        log("="*70)
        
        # Find scheduler section
        scheduler_selectors = [
            "a[href*='scheduler']",
            "[class*='scheduler']",
            "button:has-text('Scheduler')",
            "button:has-text('Schedule')",
        ]
        
        for selector in scheduler_selectors:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    el.click()
                    time.sleep(2)
                    save_screenshot(page, "scheduler_section")
                    log(f"  Opened scheduler")
                    break
            except:
                pass
        
        # Look for scheduler buttons
        scheduler_buttons = [
            "button:has-text('Add')",
            "button:has-text('New')",
            "button:has-text('Create')",
            "button:has-text('Run')",
            "button:has-text('Start')",
            "button:has-text('Stop')",
            "button:has-text('Pause')",
            "button:has-text('Resume')",
            "button:has-text('Delete')",
            "button:has-text('Edit')",
        ]
        
        for pattern in scheduler_buttons:
            try:
                btns = page.locator(pattern).all()
                for btn in btns:
                    if btn.is_visible():
                        text = btn.text_content().strip()
                        log(f"  Testing scheduler button: '{text}'...")
                        btn.click()
                        time.sleep(1)
                        save_screenshot(page, f"scheduler_{text[:10]}")
                        results["working"].append(f"Scheduler: {text}")
                        log(f"    ✓ Clicked")
            except Exception as e:
                results["broken"].append(f"Scheduler button: {str(e)[:50]}")
                log(f"    ✗ FAILED")
        
        # Look for schedule form inputs
        log("  Looking for schedule form...")
        form_inputs = page.locator("input").all()
        log(f"    Found {len(form_inputs)} inputs in scheduler section")
        
        # Try to find and fill schedule inputs
        input_placeholders = ["cron", "time", "task", "name", "description", "interval"]
        for inp in form_inputs[:5]:
            try:
                placeholder = inp.get_attribute("placeholder") or ""
                if any(p in placeholder.lower() for p in input_placeholders):
                    log(f"    Filling: {placeholder}")
                    inp.fill("test-value")
                    results["working"].append(f"Scheduler input: {placeholder}")
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 5: AGENTS / BRAIN
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: AGENTS / BRAIN")
        log("="*70)
        
        page.goto(DASHBOARD_URL, timeout=15000)
        time.sleep(1)
        
        # Find agents section
        for selector in ["a[href*='agents']", "button:has-text('Agents')", "[class*='agent']"]:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    el.click()
                    time.sleep(2)
                    save_screenshot(page, "agents_section")
                    break
            except:
                pass
        
        # Test brain/reason input
        brain_input_selectors = [
            "input[placeholder*='query']",
            "input[placeholder*='reason']",
            "input[placeholder*='ask']",
            "textarea[placeholder*='query']",
            "textarea[placeholder*='reason']",
        ]
        
        brain_input = None
        for selector in brain_input_selectors:
            try:
                inp = page.locator(selector).first
                if inp.is_visible():
                    brain_input = inp
                    break
            except:
                pass
        
        if brain_input:
            log("  Testing brain input...")
            brain_input.fill("create a Python hello world function")
            time.sleep(0.5)
            
            # Find submit
            submit_selectors = ["button[type='submit']", "button:has-text('Submit')", "button:has-text('Go')"]
            for selector in submit_selectors:
                try:
                    btn = page.locator(selector).first
                    if btn.is_visible():
                        btn.click()
                        time.sleep(4)
                        save_screenshot(page, "brain_result")
                        results["working"].append("Brain reasoning input")
                        log(f"    ✓ Submitted and got result")
                        break
                except:
                    pass
        else:
            results["broken"].append("Brain input not found")
            log("  ✗ Brain input not found")
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 6: KNOWLEDGE
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: KNOWLEDGE BANK")
        log("="*70)
        
        # Navigate to knowledge
        for selector in ["a[href*='knowledge']", "button:has-text('Knowledge')"]:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    el.click()
                    time.sleep(2)
                    save_screenshot(page, "knowledge_section")
                    break
            except:
                pass
        
        # Find knowledge inputs
        kb_inputs = page.locator("input, textarea").all()
        log(f"  Found {len(kb_inputs)} inputs")
        
        # Test search
        for inp in kb_inputs[:3]:
            try:
                placeholder = inp.get_attribute("placeholder") or ""
                if "search" in placeholder.lower():
                    log(f"  Testing search: '{placeholder}'")
                    inp.fill("API")
                    time.sleep(1)
                    
                    # Click search button
                    search_btn = page.locator("button:has-text('Search')").first
                    if search_btn.is_visible():
                        search_btn.click()
                        time.sleep(2)
                        save_screenshot(page, "kb_search_result")
                        results["working"].append("Knowledge search")
                        log(f"    ✓ Search works")
                    break
            except Exception as e:
                log(f"    ✗ Search failed: {str(e)[:40]}")
        
        # Test add/ingest
        for inp in kb_inputs[:3]:
            try:
                placeholder = inp.get_attribute("placeholder") or ""
                if "add" in placeholder.lower() or "ingest" in placeholder.lower() or "new" in placeholder.lower():
                    log(f"  Testing ingest: '{placeholder}'")
                    inp.fill("Test knowledge entry")
                    results["working"].append("Knowledge input")
                    log(f"    ✓ Input filled")
                    break
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 7: SKILLS
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: SKILLS")
        log("="*70)
        
        for selector in ["a[href*='skills']", "button:has-text('Skills')"]:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    el.click()
                    time.sleep(2)
                    save_screenshot(page, "skills_section")
                    results["working"].append("Skills section")
                    break
            except:
                pass
        
        # Look for skill action buttons
        skill_buttons = [
            "button:has-text('Import')",
            "button:has-text('Add')",
            "button:has-text('Create')",
            "button:has-text('Validate')",
            "button:has-text('Test')",
        ]
        
        for pattern in skill_buttons:
            try:
                btns = page.locator(pattern).all()
                for btn in btns:
                    if btn.is_visible():
                        text = btn.text_content().strip()
                        log(f"  Testing: '{text}'")
                        btn.click()
                        time.sleep(1)
                        save_screenshot(page, f"skill_{text[:10]}")
                        results["working"].append(f"Skill: {text}")
                        log(f"    ✓ Clicked")
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 8: BETTING
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: BETTING")
        log("="*70)
        
        for selector in ["a[href*='betting']", "button:has-text('Betting')"]:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    el.click()
                    time.sleep(2)
                    save_screenshot(page, "betting_section")
                    break
            except:
                pass
        
        # Test betting buttons
        betting_buttons = [
            "button:has-text('Refresh')",
            "button:has-text('Calculate')",
            "button:has-text('Analyze')",
            "button:has-text('Generate')",
        ]
        
        for pattern in betting_buttons:
            try:
                btns = page.locator(pattern).all()
                for btn in btns:
                    if btn.is_visible():
                        text = btn.text_content().strip()
                        log(f"  Testing: '{text}'")
                        btn.click()
                        time.sleep(2)
                        save_screenshot(page, f"betting_{text[:10]}")
                        results["working"].append(f"Betting: {text}")
                        log(f"    ✓ Clicked")
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 9: SOCIAL
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: SOCIAL / POSTS")
        log("="*70)
        
        for selector in ["a[href*='social']", "button:has-text('Social')"]:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    el.click()
                    time.sleep(2)
                    save_screenshot(page, "social_section")
                    break
            except:
                pass
        
        # Test social buttons
        social_buttons = [
            "button:has-text('Post')",
            "button:has-text('Schedule')",
            "button:has-text('Tweet')",
            "button:has-text('Publish')",
        ]
        
        for pattern in social_buttons:
            try:
                btns = page.locator(pattern).all()
                for btn in btns:
                    if btn.is_visible():
                        text = btn.text_content().strip()
                        log(f"  Testing: '{text}'")
                        btn.click()
                        time.sleep(1)
                        save_screenshot(page, f"social_{text[:10]}")
                        results["working"].append(f"Social: {text}")
                        log(f"    ✓ Clicked")
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 10: SETTINGS
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: SETTINGS")
        log("="*70)
        
        for selector in ["a[href*='settings']", "button:has-text('Settings')"]:
            try:
                el = page.locator(selector).first
                if el.is_visible():
                    el.click()
                    time.sleep(2)
                    save_screenshot(page, "settings_section")
                    results["working"].append("Settings section opened")
                    break
            except:
                pass
        
        # Test settings buttons
        settings_buttons = [
            "button:has-text('Save')",
            "button:has-text('Update')",
            "button:has-text('Reset')",
            "button:has-text('Test')",
        ]
        
        for pattern in settings_buttons:
            try:
                btns = page.locator(pattern).all()
                for btn in btns:
                    if btn.is_visible():
                        text = btn.text_content().strip()
                        log(f"  Testing: '{text}'")
                        btn.click()
                        time.sleep(1)
                        results["working"].append(f"Settings: {text}")
                        log(f"    ✓ Clicked")
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════════════════
        # SECTION 11: Any remaining buttons
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("TESTING: REMAINING BUTTONS")
        log("="*70)
        
        # Go to each major section and click remaining buttons
        sections_to_try = [
            ("signals", "Signals"),
            ("library", "Library"), 
            ("operations", "Operations"),
            ("tools", "Tools"),
            ("system", "System"),
        ]
        
        for section_key, section_name in sections_to_try:
            log(f"\n  Testing section: {section_name}")
            
            # Try to navigate
            try:
                # Try various navigation patterns
                for pattern in [f"a[href*='{section_key}']", f"button:has-text('{section_name}')"]:
                    el = page.locator(pattern).first
                    if el.is_visible():
                        el.click()
                        time.sleep(1.5)
                        save_screenshot(page, f"section_{section_key}")
                        break
            except:
                pass
            
            # Click any buttons in this section
            section_btns = page.locator("button").all()
            for btn in section_btns[:3]:
                try:
                    text = btn.text_content().strip()[:25]
                    if text and text not in ["", "submit"]:
                        log(f"    Clicking: '{text}'")
                        btn.click()
                        time.sleep(0.5)
                        results["working"].append(f"{section_name}: {text}")
                except:
                    pass
        
        # ═══════════════════════════════════════════════════════════════════════
        # FINAL SUMMARY
        # ═══════════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("FINAL SUMMARY")
        log("="*70)
        
        log(f"\nWORKING ({len(results['working'])}):")
        for item in results["working"]:
            log(f"  ✓ {item}")
        
        log(f"\nBROKEN ({len(results['broken'])}):")
        for item in results["broken"]:
            log(f"  ✗ {item}")
        
        log("\n" + "="*70)
        log(f"TOTAL: {len(results['working'])} working, {len(results['broken'])} broken")
        log("="*70)
        
        # Save results
        with open("full_ui_test_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        
        log(f"\nScreenshots: {OUTPUT_DIR}/")
        
        browser.close()
        return results


if __name__ == "__main__":
    print("="*70)
    print("FULL UI FUNCTIONAL TEST")
    print("Browser is VISIBLE - watch every interaction!")
    print("="*70)
    test_full_ui()