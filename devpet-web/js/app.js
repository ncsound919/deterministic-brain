// devpet-web/js/app.js
// Main application logic

let petA = null, petB = null;
let battleResult = null;
let battleAnimInterval = null;
let currentMatchId = null; // Track current battle to prevent stale callbacks

function handleFileUpload(which, input) {
    const file = input.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        try {
            const data = JSON.parse(e.target.result);
            if (which === 'a') {
                petA = data;
                renderPetPreview('a', data);
            } else {
                petB = data;
                renderPetPreview('b', data);
            }
            updateBattleButton();
        } catch (err) {
            alert('Invalid JSON file: ' + err.message);
        }
    };
    reader.readAsText(file);
}

function renderPetPreview(which, petData) {
    const previewDiv = document.getElementById(`preview-${which}`);
    const infoDiv = document.getElementById(`info-${which}`);

    // Render pet on canvas
    const canvas = document.createElement('canvas');
    canvas.width = 200; canvas.height = 200;
    canvas.id = `canvas-preview-${which}`;
    previewDiv.innerHTML = '';
    previewDiv.appendChild(canvas);

    // Pet data needs visual_traits
    if (!petData.visual_traits) {
        petData.visual_traits = calcVisualTraits(petData);
    }
    if (!petData.pet_type) {
        petData.pet_type = getPetType(petData);
    }

    setTimeout(() => {
        PetRenderer.renderPetStatic(`canvas-preview-${which}`, petData);
    }, 50);

    // Show info (use DOM methods to prevent XSS)
    const stats = petData.battle_stats || {};
    const wf = petData.work_fingerprint || {};
    infoDiv.innerHTML = '';

    const nameDiv = document.createElement('div');
    const strong = document.createElement('strong');
    strong.textContent = petData.identity?.pet_name || 'Unknown';
    nameDiv.appendChild(strong);
    infoDiv.appendChild(nameDiv);

    const speciesDiv = document.createElement('div');
    speciesDiv.textContent = `Species: ${petData.identity?.pet_species || 'Unknown'}`;
    infoDiv.appendChild(speciesDiv);

    const levelDiv = document.createElement('div');
    levelDiv.textContent = `Level: ${petData.level || 1} | Stage: ${petData.evolution_stage || 1}`;
    infoDiv.appendChild(levelDiv);

    // Stat bars
    ['velocity', 'precision', 'depth'].forEach(stat => {
        const barDiv = document.createElement('div');
        barDiv.className = 'stat-bar';
        const labelDiv = document.createElement('div');
        labelDiv.className = 'stat-bar-label';
        const labelSpan = document.createElement('span');
        labelSpan.textContent = stat.charAt(0).toUpperCase() + stat.slice(1);
        const valueSpan = document.createElement('span');
        valueSpan.textContent = stats[stat] || 0;
        labelDiv.appendChild(labelSpan);
        labelDiv.appendChild(valueSpan);
        barDiv.appendChild(labelDiv);
        const fillDiv = document.createElement('div');
        fillDiv.className = 'stat-bar-fill';
        fillDiv.style.width = `${(stats[stat] || 0) * 3.33}%`;
        barDiv.appendChild(fillDiv);
        infoDiv.appendChild(barDiv);
    });

    const footerDiv = document.createElement('div');
    footerDiv.style.fontSize = '0.75rem';
    footerDiv.style.marginTop = '5px';
    footerDiv.textContent = `Primary: ${wf.primary_language || 'N/A'} | CI: ${(wf.ci_pass_rate || 0) * 100}%`;
    infoDiv.appendChild(footerDiv);
}

function calcVisualTraits(petData) {
    const branches = petData.tool_branches || {};
    let maxXP = 0, primaryBranch = null;
    for (const [name, branch] of Object.entries(branches)) {
        if ((branch.xp || 0) > maxXP) {
            maxXP = branch.xp || 0;
            primaryBranch = name;
        }
    }
    const typeMap = {
        version_control: 'electric', ci_cd: 'steel', testing: 'fairy',
        containers: 'water', databases: 'grass', apis: 'psychic',
        frontend: 'fire', low_level: 'dark', ai_ml: 'dragon',
        security: 'ghost', docs: 'normal', debugging: 'fighting',
        performance: 'rock',
    };
    const typeColors = {
        electric: '#FFD700', steel: '#A8A8C8', fairy: '#FFB6C1',
        water: '#6493EA', grass: '#78C850', psychic: '#F85888',
        fire: '#F08030', dark: '#705848', dragon: '#7038F8',
        ghost: '#705898', normal: '#A8A878', fighting: '#C03028',
        rock: '#B8A038',
    };
    const petType = typeMap[primaryBranch] || 'normal';
    const stats = petData.battle_stats || {};
    return {
        type: petType,
        primary_color: typeColors[petType] || '#A8A878',
        evolution_stage: petData.evolution_stage || 1,
        level: petData.level || 1,
        body_shape: (stats.breadth || 0) > (stats.depth || 0) ? 'wide' : (stats.depth || 0) > (stats.breadth || 0) ? 'tall' : 'balanced',
        aura_effects: [
            ...((stats.velocity || 0) >= 15 ? ['speed_lines'] : []),
            ...((stats.precision || 0) >= 15 ? ['sharp_aura'] : []),
            ...((stats.resilience || 0) >= 15 ? ['shield_aura'] : []),
            ...((stats.ingenuity || 0) >= 15 ? ['sparkle_aura'] : []),
        ],
        size: Math.min(100, 40 + (petData.level || 1) * 3),
    };
}

function getPetType(petData) {
    const branches = petData.tool_branches || {};
    let maxXP = 0, primaryBranch = null;
    for (const [name, branch] of Object.entries(branches)) {
        if ((branch.xp || 0) > maxXP) {
            maxXP = branch.xp || 0;
            primaryBranch = name;
        }
    }
    const typeMap = {
        version_control: 'electric', ci_cd: 'steel', testing: 'fairy',
        containers: 'water', databases: 'grass', apis: 'psychic',
        frontend: 'fire', low_level: 'dark', ai_ml: 'dragon',
    };
    return typeMap[primaryBranch] || 'normal';
}

function updateBattleButton() {
    document.getElementById('battle-btn').disabled = !(petA && petB);
}

function startBattle() {
    if (!petA || !petB) return;

    // Fix: Clear any existing interval to prevent leak
    if (battleAnimInterval) {
        clearInterval(battleAnimInterval);
        battleAnimInterval = null;
    }

    const matchId = document.getElementById('match-id').value || `match_${Date.now()}`;
    currentMatchId = matchId; // Track current battle

    // Ensure visual traits exist
    [petA, petB].forEach(p => {
        if (!p.visual_traits) p.visual_traits = calcVisualTraits(p);
        if (!p.pet_type) p.pet_type = getPetType(p);
    });

    battleResult = battle(petA, petB, matchId);

    // Show arena
    document.getElementById('arena-section').style.display = 'block';
    document.getElementById('arena-name-a').textContent = petA.identity?.pet_name || 'Pet A';
    document.getElementById('arena-name-b').textContent = petB.identity?.pet_name || 'Pet B';

    // Render initial pets
    setTimeout(() => {
        PetRenderer.renderPetStatic('canvas-a', petA);
        PetRenderer.renderPetStatic('canvas-b', petB);
        animateBattle(battleResult);
    }, 100);

    // Scroll to arena
    document.getElementById('arena-section').scrollIntoView({ behavior: 'smooth' });
}

function animateBattle(result) {
    const logDiv = document.getElementById('battle-log');
    logDiv.innerHTML = '';

    const hpA = petA.battle_stats.resilience * 10;
    const hpB = petB.battle_stats.resilience * 10;
    let turnIndex = 0;

    battleAnimInterval = setInterval(() => {
        // Fix: Check if this is still the current battle
        if (currentMatchId && currentMatchId !== result.match_id) {
            clearInterval(battleAnimInterval);
            battleAnimInterval = null;
            return;
        }

        if (turnIndex >= result.turns.length) {
            clearInterval(battleAnimInterval);
            battleAnimInterval = null;
            showBattleResult(result);
            return;
        }

        const turn = result.turns[turnIndex];
        const turnDiv = document.createElement('div');
        turnDiv.className = `turn ${turn.critical ? 'crit' : ''}`;

        const attackerIsA = turn.attacker === (petA.identity?.pet_name || 'Pet A');
        const defenderPet = attackerIsA ? petB : petA;
        const defenderCanvas = attackerIsA ? 'canvas-b' : 'canvas-a';
        const defenderHPId = attackerIsA ? 'hp-b' : 'hp-a';
        const defenderHPTextId = attackerIsA ? 'hp-text-b' : 'hp-text-a';

        // Update HP bar
        const hpPercent = turn.defender_hp_percent || 0;
        document.getElementById(defenderHPId).style.width = hpPercent + '%';
        document.getElementById(defenderHPTextId).textContent = `${Math.max(0, turn.defender_hp_remaining)} HP`;

        // Flash damage
        if (defenderPet && defenderPet.visual_traits) {
            PetRenderer.renderPet(defenderCanvas, defenderPet, false, 0.3);
            setTimeout(() => PetRenderer.renderPetStatic(defenderCanvas, defenderPet), 200);
        }

        // Attack animation
        const attackerCanvas = attackerIsA ? 'canvas-a' : 'canvas-b';
        const attackerPet = attackerIsA ? petA : petB;
        if (attackerPet && attackerPet.visual_traits) {
            PetRenderer.renderPet(attackerCanvas, attackerPet, true, 0);
            setTimeout(() => PetRenderer.renderPetStatic(attackerCanvas, attackerPet), 300);
        }

        // Fix: Use textContent to prevent XSS from untrusted pet data
        const strong = document.createElement('strong');
        strong.textContent = `Turn ${turn.turn}:`;
        turnDiv.appendChild(strong);

        turnDiv.appendChild(document.createTextNode(' '));

        const attackerSpan = document.createElement('span');
        attackerSpan.textContent = turn.attacker;
        turnDiv.appendChild(attackerSpan);

        turnDiv.appendChild(document.createTextNode(' uses '));

        const skillSpan = document.createElement('span');
        skillSpan.className = 'skill-name';
        skillSpan.textContent = turn.skill;
        turnDiv.appendChild(skillSpan);

        turnDiv.appendChild(document.createTextNode(' → '));

        const dmgSpan = document.createElement('span');
        dmgSpan.className = 'damage';
        dmgSpan.textContent = `${turn.damage} dmg`;
        turnDiv.appendChild(dmgSpan);

        if (turn.critical) {
            turnDiv.appendChild(document.createTextNode(' **CRIT!**'));
        }

        if (turn.insight) {
            const insightDiv = document.createElement('div');
            insightDiv.className = 'insight';
            insightDiv.textContent = `💡 ${turn.insight}`;
            turnDiv.appendChild(insightDiv);
        }

        logDiv.appendChild(turnDiv);
        logDiv.scrollTop = logDiv.scrollHeight;

        turnIndex++;
    }, 800);
}

function showBattleResult(result) {
    const resultDiv = document.getElementById('battle-result');
    resultDiv.innerHTML = '';

    if (result.winner === 'Draw') {
        const drawDiv = document.createElement('div');
        drawDiv.style.color = '#f7dc6f';
        drawDiv.textContent = "It's a Draw!";
        resultDiv.appendChild(drawDiv);
    } else {
        const winnerDiv = document.createElement('div');
        winnerDiv.appendChild(document.createTextNode('Winner: '));
        const winnerSpan = document.createElement('span');
        winnerSpan.className = 'winner';
        winnerSpan.textContent = result.winner;
        winnerDiv.appendChild(winnerSpan);
        resultDiv.appendChild(winnerDiv);

        if (result.loser) {
            const loserDiv = document.createElement('div');
            loserDiv.appendChild(document.createTextNode('Loser: '));
            const loserSpan = document.createElement('span');
            loserSpan.className = 'loser';
            loserSpan.textContent = result.loser;
            loserDiv.appendChild(loserSpan);
            resultDiv.appendChild(loserDiv);
        }

        const turnsDiv = document.createElement('div');
        turnsDiv.style.fontSize = '1rem';
        turnsDiv.style.marginTop = '10px';
        turnsDiv.textContent = `Total turns: ${result.total_turns}`;
        resultDiv.appendChild(turnsDiv);

        const btn = document.createElement('button');
        btn.style.marginTop = '10px';
        btn.style.padding = '8px 20px';
        btn.style.background = '#a569bd';
        btn.style.color = '#fff';
        btn.style.border = 'none';
        btn.style.borderRadius = '5px';
        btn.style.cursor = 'pointer';
        btn.textContent = 'View Winner Stats';
        btn.onclick = () => showPetStats(result.winner);
        resultDiv.appendChild(btn);
    }
}

function showPetStats(petName) {
    const pet = petName === (petA.identity?.pet_name || 'Pet A') ? petA : petB;
    const modal = document.getElementById('stats-modal');
    const body = document.getElementById('modal-body');
    body.innerHTML = '';

    const stats = pet.battle_stats || {};
    const wf = pet.work_fingerprint || {};
    const branches = pet.tool_branches || {};

    // Title
    const title = document.createElement('h2');
    title.textContent = `${pet.identity?.pet_name || 'Unknown'} Stats`;
    body.appendChild(title);

    // Stat grid
    const statGrid = document.createElement('div');
    statGrid.className = 'stat-grid';
    const statLabels = ['Velocity', 'Precision', 'Breadth', 'Depth', 'Resilience', 'Ingenuity'];
    const statKeys = ['velocity', 'precision', 'breadth', 'depth', 'resilience', 'ingenuity'];
    statLabels.forEach((label, i) => {
        const item = document.createElement('div');
        item.className = 'stat-item';
        const labelDiv = document.createElement('div');
        labelDiv.className = 'label';
        labelDiv.textContent = label;
        const valueDiv = document.createElement('div');
        valueDiv.className = 'value';
        valueDiv.textContent = stats[statKeys[i]] || 0;
        item.appendChild(labelDiv);
        item.appendChild(valueDiv);
        statGrid.appendChild(item);
    });
    body.appendChild(statGrid);

    // Work Fingerprint
    const wfTitle = document.createElement('h3');
    wfTitle.textContent = 'Work Fingerprint';
    body.appendChild(wfTitle);

    const primaryLang = document.createElement('div');
    primaryLang.textContent = `Primary Language: ${wf.primary_language || 'N/A'}`;
    body.appendChild(primaryLang);

    const ciRate = document.createElement('div');
    ciRate.textContent = `CI Pass Rate: ${(wf.ci_pass_rate || 0) * 100}%`;
    body.appendChild(ciRate);

    const sessions = document.createElement('div');
    sessions.textContent = `Sessions: ${wf.session_count || 0}`;
    body.appendChild(sessions);

    const envDiv = document.createElement('div');
    envDiv.textContent = `Environments: ${(wf.environments || []).join(', ') || 'None'}`;
    body.appendChild(envDiv);

    // Tool Branches
    const tbTitle = document.createElement('h3');
    tbTitle.textContent = 'Tool Branches';
    body.appendChild(tbTitle);

    const ul = document.createElement('ul');
    ul.className = 'branch-list';
    for (const [name, branch] of Object.entries(branches)) {
        const li = document.createElement('li');
        const tier = (branch.tier || 'novice').toLowerCase();
        li.className = `tier-${tier}`;
        const strong = document.createElement('strong');
        strong.textContent = name;
        li.appendChild(strong);
        li.appendChild(document.createTextNode(` - ${branch.tier || 'Novice'} (XP: ${branch.xp || 0})`));
        const br = document.createElement('br');
        li.appendChild(br);
        const small = document.createElement('small');
        small.textContent = `Moves: ${(branch.signature_moves || []).join(', ')}`;
        li.appendChild(small);
        ul.appendChild(li);
    }
    body.appendChild(ul);

    modal.style.display = 'flex';
}

function closeModal() {
    document.getElementById('stats-modal').style.display = 'none';
}

function resetBattle() {
    if (battleAnimInterval) clearInterval(battleAnimInterval);
    document.getElementById('arena-section').style.display = 'none';
    document.getElementById('battle-result').innerHTML = '';
    document.getElementById('battle-log').innerHTML = '';
    petA = null; petB = null;
    document.getElementById('preview-a').innerHTML = '';
    document.getElementById('preview-b').innerHTML = '';
    document.getElementById('info-a').innerHTML = '';
    document.getElementById('info-b').innerHTML = '';
    document.getElementById('battle-btn').disabled = true;
}

// Close modal on outside click
window.onclick = function(event) {
    const modal = document.getElementById('stats-modal');
    if (event.target === modal) closeModal();
};
