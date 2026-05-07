"""Battle engine — deterministic, reproducible pet battles."""
from __future__ import annotations
import random
import hashlib
from math import floor
from typing import Dict, List, Optional, Tuple

from .models import DevPet, BattleStats
from .stats import get_available_skills


def battle(pet_a: DevPet, pet_b: DevPet, match_id: str) -> Dict:
    """
    Deterministic battle between two DevPets.
    Same inputs + match_id always produce identical output.
    """
    # 1. Generate deterministic seed using SHA-256 (not built-in hash())
    seed_input = (pet_a.developer_id + pet_b.developer_id + match_id).encode()
    battle_seed = int(hashlib.sha256(seed_input).hexdigest()[:8], 16)
    rng = random.Random(battle_seed)

    # 2. HP calculation — track in dict keyed by pet_name to avoid stale copies
    hp = {
        pet_a.pet_name: pet_a.battle_stats.resilience * 10,
        pet_b.pet_name: pet_b.battle_stats.resilience * 10,
    }
    init_hp = dict(hp)

    # 3. Determine initiative (velocity-based)
    stats_a = pet_a.battle_stats
    stats_b = pet_b.battle_stats

    if stats_a.velocity > stats_b.velocity:
        attacker, defender = pet_a, pet_b
    elif stats_b.velocity > stats_a.velocity:
        attacker, defender = pet_b, pet_a
    else:
        # Coin flip for tie
        if rng.random() > 0.5:
            attacker, defender = pet_a, pet_b
        else:
            attacker, defender = pet_b, pet_a

    # 4. Turn loop
    turns = []
    turn_count = 0
    max_turns = 50

    while hp[attacker.pet_name] > 0 and hp[defender.pet_name] > 0 and turn_count < max_turns:
        turn_count += 1

        # Select skill: 80% highest power, 20% random
        available = get_available_skills(attacker, turns)
        if available:
            if rng.random() < 0.8:
                skill = max(available, key=lambda s: s["power"])
            else:
                skill = rng.choice(available)
        else:
            skill = None

        if skill:
            # Damage formula
            base_damage = skill["power"] + floor(attacker.battle_stats.velocity * 0.5)
            mitigation = floor(defender.battle_stats.precision * 0.2)
            damage = max(1, base_damage - mitigation)

            # Critical hit: ingenuity check
            crit_chance = min(0.5, attacker.battle_stats.ingenuity / 100)
            is_crit = rng.random() < crit_chance
            if is_crit:
                damage = floor(damage * 1.5)

            hp[defender.pet_name] -= damage

            # Generate insight
            insight = generate_insight(attacker, skill, is_crit, damage)

            # HP percent relative to both pets' current HP
            total_hp = hp[attacker.pet_name] + hp[defender.pet_name] + 0.001
            defender_hp_pct = max(0, int(hp[defender.pet_name] / total_hp * 100))

            turns.append({
                "turn": turn_count,
                "attacker": attacker.pet_name,
                "defender": defender.pet_name,
                "skill": skill["name"],
                "skill_branch": skill["branch"],
                "tier": skill["tier"],
                "tier_score": skill["tier_score"],
                "damage": damage,
                "critical": is_crit,
                "defender_hp_remaining": max(0, hp[defender.pet_name]),
                "defender_hp_percent": defender_hp_pct,
                "insight": insight,
            })
        else:
            total_hp = hp[attacker.pet_name] + hp[defender.pet_name] + 0.001
            defender_hp_pct = int(hp[defender.pet_name] / total_hp * 100)

            turns.append({
                "turn": turn_count,
                "attacker": attacker.pet_name,
                "defender": defender.pet_name,
                "skill": "Pass (no skills available)",
                "damage": 0,
                "critical": False,
                "defender_hp_remaining": hp[defender.pet_name],
                "defender_hp_percent": defender_hp_pct,
                "insight": f"{attacker.pet_name} hesitates — limited tool diversity.",
            })

        # Swap roles (no HP swap needed since we index by pet_name)
        attacker, defender = defender, attacker

    # 5. Determine winner using actual tracked HP
    hp_a_final = hp[pet_a.pet_name]
    hp_b_final = hp[pet_b.pet_name]

    if hp_a_final > hp_b_final:
        winner = pet_a.pet_name
        loser = pet_b.pet_name
    elif hp_b_final > hp_a_final:
        winner = pet_b.pet_name
        loser = pet_a.pet_name
    else:
        winner = "Draw"
        loser = None

    return {
        "match_id": match_id,
        "battle_seed": battle_seed,
        "pet_a": pet_a.pet_name,
        "pet_b": pet_b.pet_name,
        "winner": winner,
        "loser": loser,
        "turns": turns,
        "total_turns": turn_count,
        "final_hp_a": max(0, hp_a_final),
        "final_hp_b": max(0, hp_b_final),
        "final_hp_a_percent": int(hp_a_final / init_hp[pet_a.pet_name] * 100) if init_hp[pet_a.pet_name] > 0 else 0,
        "final_hp_b_percent": int(hp_b_final / init_hp[pet_b.pet_name] * 100) if init_hp[pet_b.pet_name] > 0 else 0,
        "skill_showcase": extract_skill_showcase(turns),
    }


def generate_insight(pet: DevPet, skill: Dict, is_crit: bool, damage: int) -> str:
    """Generate human-readable insight about developer capabilities."""
    stats = pet.battle_stats
    branch = pet.tool_branches.get(skill["branch"], None)
    insights = []

    # Tier insight
    if skill.get("tier_score", 0) >= 4:
        insights.append(f"Master-tier {skill['branch']} — deep expertise.")
    elif skill.get("tier_score", 0) <= 1:
        insights.append(f"Novice {skill['branch']} — still learning.")

    # Stat insights
    if stats.velocity >= 15:
        insights.append(f"High velocity ({stats.velocity}) — ships fast.")
    if stats.precision >= 15:
        insights.append(f"Precision ({stats.precision}) — reliable code.")
    if is_crit:
        insights.append(f"Critical! Ingenuity ({stats.ingenuity}) — creative solutions.")

    # Work fingerprint insight
    wf = pet.work_fingerprint
    if wf.ci_pass_rate > 0.9:
        insights.append(f"CI pass: {wf.ci_pass_rate*100:.0f}% — solid testing.")
    if len(wf.environments) > 2:
        insights.append(f"Multi-env: {', '.join(wf.environments[:3])}.")

    return " ".join(insights[:2])  # Max 2 insights


def extract_skill_showcase(turns: list) -> Dict[str, List[str]]:
    """Extract unique skills used in battle for each pet."""
    showcase = {}
    for turn in turns:
        name = turn.get("attacker")
        skill = turn.get("skill")
        if name and skill and skill != "Pass (no skills available)":
            if name not in showcase:
                showcase[name] = []
            if skill not in showcase[name]:
                showcase[name].append(skill)
    return showcase


def simulate_battle_log(pet_a: DevPet, pet_b: DevPet, match_id: str) -> str:
    """Generate a human-readable battle log."""
    result = battle(pet_a, pet_b, match_id)
    lines = [
        f"=== BATTLE: {result['pet_a']} vs {result['pet_b']} ===",
        f"Match ID: {result['match_id']}",
        f"Seed: {result['battle_seed']}",
        "",
    ]
    for turn in result["turns"]:
        crit = " **CRIT!**" if turn["critical"] else ""
        lines.append(
            f"Turn {turn['turn']}: {turn['attacker']} uses {turn['skill']}"
            f" → {turn['damage']} dmg{crit}"
        )
        if turn.get("insight"):
            lines.append(f"  💡 {turn['insight']}")
    lines.append("")
    lines.append(f"WINNER: {result['winner']}!")
    return "\n".join(lines)

