"""Test what actually produces output in the brain."""
import requests

BASE = "http://localhost:8000"

# Test 1: Forge diff (always works)
print("--- Forge diff ---")
r = requests.post(f"{BASE}/forge/diff", json={"old": "hello world", "new": "hello brain", "filename": "test.txt"}, timeout=10)
d = r.json()
diff_lines = len(d.get("diff", "").splitlines()) if "diff" in d else 0
print(f"  Status: {r.status_code}  Diff lines: {diff_lines}")

# Test 2: Skills
r = requests.get(f"{BASE}/skills", timeout=10)
skills = r.json()["skills"]
exec_skills = [s for s in skills if s.get("mc") or "lane" in str(s.get("path", ""))]
print(f"\n--- Skills: {len(skills)} total, {len(exec_skills)} executable ---")
for s in exec_skills[:10]:
    print(f"  {s.get('skill','?'):30s} path={s.get('path','?')}")

# Test 3: Bundle execution
print("\n--- Bundle: audit-repo ---")
r = requests.post(f"{BASE}/bundle", json={"bundle": "audit-repo", "inputs": {"repo_path": "."}}, timeout=30)
b = r.json()
for lane, result in b.get("results", {}).items():
    status = result.get("status", "?")
    print(f"  {lane}: {status}")
    fo = result.get("final_output", {})
    if isinstance(fo, dict):
        output_keys = list(fo.keys())
        print(f"    Output keys: {output_keys}")
        for k in output_keys[:3]:
            val = str(fo.get(k, ""))[:120]
            print(f"    {k}: {val}")

# Test 4: Task execution with matching skill
print("\n--- Task: create react component ---")
r = requests.post(f"{BASE}/task", json={"query": "create a react component named BattleCard"}, timeout=30)
t = r.json()
print(f"  Status: {t.get('status')}")
print(f"  Score: {t.get('score')}")
print(f"  Confidence: {t.get('reasoning',{}).get('confidence',0):.4f}")
