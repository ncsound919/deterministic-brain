// devpet-web/js/battle.js
// Deterministic battle engine (ported from Python)

const TierScores = {
    'Novice': 1,
    'Practitioner': 2,
    'Expert': 3,
    'Master': 4,
    'Legend': 5,
};

const TierCD = {
    'Novice': 6,
    'Practitioner': 5,
    'Expert': 4,
    'Master': 3,
    'Legend': 2,
};

function cyrb53(str, seed = 0) {
    let h1 = 0xdeadbeef ^ seed, h2 = 0x41c6ce57 ^ seed;
    for (let i = 0, ch; i < str.length; i++) {
        ch = str.charCodeAt(i);
        h1 = Math.imul(h1 ^ ch, 2654435761);
        h2 = Math.imul(h2 ^ ch, 1597334677);
    }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
    h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
    h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
    h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return [h2 >>> 0, h1 >>> 0];
}

function simpleRNG(seed) {
    let s = seed;
    return function() {
        s = (s * 1664525 + 1013904223) & 0xffffffff;
        return (s >>> 0) / 0xffffffff;
    };
}

function battle(petA, petB, matchId) {
    const seedInput = petA.identity.developer_id + petB.identity.developer_id + matchId;
    const seedHash = cyrb53(seedInput);
    // Fix: cyrb53 returns [h2, h1], use first element as seed
    const battleSeed = seedHash[0];
    const rng = simpleRNG(battleSeed);

    const statsA = petA.battle_stats;
    const statsB = petB.battle_stats;

    // Fix: Track HP in dict keyed by pet name (like Python fix)
    const hp = {
        [petA.pet_name]: statsA.resilience * 10,
        [petB.pet_name]: statsB.resilience * 10,
    };
    const initHp = { ...hp };

    let attacker, defender;
    if (statsA.velocity > statsB.velocity) {
        attacker = petA; defender = petB;
    } else if (statsB.velocity > statsA.velocity) {
        attacker = petB; defender = petA;
    } else {
        if (rng() > 0.5) {
            attacker = petA; defender = petB;
        } else {
            attacker = petB; defender = petA;
        }
    }

    const turns = [];
    let turnCount = 0;
    const maxTurns = 50;

    while (hp[attacker.pet_name] > 0 && hp[defender.pet_name] > 0 && turnCount < maxTurns) {
        turnCount++;
        const available = getAvailableSkills(attacker, turns);
        let skill = null;

        if (available.length > 0) {
            if (rng() < 0.8) {
                skill = available.reduce((max, s) => s.power > max.power ? s : max);
            } else {
                skill = available[Math.floor(rng() * available.length)];
            }
        }

        if (skill) {
            const baseDamage = skill.power + Math.floor(attacker.battle_stats.velocity * 0.5);
            const mitigation = Math.floor(defender.battle_stats.precision * 0.2);
            let damage = Math.max(1, baseDamage - mitigation);

            const critChance = Math.min(0.5, attacker.battle_stats.ingenuity / 100);
            const isCrit = rng() < critChance;
            if (isCrit) {
                damage = Math.floor(damage * 1.5);
            }

            hp[defender.pet_name] -= damage;

            const insight = generateInsight(attacker, skill, isCrit, damage);
            const totalHp = hp[attacker.pet_name] + hp[defender.pet_name] + 0.001;
            const hpDefPercent = Math.max(0, Math.floor(hp[defender.pet_name] / totalHp * 100));

            turns.push({
                turn: turnCount,
                attacker: attacker.pet_name,
                defender: defender.pet_name,
                skill: skill.name,
                skill_branch: skill.branch,
                tier: skill.tier,
                tier_score: skill.tier_score,
                damage: damage,
                critical: isCrit,
                defender_hp_remaining: Math.max(0, hp[defender.pet_name]),
                defender_hp_percent: hpDefPercent,
                insight: insight,
            });
        } else {
            const totalHp = hp[attacker.pet_name] + hp[defender.pet_name] + 0.001;
            const hpDefPercent = Math.floor(hp[defender.pet_name] / totalHp * 100);

            turns.push({
                turn: turnCount,
                attacker: attacker.pet_name,
                defender: defender.pet_name,
                skill: "Pass (no skills available)",
                damage: 0,
                critical: false,
                defender_hp_remaining: hp[defender.pet_name],
                defender_hp_percent: hpDefPercent,
                insight: `${attacker.pet_name} hesitates — limited tool diversity.`,
            });
        }

        // Swap roles (no HP swap needed since we index by pet_name)
        attacker, defender = [defender, attacker];
    }

    // Determine winner using actual tracked HP
    const hpAFinal = hp[petA.pet_name];
    const hpBFinal = hp[petB.pet_name];

    let winner, loser;
    if (hpAFinal > hpBFinal) {
        winner = petA.pet_name; loser = petB.pet_name;
    } else if (hpBFinal > hpAFinal) {
        winner = petB.pet_name; loser = petA.pet_name;
    } else {
        winner = "Draw"; loser = null;
    }

    return {
        match_id: matchId,
        battle_seed: battleSeed,
        pet_a: petA.pet_name,
        pet_b: petB.pet_name,
        winner: winner,
        loser: loser,
        turns: turns,
        total_turns: turnCount,
        final_hp_a: Math.max(0, hpAFinal),
        final_hp_b: Math.max(0, hpBFinal),
        final_hp_a_percent: Math.floor(hpAFinal / initHp[petA.pet_name] * 100) || 0,
        final_hp_b_percent: Math.floor(hpBFinal / initHp[petB.pet_name] * 100) || 0,
        skill_showcase: extractSkillShowcase(turns),
    };
}

function getAvailableSkills(pet, turnHistory) {
    const skills = [];
    const branches = pet.tool_branches || {};

    for (const [branchName, branch] of Object.entries(branches)) {
        const tier = branch.tier || 'Novice';
        const tierScore = TierScores[tier] || 1;
        const cooldown = 6 - tierScore;

        for (const moveName of (branch.signature_moves || [])) {
            let lastUsed = 0;
            for (let i = turnHistory.length - 1; i >= 0; i--) {
                if (turnHistory[i].skill === moveName) {
                    lastUsed = turnHistory[i].turn;
                    break;
                }
            }
            if (turnHistory.length - lastUsed >= cooldown) {
                const basePower = 10;
                const depthBonus = (pet.battle_stats?.depth || 0) * 0.5;
                const xpMod = (branch.xp || 0) / 1000;
                const power = Math.floor(basePower + depthBonus + xpMod);

                skills.push({
                    name: moveName,
                    branch: branchName,
                    tier: tier,
                    tier_score: tierScore,
                    power: power,
                    cooldown: cooldown,
                });
            }
        }
    }
    return skills;
}

function generateInsight(pet, skill, isCrit, damage) {
    const stats = pet.battle_stats;
    const branch = pet.tool_branches?.[skill.branch];
    const insights = [];

    if ((skill.tier_score || 0) >= 4) {
        insights.push(`Master-tier ${skill.branch} — deep expertise.`);
    } else if ((skill.tier_score || 0) <= 1) {
        insights.push(`Novice ${skill.branch} — still learning.`);
    }

    if ((stats?.velocity || 0) >= 15) {
        insights.push(`High velocity (${stats.velocity}) — ships fast.`);
    }
    if ((stats?.precision || 0) >= 15) {
        insights.push(`Precision (${stats.precision}) — reliable code.`);
    }
    if (isCrit) {
        insights.push(`Critical! Ingenuity (${stats?.ingenuity || 0}) — creative solutions.`);
    }

    const wf = pet.work_fingerprint || {};
    if ((wf.ci_pass_rate || 0) > 0.9) {
        insights.push(`CI pass: ${(wf.ci_pass_rate * 100).toFixed(0)}% — solid testing.`);
    }
    if ((wf.environments || []).length > 2) {
        insights.push(`Multi-env: ${wf.environments.slice(0, 3).join(', ')}.`);
    }

    return insights.slice(0, 2).join(' ');
}

function extractSkillShowcase(turns) {
    const showcase = {};
    for (const turn of turns) {
        const name = turn.attacker;
        const skill = turn.skill;
        if (skill && skill !== "Pass (no skills available)") {
            if (!showcase[name]) showcase[name] = [];
            if (!showcase[name].includes(skill)) showcase[name].push(skill);
        }
    }
    return showcase;
}
