"""Build the skill embedding index from enriched candidates.

Run once after adding new skills. Generates:
  - skill_index.npy   (~130KB, 384-dim float32 matrix)
  - skill_index_ids.json   (skill_id list matching row order)
"""

import sys
sys.path.insert(0, ".")

from brain.router import MoERouter
from reasoning.semantic_ranker import FlatEmbeddingIndex

print("Loading router and enriched candidates...")
router = MoERouter("swarm.yaml")
enriched = router.enriched_candidates()
print(f"  {len(enriched)} enriched candidates")

print("Building embedding index with MiniLM-L6 (first run downloads ~22MB model)...")
index = FlatEmbeddingIndex("all-MiniLM-L6-v2")
index.build(enriched, "skill_index.npy")
print(f"  Index built: {index.matrix.shape}")
print("  Saved: skill_index.npy + skill_index_ids.json")

# Quick test
results = index.query("build a devpet battle website with canvas", top_k=3)
print("\nTest query: 'build a devpet battle website with canvas'")
for sid, score in results:
    print(f"  {sid:40s} {score:.4f}")

results2 = index.query("deploy my web app to production", top_k=3)
print("\nTest query: 'deploy my web app to production'")
for sid, score in results2:
    print(f"  {sid:40s} {score:.4f}")
