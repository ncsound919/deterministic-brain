"""Apply healing based on benchmark findings."""
import json
import sys
sys.path.insert(0, ".")
from evolution.skill_evolver import SkillEvolver

report = json.loads(open(".benchmark_report.json").read())
evolver = SkillEvolver()

# Track all reasoning queries
for query, data in report.get("reasoning", {}).items():
    confidence = data.get("confidence", 0)
    skill = data.get("chosen_skill", "unknown")
    ms = data.get("ms", 0)
    success = confidence > 0.3
    evolver.track(skill, success, latency_ms=min(ms, 5000), confidence=confidence)

# Evolve weights
evolved = evolver.evolve()
print(f"Skills evolved: {len(evolved)}")
for e in evolved:
    print(f"  {e['skill_id']}: {e['old_weight']:.3f} -> {e['new_weight']:.3f} (sr: {e['success_rate']:.3f})")

# Show ranking
stats = evolver.all_stats()
print(f"\nSkill performance ranking ({len(stats)} tracked):")
for s in stats[:10]:
    print(f"  {s['skill_id'][:35]:35s} runs:{s['runs']:3d} sr:{s['success_rate']:.3f} w:{s['weight']:.3f}")

# Deprecate zero-confidence skills that ran 5+ times
deprecations = 0
for query, data in report.get("reasoning", {}).items():
    skill = data.get("chosen_skill", "")
    if data.get("confidence", 0) == 0.0:
        s = evolver.get_stats(skill)
        if s and s["runs"] >= 3:
            evolver.deprecate(skill)
            deprecations += 1
            print(f"  DEPRECATED: {skill} (0.0 confidence across {s['runs']} runs)")

print(f"\nDeprecated: {deprecations} skills")
print("Report: .skill_performance.json")
print("Weights: .skill_weights.json")
