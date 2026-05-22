"""
Visual Quality Assessment - Grades UI/UX, data quality, and system outputs
Captures screenshots and evaluates each major section of the Aether Dashboard
"""
import time, json, sys, io, os
import requests
from playwright.sync_api import sync_playwright

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DASHBOARD_URL = "http://localhost:5173"
API_BASE = "http://localhost:8000"
ENGINE_API = "http://localhost:8100"

OUTPUT_DIR = "visual_test_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def grade_quality(name, data, criteria):
    """Grade quality based on criteria"""
    score = 0
    max_score = len(criteria) * 10
    feedback = []

    for criterion, check_fn in criteria.items():
        result = check_fn(data)
        if result["pass"]:
            score += 10
            feedback.append(f"[PASS] {criterion}")
        else:
            feedback.append(f"[FAIL] {criterion}: {result['reason']}")

    percentage = (score / max_score) * 100 if max_score > 0 else 0
    return {"score": score, "max": max_score, "percentage": percentage, "feedback": feedback}


def test_visual_quality():
    results = {
        "sections": [],
        "api_quality": {},
        "ui_quality": {},
        "data_quality": {},
        "overall_score": 0
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visible mode
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        # ─────────────────────────────────────────────────────────────────
        # SECTION 1: Dashboard Overview
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 1: Dashboard Overview")
        step_start = time.perf_counter()

        page.goto(DASHBOARD_URL, timeout=20000)
        page.wait_for_load_state("networkidle", timeout=20000)
        page.screenshot(path=f"{OUTPUT_DIR}/01_dashboard_overview.png", full_page=True)

        # Check header, nav, stats cards
        header_text = page.locator("h1").first.text_content(timeout=5000) if page.locator("h1").count() > 0 else ""
        nav_items = page.locator("nav, .nav, .sidebar").count()
        stat_cards = page.locator(".card, .stat, [class*='stat']").count()

        quality = grade_quality("Dashboard Overview", {
            "header": header_text,
            "nav_items": nav_items,
            "stat_cards": stat_cards,
            "console_errors": [c for c in console_logs if "error" in c.lower()]
        }, {
            "Has header title": lambda d: {"pass": bool(d.get("header")), "reason": "No header found"},
            "Has navigation": lambda d: {"pass": d.get("nav_items", 0) > 0, "reason": "No navigation found"},
            "Has stat displays": lambda d: {"pass": d.get("stat_cards", 0) > 0, "reason": "No stat cards"},
            "No console errors": lambda d: {"pass": len(d.get("console_errors", [])) == 0, "reason": f"{len(d.get('console_errors', []))} errors"}
        })

        results["sections"].append({
            "section": "Dashboard Overview",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"header": header_text, "nav_items": nav_items, "stat_cards": stat_cards},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        # ─────────────────────────────────────────────────────────────────
        # SECTION 2: Brain Reasoning (via API)
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 2: Brain Reasoning Quality")
        step_start = time.perf_counter()

        test_queries = [
            "build a React login form with JWT auth",
            "create a python REST API with FastAPI",
            "generate a Dockerfile for a Node.js app"
        ]

        reasoning_outputs = []
        for query in test_queries:
            r = requests.post(f"{API_BASE}/reason", json={"query": query}, timeout=30)
            data = r.json()
            decision = data.get("decision", {})
            reasoning_outputs.append({
                "query": query[:40],
                "skill": decision.get("chosen_skill", "unknown"),
                "confidence": decision.get("confidence", 0),
                "audit_ok": decision.get("audit_ok", False)
            })

        # Check for skill diversity and confidence levels
        skills_used = set(r.get("skill") for r in reasoning_outputs if r.get("skill") not in [None, "unknown", ""])
        avg_confidence = sum(r.get("confidence", 0) for r in reasoning_outputs) / len(reasoning_outputs)
        audit_pass_rate = sum(1 for r in reasoning_outputs if r.get("audit_ok")) / len(reasoning_outputs)

        quality = grade_quality("Brain Reasoning", {
            "outputs": reasoning_outputs,
            "skills_used_count": len(skills_used),
            "avg_confidence": avg_confidence,
            "audit_pass_rate": audit_pass_rate
        }, {
            "Routes to skills": lambda d: {"pass": d.get("skills_used_count", 0) > 0, "reason": "No skills routed"},
            "High avg confidence": lambda d: {"pass": d.get("avg_confidence", 0) > 0.5, "reason": f"Only {d.get('avg_confidence', 0):.2f}"},
            "High audit pass": lambda d: {"pass": d.get("audit_pass_rate", 0) > 0.8, "reason": f"Only {d.get('audit_pass_rate', 0):.0%} pass"},
            "Skill diversity": lambda d: {"pass": d.get("skills_used_count", 0) > 1, "reason": "Only 1 skill used"}
        })

        results["sections"].append({
            "section": "Brain Reasoning",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"avg_confidence": round(avg_confidence, 2), "skills_used": list(skills_used)},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        # ─────────────────────────────────────────────────────────────────
        # SECTION 3: Task Execution Quality
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 3: Task Execution Quality")
        step_start = time.perf_counter()

        task_resp = requests.post(f"{API_BASE}/task", json={
            "query": "create a React component called UserCard",
            "skill": "react-component"
        }, timeout=45)
        task_data = task_resp.json()

        # Extract output quality metrics
        final_output = task_data.get("final_output", {})
        status = task_data.get("status")
        artifacts = final_output.get("artifacts", []) if isinstance(final_output, dict) else []

        quality = grade_quality("Task Execution", {
            "status": status,
            "artifacts": artifacts,
            "has_output": bool(final_output)
        }, {
            "Status ok": lambda d: {"pass": d.get("status") == "ok", "reason": f"Status: {d.get('status')}"},
            "Has output": lambda d: {"pass": d.get("has_output"), "reason": "No output generated"},
            "Generates artifacts": lambda d: {"pass": len(d.get("artifacts", [])) > 0, "reason": "No files created"},
            "Output is useful": lambda d: {"pass": len(d.get("artifacts", [])) > 0 and isinstance(d.get("artifacts", [{}])[0], dict), "reason": "Invalid artifact format"}
        })

        results["sections"].append({
            "section": "Task Execution",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"status": status, "artifacts_count": len(artifacts)},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        # ─────────────────────────────────────────────────────────────────
        # SECTION 4: Knowledge Bank Quality
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 4: Knowledge Bank Quality")
        step_start = time.perf_counter()

        # Get stats
        stats_resp = requests.get(f"{API_BASE}/knowledge/stats", timeout=10)
        stats = stats_resp.json()

        # Search test
        search_resp = requests.post(f"{API_BASE}/knowledge/search", json={"query": "testing"}, timeout=10)
        search_data = search_resp.json()
        search_results = search_data.get("results", [])
        has_content = any(r.get("chunk_text") or r.get("content") for r in search_results)

        quality = grade_quality("Knowledge Bank", {
            "total_fragments": stats.get("total_fragments", 0),
            "snippets": stats.get("snippets", 0),
            "search_results": len(search_results),
            "has_content": has_content
        }, {
            "Has stored data": lambda d: {"pass": d.get("total_fragments", 0) + d.get("snippets", 0) > 0, "reason": "No data stored"},
            "Search works": lambda d: {"pass": d.get("search_results", 0) > 0, "reason": "No search results"},
            "Content relevant": lambda d: {"pass": d.get("has_content"), "reason": "No actual content in results"},
            "Multiple snippets": lambda d: {"pass": d.get("snippets", 0) > 3, "reason": f"Only {d.get('snippets', 0)} snippets"}
        })

        results["sections"].append({
            "section": "Knowledge Bank",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"fragments": stats.get("total_fragments"), "snippets": stats.get("snippets")},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        # ─────────────────────────────────────────────────────────────────
        # SECTION 5: Betting Engine Quality
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 5: Betting Engine Quality")
        step_start = time.perf_counter()

        odds_resp = requests.get(f"{API_BASE}/betting/odds", timeout=10)
        odds_data = odds_resp.json()
        lines = odds_data.get("lines", [])
        unique_events = set(l.get("event") for l in lines)

        sheet_resp = requests.get(f"{API_BASE}/betting/sheet?sport=basketball_nba&bankroll=1000", timeout=30)
        sheet_data = sheet_resp.json()
        picks = sheet_data.get("recommended_picks", 0)
        analysis = sheet_data.get("analysis", {})

        quality = grade_quality("Betting Engine", {
            "odds_lines": len(lines),
            "unique_events": len(unique_events),
            "recommended_picks": picks,
            "has_analysis": bool(analysis)
        }, {
            "Has live odds": lambda d: {"pass": d.get("odds_lines", 0) > 0, "reason": "No odds available"},
            "Multiple events": lambda d: {"pass": d.get("unique_events", 0) > 1, "reason": "Only 1 event"},
            "Makes recommendations": lambda d: {"pass": d.get("recommended_picks", 0) > 0, "reason": "No picks recommended"},
            "Provides analysis": lambda d: {"pass": d.get("has_analysis"), "reason": "No analysis provided"}
        })

        results["sections"].append({
            "section": "Betting Engine",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"odds_lines": len(lines), "events": len(unique_events), "picks": picks},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        # ─────────────────────────────────────────────────────────────────
        # SECTION 6: Social Scheduler Quality
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 6: Social Scheduler Quality")
        step_start = time.perf_counter()

        schedule_resp = requests.post(f"{API_BASE}/social/schedule", params={
            "platform": "twitter",
            "content": "Quality test post",
            "delay_minutes": 30
        }, timeout=10)

        queue_resp = requests.get(f"{API_BASE}/social/posts", timeout=10)
        queue_data = queue_resp.json()
        posts = queue_data.get("posts", [])
        has_content = any(p.get("content") for p in posts)

        quality = grade_quality("Social Scheduler", {
            "schedule_works": schedule_resp.status_code == 200,
            "queue_count": len(posts),
            "has_content": has_content,
            "platforms": list(set(p.get("platform") for p in posts if p.get("platform")))
        }, {
            "Schedule works": lambda d: {"pass": d.get("schedule_works"), "reason": "Failed to schedule"},
            "Queue has posts": lambda d: {"pass": d.get("queue_count", 0) > 0, "reason": "Empty queue"},
            "Has content": lambda d: {"pass": d.get("has_content"), "reason": "Posts have no content"},
            "Multiple posts": lambda d: {"pass": d.get("queue_count", 0) > 1, "reason": "Only 1 post"}
        })

        results["sections"].append({
            "section": "Social Scheduler",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"queue_count": len(posts)},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        # ─────────────────────────────────────────────────────────────────
        # SECTION 7: Soul Identity Quality
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 7: Soul Identity Quality")
        step_start = time.perf_counter()

        soul_resp = requests.get(f"{API_BASE}/soul", timeout=10)
        soul_data = soul_resp.json()
        summary = soul_data.get("summary", {})
        name = summary.get("name") or soul_data.get("name")
        role = summary.get("role") or soul_data.get("role")
        agenda = soul_data.get("agenda", {})
        goals = agenda.get("goals", []) if isinstance(agenda, dict) else []
        meta = soul_data.get("meta", {})
        sessions = meta.get("session_count", 0)

        pulse_resp = requests.post(f"{API_BASE}/soul/pulse", json={}, timeout=10)
        pulse_data = pulse_resp.json() if pulse_resp.text else {}
        recent_sessions = pulse_data.get("recent_sessions", []) if isinstance(pulse_data, dict) else []

        quality = grade_quality("Soul Identity", {
            "name": name,
            "role": role,
            "goals_count": len(goals),
            "sessions": sessions,
            "has_history": len(recent_sessions) > 0
        }, {
            "Has identity": lambda d: {"pass": bool(d.get("name")), "reason": "No name set"},
            "Has role": lambda d: {"pass": bool(d.get("role")), "reason": "No role defined"},
            "Has goals": lambda d: {"pass": d.get("goals_count", 0) > 0, "reason": "No goals set"},
            "Has history": lambda d: {"pass": d.get("sessions", 0) > 10, "reason": f"Only {d.get('sessions', 0)} sessions"}
        })

        results["sections"].append({
            "section": "Soul Identity",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"name": name, "role": role, "goals": len(goals), "sessions": sessions},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        # ─────────────────────────────────────────────────────────────────
        # SECTION 8: News & Intel Quality
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 8: News & Intel Quality")
        step_start = time.perf_counter()

        news_resp = requests.get(f"{API_BASE}/news", timeout=15)
        news_data = news_resp.json()
        items = news_data.get("news", []) or news_data.get("items", [])
        sources = list(set(n.get("source") for n in items if n.get("source")))

        unified_resp = requests.get(f"{API_BASE}/news/unified", timeout=15)
        unified_data = unified_resp.json()
        categories = list(unified_data.keys())

        quality = grade_quality("News & Intel", {
            "news_count": len(items),
            "sources": len(sources),
            "categories": len(categories),
            "has_content": any(n.get("title") or n.get("headline") or n.get("description") for n in items[:3])
        }, {
            "Has news items": lambda d: {"pass": d.get("news_count", 0) > 0, "reason": f"Only {d.get('news_count', 0)} items"},
            "Multiple sources": lambda d: {"pass": d.get("sources", 0) > 2, "reason": f"Only {d.get('sources', 0)} sources"},
            "Categorized": lambda d: {"pass": d.get("categories", 0) > 2, "reason": f"Only {d.get('categories', 0)} categories"},
            "Content present": lambda d: {"pass": d.get("has_content"), "reason": "No titles in news"}
        })

        results["sections"].append({
            "section": "News & Intel",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"news_count": len(items), "sources": sources[:3], "categories": categories},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        # ─────────────────────────────────────────────────────────────────
        # SECTION 9: Engine API Quality
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 9: Engine API Quality")
        step_start = time.perf_counter()

        state_resp = requests.get(f"{ENGINE_API}/engine/state", timeout=10)
        state_data = state_resp.json()
        engine_info = state_data.get("engine", {})
        skill_count = engine_info.get("skill_count", 0)
        components = state_data.get("components", [])

        proc_resp = requests.post(f"{ENGINE_API}/engine/process", json={"query": "test quality"}, timeout=30)
        proc_data = proc_resp.json()
        proc_status = proc_data.get("status")
        result = proc_data.get("result", {})

        quality = grade_quality("Engine API", {
            "skill_count": skill_count,
            "components": len(components),
            "process_works": proc_status == "ok",
            "has_result": bool(result)
        }, {
            "Many skills": lambda d: {"pass": d.get("skill_count", 0) > 100, "reason": f"Only {d.get('skill_count', 0)} skills"},
            "Multiple components": lambda d: {"pass": d.get("components", 0) > 5, "reason": f"Only {d.get('components', 0)} components"},
            "Process works": lambda d: {"pass": d.get("process_works"), "reason": f"Status: {d.get('process_works')}"},
            "Returns result": lambda d: {"pass": d.get("has_result"), "reason": "No result returned"}
        })

        results["sections"].append({
            "section": "Engine API",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"skills": skill_count, "components": len(components)},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        # ─────────────────────────────────────────────────────────────────
        # SECTION 10: UI/UX Quality (Visual)
        # ─────────────────────────────────────────────────────────────────
        print("\n[GRADING] Section 10: UI/UX Quality")
        step_start = time.perf_counter()

        # Take screenshots of different pages
        page.goto(f"{DASHBOARD_URL}/#/agents", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.screenshot(path=f"{OUTPUT_DIR}/02_agents_page.png")

        page.goto(f"{DASHBOARD_URL}/#/signals", timeout=15000)
        page.wait_for_load_state("networkidle", timeout=15000)
        page.screenshot(path=f"{OUTPUT_DIR}/03_signals_page.png")

        # Check for visible UI elements
        visible_elements = page.locator("div, section, main").count()
        buttons = page.locator("button").count()
        inputs = page.locator("input, textarea").count()

        quality = grade_quality("UI/UX", {
            "visible_elements": visible_elements,
            "buttons": buttons,
            "inputs": inputs,
            "console_errors": len([c for c in console_logs if "error" in c.lower()])
        }, {
            "Has content": lambda d: {"pass": d.get("visible_elements", 0) > 10, "reason": "Too few elements"},
            "Has interactive": lambda d: {"pass": d.get("buttons", 0) > 0, "reason": "No buttons found"},
            "Clean console": lambda d: {"pass": d.get("console_errors", 0) == 0, "reason": f"{d.get('console_errors', 0)} errors"}
        })

        results["sections"].append({
            "section": "UI/UX",
            "score": quality["percentage"],
            "time_ms": round((time.perf_counter() - step_start) * 1000),
            "details": {"buttons": buttons, "inputs": inputs},
            "feedback": quality["feedback"]
        })
        print(f"  Score: {quality['percentage']:.0f}%")

        browser.close()

        # Calculate overall score
        total_score = sum(s["score"] for s in results["sections"])
        max_score = len(results["sections"]) * 100
        overall_percentage = (total_score / max_score) * 100

        results["overall_score"] = round(overall_percentage, 1)
        results["total_sections"] = len(results["sections"])

        return results


def print_report(results):
    print("\n" + "=" * 70)
    print("VISUAL QUALITY ASSESSMENT REPORT")
    print("=" * 70)

    print("\n📊 SECTION-BY-SECTION GRADES:")
    print("-" * 70)

    for section in results["sections"]:
        bar = "█" * int(section["score"] / 10) + "░" * (10 - int(section["score"] / 10))
        print(f"  {section['section']:25} {bar} {section['score']:.0f}%  ({section['time_ms']}ms)")

    print("\n" + "=" * 70)
    print(f"OVERALL QUALITY SCORE: {results['overall_score']:.1f}%")
    print(f"Sections Tested: {results['total_sections']}")
    print("=" * 70)

    # Detailed feedback
    print("\n📋 DETAILED FEEDBACK:")
    print("-" * 70)
    for section in results["sections"]:
        print(f"\n[{section['section']}]")
        for feedback in section["feedback"]:
            print(f"  {feedback}")

    print(f"\n\n📁 Screenshots saved to: {OUTPUT_DIR}/")
    print("  - 01_dashboard_overview.png")
    print("  - 02_agents_page.png")
    print("  - 03_signals_page.png")

    # Save results
    with open("visual_quality_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\nResults saved to visual_quality_results.json")


if __name__ == "__main__":
    print("Starting Visual Quality Assessment...")
    results = test_visual_quality()
    print_report(results)