"""Test the brain building the devpet battle website end-to-end."""
import requests
import json
import time

BASE = "http://localhost:8000"

QUERY = (
    "build a devpet battle website with two pet selectors, "
    "HTML5 canvas pet rendering based on JSON traits, "
    "deterministic turn-based battle with hit points and turn log"
)

print(f"Query: {QUERY}\n")
print("=" * 60)

# Step 1: Reason
print("\n--- STEP 1: REASON ---")
t0 = time.time()
r = requests.post(f"{BASE}/reason", json={"query": QUERY}, timeout=30)
ms = (time.time() - t0) * 1000
d = r.json()["decision"]
print(f"  Chosen: {d['chosen_skill']}")
print(f"  Confidence: {d['confidence']:.4f}")
print(f"  Audit OK: {d['audit_ok']}")
print(f"  Time: {ms:.0f}ms")
print("  Breakdown:")
for step in d.get("breakdown", []):
    print(f"    [{step['step']}] { {k:v for k,v in step.items() if k!='step'} }")

# Step 2: Execute
print("\n--- STEP 2: EXECUTE ---")
t0 = time.time()
r = requests.post(f"{BASE}/task", json={"query": QUERY}, timeout=60)
ms = (time.time() - t0) * 1000
result = r.json()
print(f"  Status: {result.get('status')}")
print(f"  Score: {result.get('score')}")
print(f"  Session: {result.get('session_id')}")
print(f"  Confidence: {result.get('reasoning',{}).get('confidence', 0):.4f}")
print(f"  Time: {ms:.0f}ms")

# Step 3: Check output
output = result.get("final_output", {})
if isinstance(output, dict):
    print(f"\n  Output keys: {list(output.keys())}")
    if "error" in output:
        print(f"  Error: {output['error'][:200]}")
    if "raw" in output:
        print(f"  Raw result: {str(output['raw'])[:300]}")
    if "files" in output:
        print(f"  Files: {list(output['files'].keys())}")
    # Try to find generated HTML/JS
    result_str = json.dumps(result)
    html_count = result_str.count(".html") + result_str.count("index.html")
    js_count = result_str.count(".js") + result_str.count("battle.js")
    canvas_count = result_str.lower().count("canvas")
    print(f"\n  HTML references: {html_count}")
    print(f"  JS references: {js_count}")
    print(f"  Canvas references: {canvas_count}")

# Step 4: Try alternative query for frontend-design skill
print("\n--- STEP 4: ALTERNATIVE (frontend-design) ---")
r2 = requests.post(f"{BASE}/reason", json={
    "query": "design a beautiful website interface with canvas graphics and battle animations"
}, timeout=30)
d2 = r2.json()["decision"]
print(f"  Chosen: {d2['chosen_skill']}")
print(f"  Confidence: {d2['confidence']:.4f}")

# Step 5: Try web artifacts builder
print("\n--- STEP 5: ALTERNATIVE (web-artifacts-builder) ---")
r3 = requests.post(f"{BASE}/reason", json={
    "query": "build a web application with interactive components and JavaScript"
}, timeout=30)
d3 = r3.json()["decision"]
print(f"  Chosen: {d3['chosen_skill']}")
print(f"  Confidence: {d3['confidence']:.4f}")

# Step 6: Bundle dispatch
print("\n--- STEP 6: BUNDLE (scaffold-rest-api) ---")
r4 = requests.post(f"{BASE}/bundle", json={
    "bundle": "scaffold-rest-api",
    "inputs": {"resource": "DevPet"}
}, timeout=30)
b = r4.json()
print(f"  Bundle: {b.get('bundle')}")
print(f"  Results: {list(b.get('results',{}).keys())}")

print("\n" + "=" * 60)
print("Test complete.")
