"""
Full end-to-end test suite — runs entirely in-process, no HTTP server needed.
Usage: python test_full.py
"""
import sys
import os
import traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0

def check(label: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}" + (f" — {detail}" if detail else ""))

def section(title: str):
    print(f"\n=== {title} ===")

# ── 1. Imports ──────────────────────────────────────────────────────
section("IMPORTS")
try:
    from orchestration.dca_engine import DeterministicCodingAgent
    from orchestration.skill_registry import get_skill_registry
    from brain.router import MoERouter
    from brain.task_parser import TaskParser
    from reasoning.math_engine import ReasoningEngine
    check("Core imports", True)
except Exception as e:
    check("Core imports", False, str(e))
    traceback.print_exc()
    sys.exit(1)

try:
    from knowledge.bank import get_knowledge_bank
    from knowledge.ingester import KnowledgeIngester
    from knowledge.fragment import KnowledgeFragment
    check("Knowledge bank imports", True)
except Exception as e:
    check("Knowledge bank imports", False, str(e))

# ── 2. Registry ─────────────────────────────────────────────────────
section("SKILL REGISTRY")
try:
    sr = get_skill_registry("skill_packs")
    sr.discover()
    all_skills = sr.list_all()
    check("Discovery runs", len(all_skills) > 0, f"found {len(all_skills)}")
    print(f"    Skills discovered: {len(all_skills)}")
    react_skill = sr.get("react")
    check("'react' skill in registry", react_skill is not None)
    api_skill = sr.get("rest_api") or sr.get("rest-api")
    check("rest_api or rest-api in registry", api_skill is not None)
except Exception as e:
    check("Registry", False, str(e))
    traceback.print_exc()

# ── 3. Router ────────────────────────────────────────────────────────
section("ROUTER")
try:
    router = MoERouter("swarm.yaml")
    candidates = router.enriched_candidates()
    check("enriched_candidates returns list", len(candidates) > 0)
    print(f"    Route candidates: {len(candidates)}")
    ids = [sid for sid, _ in candidates]
    check("create-react-component in routes", "create-react-component" in ids, str(ids[:5]))
except Exception as e:
    check("Router", False, str(e))
    traceback.print_exc()

# ── 4. Reasoner ──────────────────────────────────────────────────────
section("REASONER")
try:
    parser = TaskParser()
    reasoner = ReasoningEngine()
    router2 = MoERouter("swarm.yaml")
    enriched = router2.enriched_candidates()
    enriched_texts = [t for _, t in enriched]
    task = parser.parse("create a react component named PetCard")
    decision = reasoner.decide(
        task=task,
        skill_candidates=enriched_texts,
        scorer_fn=lambda c: 0.6 if "react" in str(c).lower() else 0.0,
        constraints=[],
        variable_domains={"lang": ["python","typescript"], "async": [True,False], "size": ["tiny","small","medium"]},
    )
    check("Reasoner returns decision", decision is not None)
    check("Confidence > 0", decision.confidence > 0, f"conf={decision.confidence}")
    check("Audit ok", decision.audit_ok, str(decision.pre_audit))
    print(f"    Chosen: {decision.chosen_skill}  Conf: {decision.confidence:.4f}")
except Exception as e:
    check("Reasoner", False, str(e))
    traceback.print_exc()

# ── 5. DCA handle() ─────────────────────────────────────────────────
section("DCA HANDLE")
queries = [
    ("React component",      "create a react component named PetCard"),
    ("REST API scaffold",    "scaffold a REST API for User with auth"),
    ("Canvas web build",     "build a canvas battle website"),
    ("Shorthand parse",      "build:web[canvas,battle:turnbased,lang:typescript]"),
]
agent = None
try:
    agent = DeterministicCodingAgent()
    check("Agent initialized", True)
except Exception as e:
    check("Agent initialized", False, str(e))
    traceback.print_exc()

if agent:
    for label, query in queries:
        try:
            result = agent.handle(query)
            status = result.get("status", "?")
            skill  = result.get("reasoning", {}).get("chosen_skill", "?")
            conf   = result.get("reasoning", {}).get("confidence", 0)
            fo     = result.get("final_output", {})
            ok     = status in ("ok", "low_confidence")  # both are valid non-crash states
            check(label, ok, f"status={status} skill={skill} conf={conf:.3f}")
            print(f"    status={status}  skill={skill}  conf={conf:.4f}")
            if status == "failed":
                print(f"    error: {fo.get('error', '?')}")
            if status == "ok" and fo.get("artifacts"):
                print(f"    artifacts: {len(fo['artifacts'])}")
        except Exception as e:
            check(label, False, str(e))
            traceback.print_exc()

# ── 6. Knowledge Bank ────────────────────────────────────────────────
section("KNOWLEDGE BANK")
try:
    kb = get_knowledge_bank()
    ingester = KnowledgeIngester()
    check("KB init", kb is not None)

    # Ingest text
    frags = ingester.ingest_text(
        "Stripe webhooks send POST requests when events happen. Verify with Stripe-Signature header.",
        "Stripe Webhooks", ["stripe", "payments"]
    )
    for f in frags:
        kb.add(f)
    kb.rebuild_index()
    check("Ingest text (stripe)", len(frags) > 0, f"got {len(frags)}")

    frags2 = ingester.ingest_text(
        "React hooks: useState for state, useEffect for side effects, useContext for context.",
        "React Hooks", ["react", "frontend"]
    )
    for f in frags2:
        kb.add(f)
    kb.rebuild_index()
    check("Ingest text (react)", len(frags2) > 0)

    # Search
    results_stripe = kb.query("stripe webhook payments", top_k=3)
    check("Search returns results", len(results_stripe) > 0, f"got {len(results_stripe)}")
    if results_stripe:
        top_frag, top_score = results_stripe[0]
        check("Top stripe result relevant", "stripe" in top_frag.source_title.lower() or
              "stripe" in top_frag.chunk_text.lower(),
              f"top={top_frag.source_title}")
        print(f"    stripe search top: {top_frag.source_title} score={top_score:.4f}")

    results_react = kb.query("react hooks state", top_k=3)
    if results_react:
        top2_frag, top2_score = results_react[0]
        check("Top react result relevant", "react" in top2_frag.source_title.lower() or
              "react" in top2_frag.chunk_text.lower(),
              f"top={top2_frag.source_title}")
        print(f"    react search top: {top2_frag.source_title} score={top2_score:.4f}")

    # Stats
    stats = kb.stats()
    check("Stats returns dict", isinstance(stats, dict))
    print(f"    fragments={stats.get('total_fragments')} snippets={stats.get('snippets')} index={stats.get('index_loaded')}")

    # Snippet save
    snippet = KnowledgeFragment(
        id="test-snippet-001",
        source_type="snippet",
        source_url="snippet://test",
        source_title="Test Snippet",
        chunk_text="stripe.Webhook.construct_event(payload, sig, secret)",
        tags=["stripe", "python"],
        build_relevance=[],
    )
    kb.add_snippet(snippet)
    snippets = kb.list_snippets()
    check("Snippet saved and listed", len(snippets) > 0)
    print(f"    snippets in bank: {len(snippets)}")

except Exception as e:
    check("Knowledge bank", False, str(e))
    traceback.print_exc()

# ── 7. Summary ───────────────────────────────────────────────────────
total = PASS + FAIL
print(f"\n{'='*40}")
print(f"Results: {PASS}/{total} passed  ({FAIL} failed)")
if FAIL == 0:
    print("ALL TESTS PASSED ✓")
else:
    print(f"{FAIL} TESTS FAILED — see output above")
print("="*40)
sys.exit(0 if FAIL == 0 else 1)
