"""Comprehensive system benchmark — exercises every subsystem and produces a deliverable report."""
from __future__ import annotations
import json, time, sys, traceback
import requests
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "http://localhost:8000"
RESULTS = {}

def call(method: str, path: str, json_data: dict = None, params: dict = None, timeout: int = 30) -> tuple:
    url = f"{BASE}{path}"
    t0 = time.perf_counter()
    try:
        if method == "GET":
            r = requests.get(url, params=params, timeout=timeout)
        else:
            r = requests.post(url, json=json_data, params=params, timeout=timeout)
        ms = round((time.perf_counter() - t0) * 1000)
        return r.status_code, r.json() if r.text else {}, ms
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000)
        return 0, {"_error": str(e)}, ms

def bm(name, method, path, data=None, params=None, timeout=30):
    code, result, ms = call(method, path, data, params=params, timeout=timeout)
    ok = code == 200 and not result.get("_error")
    RESULTS[name] = {"code": code, "ok": ok, "ms": ms, "result": result}
    status = "OK" if ok else f"FAIL({code})"
    print(f"  [{status} {ms}ms] {name}")
    return result

# ═══════════════════════════════════════════════════════════════════════
print("=" * 70)
print("DETERMINISTIC BRAIN — FULL SYSTEM BENCHMARK")
print(f"Target: {BASE}")
print(f"Time:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# ── 1. SYSTEM HEALTH ────────────────────────────────────────────────
print("\n── 1. SYSTEM HEALTH ──")
health = bm("Health check", "GET", "/health")
version = health.get("version", "?")
print(f"   Version: {version}")

integrations = bm("Integrations status", "GET", "/integrations")
apis = integrations.get("apis", {})
configured = sum(1 for v in apis.values() if v.get("configured"))
total_apis = len(apis)
features = integrations.get("features", {})
print(f"   APIs configured: {configured}/{total_apis}")
print(f"   Features: {', '.join(k for k,v in features.items() if v.get('available'))}")

llm = bm("LLM Status", "GET", "/llm-status")
print(f"   LLM: provider={llm.get('provider')}, available={llm.get('available')}")

# ── 2. BRAIN REASONING ──────────────────────────────────────────────
print("\n── 2. BRAIN REASONING ──")
queries = [
    ("build a React login form with JWT auth", "coding"),
    ("create a python REST API with FastAPI", "coding"),
    ("generate a Dockerfile for a Node.js app", "coding"),
    ("audit my codebase for security vulnerabilities", "coding"),
    ("I have a business proposal — should I accept it?", "business"),
    ("what are the legal implications of hiring contractors?", "business"),
    ("open the browser and navigate to github.com", "browser"),
    ("explain quantum computing to a beginner", "general"),
    ("write a blog post about AI safety", "content"),
    ("scaffold a SaaS landing page with stripe payments", "coding"),
]
reasoning_deliverables = []
for q, cat in queries:
    data = bm(f"Reason: {q[:50]}...", "POST", "/reason", {"query": q})
    dec = data.get("decision", {})
    skill = dec.get("chosen_skill", "?")
    conf = dec.get("confidence", 0)
    audit = dec.get("audit_ok", False)
    reasoning_deliverables.append({
        "query": q, "category": cat,
        "chosen_skill": skill, "confidence": round(conf, 4),
        "audit_passed": audit
    })
    print(f"     -> {skill} (conf={conf:.3f}, audit={'PASS' if audit else 'FAIL'})")

# ── 3. BRAIN TASK EXECUTION ─────────────────────────────────────────
print("\n── 3. TASK EXECUTION ──")
exec_tasks = [
    "create a React component called UserCard",
    "write a FastAPI endpoint for user registration",
    "generate a README.md for a Python project",
]
exec_deliverables = []
for t in exec_tasks:
    data = bm(f"Execute: {t[:50]}...", "POST", "/task", {"query": t})
    fo = data.get("final_output", {})
    out_text = ""
    if isinstance(fo, dict):
        out_text = fo.get("output", "") or str(fo.get("artifacts", ""))[:200]
    elif isinstance(fo, str):
        out_text = fo
    exec_deliverables.append({
        "query": t,
        "status": data.get("status"),
        "skill": data.get("task", {}).get("task", "?"),
        "has_output": bool(out_text),
        "output_len": len(out_text) if out_text else 0,
        "session_id": data.get("session_id", "?")[:12],
    })
    out = data.get("final_output", {})
    if isinstance(out, dict):
        print(f"     status={data.get('status')}, output='{out.get('output','')[:80]}...'")
    else:
        print(f"     status={data.get('status')}, output={len(str(out))} chars")

# ── 4. SKILLS REGISTRY ──────────────────────────────────────────────
print("\n── 4. SKILLS REGISTRY ──")
skills_data = bm("Skills list", "GET", "/skills")
skills = skills_data.get("skills", [])
print(f"   Total skills: {len(skills)}")

bundles_data = bm("Bundles list", "GET", "/bundles")
bundles = bundles_data.get("bundles", [])
print(f"   Bundles: {len(bundles)} -> {[b['name'] for b in bundles[:5]]}")

chains_data = bm("Chains list", "GET", "/chains")
chains = chains_data.get("chains", [])
print(f"   Chains: {len(chains)}")

# Forge validate a real skill file
bundle_result = bm(f"Forge validate", "POST", "/forge/validate", data={
    "path": "skill_packs/skills-main/skills/scaffold-rest-api/SKILL.md"
})
print(f"   Forge: status={bundle_result.get('status', '?')}")

# ── 5. KNOWLEDGE BANK ───────────────────────────────────────────────
print("\n── 5. KNOWLEDGE BANK ──")
kb_stats = bm("KB Stats", "GET", "/knowledge/stats")
print(f"   Fragments: {kb_stats.get('fragments', 0)}, Snippets: {kb_stats.get('snippets', 0)}")

kb_search = bm("KB Search", "POST", "/knowledge/search", {"query": "React hooks pattern", "top_k": 3})
kb_results = kb_search.get("results", [])
print(f"   Search results: {len(kb_results)}")

# Ingest new data via text endpoint
kb_ingest = bm("KB Ingest", "POST", "/knowledge/ingest-text", data={
    "text": "The Observer pattern is a behavioral design pattern where an object maintains a list of dependents and notifies them of state changes. Used in event-driven architectures.",
    "title": "Design Patterns Handbook"
})
print(f"   Ingested: {kb_ingest.get('ingested', 0)} fragments")

# Verify ingested content is searchable
kb_verify = bm("KB Verify search", "POST", "/knowledge/search", {"query": "Observer pattern design", "top_k": 3})
print(f"   Verified: {len(kb_verify.get('results', []))} results")

# ── 6. SAAS BUILDER ─────────────────────────────────────────────────
print("\n── 6. SAAS BUILDER ──")
projects_list = bm("Projects list", "GET", "/saas/projects")
projects = projects_list.get("projects", [])
print(f"   Projects: {len(projects)}")

saas_create = bm("Create project", "POST", "/saas/create", params={
    "name": "BenchmarkProject",
    "idea": "E2E benchmark SaaS project",
    "tech_stack": "python,fastapi,react"
})
print(f"   Created: {saas_create.get('project', {}).get('name', '?')}")

# ── 7. SOCIAL SCHEDULER ─────────────────────────────────────────────
print("\n── 7. SOCIAL SCHEDULER ──")
social_schedule = bm("Schedule post", "POST", "/social/schedule", params={
    "platform": "twitter",
    "content": f"Benchmark report generated at {time.strftime('%H:%M')}",
    "delay_minutes": 120
})
print(f"   Schedule: {social_schedule.get('status')}")

social_feed = bm("Social feed", "GET", "/social/posts")
social_posts = social_feed.get("posts", [])
print(f"   Posts in queue: {len(social_posts)}")

# ── 8. BETTING ENGINE ───────────────────────────────────────────────
print("\n── 8. BETTING ENGINE ──")
odds = bm("Odds feed", "GET", "/betting/odds")
odds_lines = odds.get("lines", [])
print(f"   Odds lines: {len(odds_lines)}")
if odds_lines:
    for line in odds_lines[:3]:
        print(f"     {line.get('event')} | {line.get('market')} | {line.get('selection')} @ {line.get('odds')}")

sheet = bm("Bet sheet", "GET", "/betting/sheet?sport=basketball_nba&bankroll=1000")
sheet_keys = list(sheet.keys())
print(f"   Sheet keys: {sheet_keys}")
picks = sheet.get("recommended_picks", [])
if isinstance(picks, list) and picks:
    for pick in picks[:3]:
        print(f"     PICK: {pick.get('selection')} @ {pick.get('odds')} (EV: {pick.get('ev', '?')})")
elif isinstance(picks, int):
    print(f"   {picks} recommended picks (int)")

kelly = bm("Kelly calc", "GET", "/betting/kelly?bankroll=1000")
kelly_recs = kelly.get("recommendations", [])
print(f"   Kelly recommendations: {len(kelly_recs)}")

# ── 9. SOUL IDENTITY ────────────────────────────────────────────────
print("\n── 9. SOUL IDENTITY ──")
soul = bm("Soul read", "GET", "/soul")
print(f"   Identity: {soul.get('identity', {}).get('name')} / {soul.get('identity', {}).get('role')}")

pulse = bm("Soul pulse", "POST", "/soul/pulse")
print(f"   Sessions: {pulse.get('sessions')}")

# ── 10. PLANNER ─────────────────────────────────────────────────────
print("\n── 10. PLANNER ──")
planner_tasks = bm("Planner tasks", "GET", "/planner/tasks")
planner_list = planner_tasks.get("tasks", [])
print(f"   Tasks: {len(planner_list)}")
for t in planner_list[:3]:
    print(f"     [{t.get('status')}] {t.get('title')}")

planner_add = bm("Planner add task", "POST", "/planner/tasks", {
    "title": "Benchmark follow-up actions",
    "status": "pending"
})
print(f"   Added: id={planner_add.get('id', '?')[:12]}")

# ── 11. DIALOGUE & CHAT ─────────────────────────────────────────────
print("\n── 11. DIALOGUE & CHAT ──")
dialogues = [
    ("hello", "greeting"),
    ("help me understand something", "help"),
    ("goodbye and thanks", "farewell"),
]
for msg, expected_type in dialogues:
    data = bm(f"Dialogue: {msg}", "POST", "/dialogue/process", data={"text": msg})
    print(f"     '{msg}' -> intent={data.get('intent')}, response={data.get('response', '')[:60]}...")

chat_data = bm("Chat route", "POST", "/chat", {"text": "what skills can you use?"})
print(f"   Chat response: {chat_data.get('text', '')[:100]}...")

# ── 12. SCHEDULER & AUTONOMY ────────────────────────────────────────
print("\n── 12. SCHEDULER & AUTONOMY ──")
sched_tasks = bm("Scheduler tasks", "GET", "/scheduler/tasks")
print(f"   Scheduled tasks: {len(sched_tasks.get('tasks', []))}")

kairos = bm("KAIROS status", "GET", "/kairos/status")
print(f"   KAIROS: running={kairos.get('running')}, runs={kairos.get('total_runs')}")

autonomy = bm("Autonomy status", "GET", "/autonomy/status")
dream_stats = autonomy.get("dream_stats", {})
print(f"   Dreams: cycles={dream_stats.get('cycles')}, skills_expanded={dream_stats.get('total_skills_expanded')}")

autodream = bm("AutoDream status", "GET", "/autodream/status")
print(f"   AutoDream: corrections={autodream.get('corrections', 0)}")

# ── 13. SYSTEMS REGISTRY ────────────────────────────────────────────
print("\n── 13. SYSTEMS REGISTRY ──")
sys_reg = bm("Systems registry", "GET", "/systems/registry")
agents = sys_reg.get("agents", [])
print(f"   Registered agents: {len(agents)}")

sys_health = bm("Systems health", "GET", "/systems/health")
for name, status in sys_health.items():
    print(f"   {name}: {status}")

# ── 14. NEWS & INTEL ────────────────────────────────────────────────
print("\n── 14. NEWS & INTEL ──")
news = bm("News feed", "GET", "/news")
news_items = news.get("items", [])
print(f"   News items: {len(news_items)}")
for item in news_items[:3]:
    print(f"     [{item.get('source')}] {item.get('title')[:70]}...")

news_unified = bm("News unified", "GET", "/news/unified")
cats = news_unified.get("categories", {})
for cat, items in cats.items():
    if items:
        print(f"   {cat}: {len(items)} items")

opportunities = bm("Opportunities", "GET", "/opportunities")
print(f"   Opportunities found: {len(opportunities.get('opportunities', []))}")

# ── 15. TEMPLATES & SETTINGS ────────────────────────────────────────
print("\n── 15. TEMPLATES & SETTINGS ──")
templates = bm("Templates list", "GET", "/templates")
print(f"   Templates: {len(templates.get('templates', []))}")

settings_keys = bm("Settings keys", "POST", "/settings/keys", {
    "anthropic": "test-key-12345",
    "openai": "test-key-67890"
})
print(f"   Keys saved: {settings_keys.get('saved', [])}")

# ── 16. MIDDLEWARE & STATS ──────────────────────────────────────────
print("\n── 16. MIDDLEWARE & STATS ──")
stats = bm("Route stats", "GET", "/dashboard/middleware-stats")
routes = stats.get("routes", {})
top_routes = sorted(routes.items(), key=lambda x: x[1].get("total", 0), reverse=True)[:5]
for path, data in top_routes:
    print(f"   {data.get('methods', ['?'])[0]} {path}: {data.get('total')} calls")

# ── 17. DASHBOARD FEED ──────────────────────────────────────────────
print("\n── 17. DASHBOARD FEED ──")
feed = bm("Dashboard feed", "GET", "/dashboard/feed")
feed_events = feed.get("events", [])
print(f"   Feed events: {len(feed_events)}")
event_types = {}
for e in feed_events:
    evt = e.get("event", "?")
    event_types[evt] = event_types.get(evt, 0) + 1
for evt, count in sorted(event_types.items()):
    print(f"     {evt}: {count}")

# ── 18. ENGINE API (port 8100) ─────────────────────────────────────
print("\n── 18. ENGINE API (port 8100) ──")
ENG_BASE = "http://localhost:8100"

def eng_call(method, path, json_data=None):
    url = f"{ENG_BASE}{path}"
    t0 = time.perf_counter()
    try:
        if method == "GET":
            r = requests.get(url, timeout=30)
        else:
            r = requests.post(url, json=json_data, timeout=30)
        ms = round((time.perf_counter() - t0) * 1000)
        return r.status_code, r.json() if r.text else {}, ms
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000)
        return 0, {"_error": str(e)}, ms

def eng_bm(name, method, path, data=None):
    code, result, ms = eng_call(method, path, data)
    ok = code == 200 and not result.get("_error")
    RESULTS[name] = {"code": code, "ok": ok, "ms": ms, "result": result}
    status = "OK" if ok else f"FAIL({code})"
    print(f"  [{status} {ms}ms] {name}")
    return result

eng_state = eng_bm("Engine state", "GET", "/engine/state")
if eng_state:
    print(f"   Engine: {eng_state.get('engine', {}).get('name')}")

eng_process = eng_bm("Engine process", "POST", "/engine/process", {"query": "test the benchmark pipeline"})
print(f"   Process: {eng_process.get('status')}")
result = eng_process.get("result", {})
print(f"   Result keys: {list(result.keys())[:8]}")

eng_events = eng_bm("Engine events", "GET", "/engine/events")
eng_evt_list = eng_events.get("events", [])
print(f"   Engine events: {len(eng_evt_list)}")

# ═══════════════════════════════════════════════════════════════════════
# DELIVERABLES & REPORT
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("DELIVERABLES PER SYSTEM")
print("=" * 70)

deliverables = {}

# 1. Reasoning deliverable: skill routing matrix
deliverables["reasoning_matrix"] = reasoning_deliverables
print("\n1. BRAIN REASONING — Skill Routing Matrix:")
print(f"   {'Query':<50} {'Skill':<25} {'Conf':<8} {'Audit'}")
print(f"   {'-'*50} {'-'*25} {'-'*8} {'-'*5}")
for d in reasoning_deliverables:
    print(f"   {d['query']:<50} {d['chosen_skill']:<25} {d['confidence']:<8.3f} {'PASS' if d['audit_passed'] else 'FAIL'}")

# 2. Task execution deliverables
deliverables["task_execution"] = exec_deliverables
print("\n2. TASK EXECUTION — Session Results:")
for d in exec_deliverables:
    print(f"   Session {d['session_id']}: {d['skill']} -> status={d['status']}, output={'YES' if d['has_output'] else 'NO'}")

# 3. Knowledge bank deliverables
deliverables["knowledge"] = {
    "fragments": kb_stats.get("fragments", 0),
    "snippets": kb_stats.get("snippets", 0),
    "search_works": len(kb_results) > 0,
    "ingest_works": kb_ingest.get("ingested", 0) > 0,
    "ingest_verified": len(kb_verify.get("results", [])) > 0,
}
print("\n3. KNOWLEDGE BANK:")
print(f"   Storage: {deliverables['knowledge']['fragments']} fragments, {deliverables['knowledge']['snippets']} snippets")
print(f"   Search: {'works' if deliverables['knowledge']['search_works'] else 'broken'}")
print(f"   Ingest: {'works' if deliverables['knowledge']['ingest_works'] else 'broken'}")
print(f"   Verify: {'passes' if deliverables['knowledge']['ingest_verified'] else 'fails'}")

# 4. Betting deliverable
deliverables["betting"] = {
    "odds_lines": len(odds_lines),
    "has_sheet": bool(sheet.get("recommended_picks")),
    "sheet_picks": len(sheet.get("recommended_picks", [])) if isinstance(sheet.get("recommended_picks"), list) else (sheet.get("recommended_picks", 0) if isinstance(sheet.get("recommended_picks"), int) else 0),
    "kelly_recs": len(kelly_recs),
}
print("\n4. BETTING ENGINE:")
print(f"   Live odds: {deliverables['betting']['odds_lines']} lines")
print(f"   Bet sheet: {deliverables['betting']['sheet_picks']} recommended picks")
print(f"   Kelly sizing: {deliverables['betting']['kelly_recs']} recommendations")

# 5. Social deliverable
deliverables["social"] = {
    "posts_queued": len(social_posts),
    "schedule_works": social_schedule.get("status") == "ok",
}
print("\n5. SOCIAL SCHEDULER:")
print(f"   Queue: {deliverables['social']['posts_queued']} posts")
print(f"   Publishing: {'works' if deliverables['social']['schedule_works'] else 'broken'}")

# 6. SaaS deliverable
deliverables["saas"] = {
    "projects": len(projects),
    "create_works": bool(saas_create.get("id")),
}
print("\n6. SAAS BUILDER:")
print(f"   Projects: {deliverables['saas']['projects']}")
print(f"   Create: {'works' if deliverables['saas']['create_works'] else 'broken'}")

# 7. Autonomy deliverable
deliverables["autonomy"] = {
    "scheduler_tasks": len(sched_tasks.get("tasks", [])),
    "kairos_running": kairos.get("running", False),
    "dream_cycles": dream_stats.get("cycles", 0),
    "corrections": autodream.get("corrections", 0),
}
print("\n7. AUTONOMY:")
print(f"   Scheduler: {deliverables['autonomy']['scheduler_tasks']} tasks")
print(f"   KAIROS: {'running' if deliverables['autonomy']['kairos_running'] else 'stopped'}")
print(f"   Dreams: {deliverables['autonomy']['dream_cycles']} cycles")
print(f"   AutoDream corrections: {deliverables['autonomy']['corrections']}")

# 8. Soul deliverable
deliverables["soul"] = {
    "identity": f"{soul.get('identity', {}).get('name')} / {soul.get('identity', {}).get('role')}",
    "goals": soul.get("agenda", {}).get("goals", []),
    "sessions": pulse.get("sessions", 0),
}
print("\n8. SOUL IDENTITY:")
print(f"   Identity: {deliverables['soul']['identity']}")
print(f"   Goals: {deliverables['soul']['goals'][:3]}")
print(f"   Total sessions: {deliverables['soul']['sessions']}")

# 9. News deliverable
deliverables["news"] = {
    "total_items": len(news_items),
    "sources": list(set(i.get("source", "?") for i in news_items)),
    "categories": {k: len(v) for k, v in cats.items()},
}
print("\n9. NEWS & INTEL:")
print(f"   Items: {deliverables['news']['total_items']}")
print(f"   Sources: {deliverables['news']['sources']}")
print(f"   Categories: {deliverables['news']['categories']}")

# 10. Systems deliverable
deliverables["systems"] = {
    "agents": len(agents),
    "routes_tracked": len(routes),
    "feed_events": len(feed_events),
    "event_types": event_types,
}
print("\n10. SYSTEMS:")
print(f"   Agents: {deliverables['systems']['agents']}")
print(f"   Tracked routes: {deliverables['systems']['routes_tracked']}")
print(f"   Feed events: {deliverables['systems']['feed_events']}")
print(f"   Event types: {deliverables['systems']['event_types']}")

# ═══════════════════════════════════════════════════════════════════════
# SCORECARD
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("SCORECARD")
print("=" * 70)

scores = {}
all_ok = sum(1 for v in RESULTS.values() if v["ok"])
total = len(RESULTS)
scores["endpoints"] = {"pass": all_ok, "total": total, "pct": round(all_ok/total*100, 1)}
print(f"\nAPI Endpoints: {all_ok}/{total} ({scores['endpoints']['pct']}%) pass")

# Per-category scoring
categories = {
    "Health": ["Health check", "Integrations status", "LLM Status"],
    "Reasoning": [f"Reason: {q[:50]}..." for q, _ in queries],
    "Execution": [f"Execute: {t[:50]}..." for t in exec_tasks],
    "Skills": ["Skills list", "Bundles list", "Chains list", "Forge validate"],
    "Dialogue": [f"Dialogue: {m}" for m, _ in dialogues],
    "Systems": ["Systems registry", "Systems health", "Route stats", "Dashboard feed"],
    "News": ["News feed", "News unified", "Opportunities"],
    "Settings": ["Templates list", "Settings keys"],
    "Engine": ["Engine state", "Engine process", "Engine events"],
}

print("\nPer-Category:")
for cat, endpoints in categories.items():
    endpoints = [e for e in endpoints if e]  # Remove empty
    cat_ok = sum(1 for e in endpoints if RESULTS.get(e, {}).get("ok"))
    cat_total = len(endpoints)
    pct = round(cat_ok/cat_total*100, 1) if cat_total else 0
    bar = "█" * int(pct/10) + "░" * (10 - int(pct/10))
    print(f"  {cat:<12} {bar} {pct}% ({cat_ok}/{cat_total})")

# ═══════════════════════════════════════════════════════════════════════
# GAPS & FAILURES
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("FAILURES & GAPS")
print("=" * 70)

failures = [(name, v) for name, v in RESULTS.items() if not v["ok"]]
if failures:
    for name, v in failures:
        err = v["result"].get("_error", str(v["result"])[:100])
        print(f"  FAIL [{v['code']}] {name}: {err}")
else:
    print("  No failures detected!")

# Time analysis
times = [(name, v["ms"]) for name, v in RESULTS.items()]
slow = [t for t in times if t[1] > 1000]
if slow:
    print(f"\n  SLOW ENDPOINTS (>1s):")
    for name, ms in sorted(slow, key=lambda x: -x[1]):
        print(f"    {ms}ms — {name}")

print(f"\n  FASTEST: {min(times, key=lambda x: x[1])[0]} ({min(times, key=lambda x: x[1])[1]}ms)")
print(f"  SLOWEST: {max(times, key=lambda x: x[1])[0]} ({max(times, key=lambda x: x[1])[1]}ms)")
print(f"  MEDIAN:  {sorted(times, key=lambda x: x[1])[len(times)//2][1]}ms")

# ═══════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

# Count deliverables
deliv_count = sum(
    len(v) if isinstance(v, list) else 1
    for v in deliverables.values()
)
print(f"\nTotal benchmark endpoints tested: {total}")
print(f"Total passing: {all_ok}")
print(f"System-wide pass rate: {scores['endpoints']['pct']}%")
print(f"Deliverables produced: {len(deliverables)}")

# Write detailed report
report_path = "benchmark_results.json"
with open(report_path, "w") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {"total": total, "pass": all_ok, "pct": scores["endpoints"]["pct"]},
        "categories": {cat: {"pass": sum(1 for e in endpoints if RESULTS.get(e, {}).get("ok")), "total": len(endpoints)}
                       for cat, endpoints in categories.items()},
        "results": {k: {"code": v["code"], "ok": v["ok"], "ms": v["ms"]} for k, v in RESULTS.items()},
        "deliverables": {},
        "failures": [{"name": n, "code": v["code"]} for n, v in failures],
        "slow": [{"name": n, "ms": m} for n, m in slow],
    }, f, indent=2, default=str)

print(f"\nFull report saved to {report_path}")
print("=" * 70)
