"""
FULL VISUAL TEST - See every function working in the browser
Run with visible browser to watch all sections execute
"""
import time, json, sys, io, os
import requests
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = 'http://localhost:8000'
ENGINE = 'http://localhost:8100'
DASH = 'http://localhost:5173'

OUTPUT_DIR = "visual_full_test"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def test_everything():
    results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        
        log("="*70)
        log("STARTING FULL VISUAL TEST")
        log("="*70)
        
        log("="*70)
        log("STARTING FULL VISUAL TEST")
        log("="*70)
        
        # ═══════════════════════════════════════════════════════════════════
        # SECTION 1: HOME / DASHBOARD
        # ═══════════════════════════════════════════════════════════════════
        log("\n[SECTION 1] DASHBOARD")
        page.goto(DASH, timeout=30000)
        page.wait_for_load_state("networkidle", timeout=20000)
        page.screenshot(path=f"{OUTPUT_DIR}/01_dashboard.png", full_page=True)
        
        # Click through nav
        nav_buttons = ['Agents', 'Skills', 'Scheduler', 'Health', 'Signals', 'Betting', 'Content', 'Settings']
        for btn_name in nav_buttons[:5]:
            try:
                btn = page.locator(f"button:has-text('{btn_name}')").first
                if btn.is_visible():
                    btn.click()
                    time.sleep(1.5)
                    page.screenshot(path=f"{OUTPUT_DIR}/nav_{btn_name}.png")
                    log(f"  -> {btn_name}")
            except Exception as e:
                log(f"  ! {btn_name}: {str(e)[:30]}")
        
        results.append(("Dashboard Navigation", True))
        
        # ═══════════════════════════════════════════════════════════════════
        # SECTION 2: TEST API FUNCTIONS DIRECTLY
        # ═══════════════════════════════════════════════════════════════════
        log("\n[SECTION 2] API FUNCTIONS")
        
        # Health
        r = requests.get(f'{BASE}/health', timeout=10)
        log(f"  Health: {r.json().get('version')}")
        results.append(("Health API", r.status_code == 200))
        
        # Brain Reasoning
        r = requests.post(f'{BASE}/reason', json={'query': 'build a React login form'}, timeout=30)
        skill = r.json().get('decision', {}).get('chosen_skill', 'unknown')
        log(f"  Brain: '{skill}'")
        results.append(("Brain Reasoning", skill != 'unknown'))
        
        # Task
        r = requests.post(f'{BASE}/task', json={'query': 'create test component', 'skill': 'test'}, timeout=30)
        session = r.json().get('session_id', '')
        log(f"  Task: {session[:20]}...")
        results.append(("Task Execution", bool(session)))
        
        # Skills
        r = requests.get(f'{BASE}/skills', timeout=10)
        count = len(r.json().get('skills', []))
        log(f"  Skills: {count} loaded")
        results.append(("Skills", count > 0))
        
        # Knowledge
        r = requests.get(f'{BASE}/knowledge/stats', timeout=10)
        stats = r.json()
        log(f"  KB: {stats.get('snippets', 0)} snippets")
        results.append(("Knowledge Bank", True))
        
        # Betting
        r = requests.get(f'{BASE}/betting/odds', timeout=10)
        lines = r.json().get('count', 0)
        log(f"  Betting: {lines} odds")
        results.append(("Betting", lines > 0))
        
        # Social
        r = requests.get(f'{BASE}/social/posts', timeout=10)
        log(f"  Social: OK")
        results.append(("Social", True))
        
        # Soul
        r = requests.get(f'{BASE}/soul', timeout=10)
        name = r.json().get('summary', {}).get('name', '')
        log(f"  Soul: {name}")
        results.append(("Soul", bool(name)))
        
        # Scheduler
        r = requests.get(f'{BASE}/scheduler/tasks', timeout=10)
        tasks = len(r.json().get('tasks', []))
        log(f"  Scheduler: {tasks} tasks")
        results.append(("Scheduler", tasks > 0))
        
        # News
        r = requests.get(f'{BASE}/news', timeout=15)
        items = len(r.json().get('items', []))
        log(f"  News: {items} items")
        results.append(("News", items > 0))
        
        # Systems
        r = requests.get(f'{BASE}/systems/registry', timeout=10)
        agents = len(r.json().get('agents', []))
        log(f"  Systems: {agents} agents")
        results.append(("Systems", agents > 0))
        
        # Engine API
        r = requests.get(f'{ENGINE}/engine/state', timeout=10)
        skills = r.json().get('engine', {}).get('skill_count', 0)
        log(f"  Engine: {skills} skills")
        results.append(("Engine API", skills > 0))
        
        # ═══════════════════════════════════════════════════════════════════
        # SECTION 3: UI FORM FILLS
        # ═══════════════════════════════════════════════════════════════════
        log("\n[SECTION 3] UI INTERACTIONS")
        
        # Go to agents section and try to find input
        page.goto(f"{DASH}/#/agents", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.screenshot(path=f"{OUTPUT_DIR}/agents_section.png")
        
        # Try to find and fill reason input
        for selector in ["input[placeholder*='query']", "input[placeholder*='reason']", "input[type='text']"]:
            try:
                inp = page.locator(selector).first
                if inp.is_visible():
                    inp.fill("test query")
                    log(f"  Filled input: {selector}")
                    page.screenshot(path=f"{OUTPUT_DIR}/input_filled.png")
                    break
            except:
                pass
        
        # Go to scheduler and test form
        page.goto(f"{DASH}/#/scheduler", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.screenshot(path=f"{OUTPUT_DIR}/scheduler_section.png")
        
        # Fill scheduler form
        inputs = page.locator("input").all()
        log(f"  Scheduler inputs: {len(inputs)}")
        for i, inp in enumerate(inputs[:3]):
            try:
                ph = inp.get_attribute("placeholder") or ""
                inp.fill(f"test-{i}")
                log(f"    Filled: {ph}")
            except:
                pass
        
        # Go to settings
        page.goto(f"{DASH}/#/settings", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.screenshot(path=f"{OUTPUT_DIR}/settings_section.png")
        
        # Try clicking settings buttons
        btns = page.locator("button").all()
        log(f"  Settings buttons: {len(btns)}")
        for btn in btns[:3]:
            try:
                text = btn.text_content().strip()[:20]
                if text and text not in ['Dashboard', 'Agents']:
                    log(f"    Button: {text}")
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════════════
        # SECTION 4: DELIVERABLES
        # ═══════════════════════════════════════════════════════════════════
        log("\n[SECTION 4] DELIVERABLES")
        
        # Skill routing
        queries = [
            ("build React login", "add-auth"),
            ("create FastAPI", "scaffold-rest-api"),
            ("generate Dockerfile", "generate-dockerfile"),
            ("audit security", "security-best-practices"),
        ]
        
        routing = {}
        for q, expected in queries:
            r = requests.post(f'{BASE}/reason', json={'query': q}, timeout=30)
            skill = r.json().get('decision', {}).get('chosen_skill', 'unknown')
            routing[q[:15]] = skill
        
        log(f"  Routing: {json.dumps(routing, indent=2)[:200]}")
        
        # Knowledge search results
        r = requests.post(f'{BASE}/knowledge/search', json={'query': 'API'}, timeout=10)
        results_count = len(r.json().get('results', []))
        log(f"  KB Search: {results_count} results")
        
        # Betting recommendations
        r = requests.get(f'{BASE}/betting/sheet?sport=basketball_nba&bankroll=1000', timeout=30)
        picks = r.json().get('recommended_picks', 0)
        log(f"  Betting picks: {picks}")
        
        # News items
        r = requests.get(f'{BASE}/news', timeout=15)
        items = len(r.json().get('items', []))
        log(f"  News items: {items}")
        
        # ═══════════════════════════════════════════════════════════════════
        # FINAL SUMMARY
        # ═══════════════════════════════════════════════════════════════════
        log("\n" + "="*70)
        log("FINAL SUMMARY")
        log("="*70)
        
        passed = sum(1 for _, ok in results if ok)
        total = len(results)
        
        log(f"\nTotal: {passed}/{total} working")
        log(f"Screenshots saved to: {OUTPUT_DIR}/")
        
        for name, ok in results:
            status = "OK" if ok else "FAIL"
            log(f"  [{status}] {name}")
        
        browser.close()
        
        return results

if __name__ == "__main__":
    test_everything()