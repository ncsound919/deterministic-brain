"""Stat calculation for DevPet — deterministic formulas."""
from __future__ import annotations
from math import floor
from .models import DevPet, BattleStats


def calculate_stats(pet: DevPet) -> BattleStats:
    """Calculate the six battle stats from work fingerprint and tool branches."""
    wf = pet.work_fingerprint
    branches = pet.tool_branches

    # Velocity: speed of task completion
    avg_sec = wf.avg_task_completion_seconds or 1  # avoid div by zero
    velocity = floor(min(60, 60 / avg_sec * 100)) + floor(wf.session_count / 50)

    # Precision: low error/rework rate
    total_builds = sum(b.events.get("ci_fail", 0) + b.events.get("ci_pass", 0)
                       for b in branches.values()) or 1
    failed = sum(b.events.get("ci_fail", 0) for b in branches.values())
    precision = floor(wf.ci_pass_rate * 20) + floor((1 - failed / total_builds) * 10)

    # Breadth: number of tool branches mastered
    breadth = wf.tools_used_distinct * 2 + len(wf.environments) * 1

    # Depth: highest tier in any single branch
    max_tier = max((b.tier_score for b in branches.values()), default=1)
    max_xp = max((b.xp for b in branches.values()), default=0)
    depth = max_tier * 3 + floor(max_xp / 1000)

    # Resilience: recovery from failures, debug speed
    total_failed = sum(b.events.get("ci_fail", 0) for b in branches.values()) or 1
    recovered = sum(b.events.get("ci_pass", 0) for b in branches.values())  # Simplified
    resilience = floor(recovered / total_failed * 15) + floor(wf.session_count / 100)

    # Ingenuity: novel solutions, tool combinations
    ingenuity = len(wf.problem_patterns) * 4 + len(wf.languages) * 2

    # Clamp all stats to 1-30 range
    clamp = lambda x: max(1, min(30, x))
    return BattleStats(
        velocity=clamp(velocity),
        precision=clamp(precision),
        breadth=clamp(breadth),
        depth=clamp(depth),
        resilience=clamp(resilience),
        ingenuity=clamp(ingenuity),
    )


def calculate_pet_level(pet: DevPet) -> tuple[int, int]:
    """Calculate pet level and evolution stage from total XP."""
    total_xp = sum(b.xp for b in pet.tool_branches.values())

    # Level thresholds
    level_thresholds = [
        0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500,
        5500, 6600, 7800, 9100, 10500, 12000, 13600, 15300, 17100, 19000,
    ]

    level = 1
    for i, threshold in enumerate(level_thresholds):
        if total_xp >= threshold:
            level = i + 1
        else:
            break

    # Evolution stage: changes form every 10 levels (max stage 4)
    evolution_stage = min(4, (level - 1) // 10 + 1)

    return level, evolution_stage


def get_available_skills(pet: DevPet, turn_history: list) -> list:
    """Get available skills for battle, respecting cooldowns."""
    skills = []
    for branch_name, branch in pet.tool_branches.items():
        for move_name in branch.signature_moves:
            # Cooldown check
            cooldown = 6 - branch.tier_score  # Master=2, Legend=1
            last_used = 0
            for t in reversed(turn_history):
                if t.get("skill") == move_name:
                    last_used = t.get("turn", 0)
                    break
            if len(turn_history) - last_used >= cooldown:
                # Power = base + depth bonus + branch xp modifier
                base_power = 10
                depth_bonus = pet.battle_stats.depth * 0.5
                xp_modifier = branch.xp / 1000
                power = floor(base_power + depth_bonus + xp_modifier)
                skills.append({
                    "name": move_name,
                    "branch": branch_name,
                    "tier": branch.tier.display_name,
                    "tier_score": branch.tier_score,
                    "power": power,
                    "cooldown": cooldown,
                })
    return skills
