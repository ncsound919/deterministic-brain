import requests
BASE = "http://localhost:8000"

queries = [
    ("use the web artifacts builder skill", "web artifacts"),
    ("generate a canvas design", "canvas design"),
    ("build a frontend design for a pokemon arena", "frontend design"),
    ("scaffold rest api for devpets", "scaffold rest"),
    ("design a battle website interface", "design website"),
    ("create a jupyter notebook about devpets", "jupyter"),
]

print("Targeted skill matching test:")
for query, label in queries:
    r = requests.post(f"{BASE}/reason", json={"query": query}, timeout=20)
    d = r.json()["decision"]
    print(f"  {d['chosen_skill'][:30]:30s} conf={d['confidence']:.4f}  [{label}]")
