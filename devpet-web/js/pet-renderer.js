// devpet-web/js/pet-renderer.js
// Canvas-based procedural pet rendering based on traits

const TypeColors = {
    electric: { primary: '#FFD700', secondary: '#FFA500', accent: '#FFF8DC' },
    steel: { primary: '#A8A8C8', secondary: '#808090', accent: '#D3D3D3' },
    fairy: { primary: '#FFB6C1', secondary: '#FF69B4', accent: '#FFF0F5' },
    water: { primary: '#6493EA', secondary: '#1E90FF', accent: '#87CEEB' },
    grass: { primary: '#78C850', secondary: '#228B22', accent: '#98FB98' },
    psychic: { primary: '#F85888', secondary: '#C71585', accent: '#FFC0CB' },
    fire: { primary: '#F08030', secondary: '#FF4500', accent: '#FFDAB9' },
    dark: { primary: '#705848', secondary: '#2F4F4F', accent: '#696969' },
    dragon: { primary: '#7038F8', secondary: '#4B0082', accent: '#E6E6FA' },
    ghost: { primary: '#705898', secondary: '#483D8B', accent: '#D8BFD8' },
    normal: { primary: '#A8A878', secondary: '#808000', accent: '#F0E68C' },
    fighting: { primary: '#C03028', secondary: '#8B0000', accent: '#FFB6C1' },
    rock: { primary: '#B8A038', secondary: '#8B4513', accent: '#DEB887' },
};

function renderPet(canvasId, petData, isAttacking = false, damageFlash = 0) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    const traits = petData.visual_traits || {};
    const petType = petData.pet_type || 'normal';
    const colors = TypeColors[petType] || TypeColors.normal;
    const stage = traits.evolution_stage || 1;
    const level = traits.level || 1;
    const bodyShape = traits.body_shape || 'balanced';
    const size = traits.size || 60;
    const effects = traits.aura_effects || [];

    const cx = w / 2, cy = h / 2;

    // Damage flash
    if (damageFlash > 0) {
        ctx.globalAlpha = damageFlash;
        ctx.fillStyle = '#FF0000';
        ctx.fillRect(0, 0, w, h);
        ctx.globalAlpha = 1.0;
    }

    // Aura effects
    if (effects.includes('shield_aura')) {
        ctx.beginPath();
        ctx.arc(cx, cy, size + 20, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(100, 149, 237, 0.3)';
        ctx.fill();
    }
    if (effects.includes('speed_lines')) {
        for (let i = 0; i < 3; i++) {
            ctx.beginPath();
            ctx.moveTo(cx - size - 30, cy - 10 + i * 10);
            ctx.lineTo(cx - size - 10, cy - 10 + i * 10);
            ctx.strokeStyle = 'rgba(255, 215, 0, 0.6)';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    }
    if (effects.includes('sparkle_aura')) {
        for (let i = 0; i < 5; i++) {
            const angle = (Date.now() / 1000 + i) % (Math.PI * 2);
            const sx = cx + Math.cos(angle) * (size + 15);
            const sy = cy + Math.sin(angle) * (size + 15);
            ctx.beginPath();
            ctx.arc(sx, sy, 3, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255, 215, 0, 0.8)';
            ctx.fill();
        }
    }

    // Body
    ctx.fillStyle = colors.primary;
    ctx.strokeStyle = colors.secondary;
    ctx.lineWidth = 2;

    if (bodyShape === 'wide') {
        // Wide body (versatile dev)
        ctx.beginPath();
        ctx.ellipse(cx, cy, size * 0.8, size * 0.5, 0, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
    } else if (bodyShape === 'tall') {
        // Tall body (specialist)
        ctx.beginPath();
        ctx.ellipse(cx, cy, size * 0.4, size * 0.8, 0, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
    } else {
        // Balanced
        ctx.beginPath();
        ctx.arc(cx, cy, size * 0.5, 0, Math.PI * 2);
        ctx.fill(); ctx.stroke();
    }

    // Evolution stage features
    if (stage >= 2) {
        // Arms
        ctx.fillStyle = colors.primary;
        ctx.fillRect(cx - size * 0.6, cy - 5, size * 0.2, size * 0.4);
        ctx.fillRect(cx + size * 0.4, cy - 5, size * 0.2, size * 0.4);
    }
    if (stage >= 3) {
        // Legs
        ctx.fillRect(cx - size * 0.3, cy + size * 0.4, size * 0.15, size * 0.3);
        ctx.fillRect(cx + size * 0.15, cy + size * 0.4, size * 0.15, size * 0.3);
    }
    if (stage >= 4) {
        // Wings/aura for final form
        ctx.fillStyle = colors.accent;
        ctx.globalAlpha = 0.5;
        ctx.beginPath();
        ctx.ellipse(cx - size * 0.7, cy, size * 0.3, size * 0.6, -0.3, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.ellipse(cx + size * 0.7, cy, size * 0.3, size * 0.6, 0.3, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1.0;
    }

    // Eyes
    ctx.fillStyle = '#FFF';
    ctx.beginPath(); ctx.arc(cx - 10, cy - 5, 5, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(cx + 10, cy - 5, 5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#000';
    ctx.beginPath(); ctx.arc(cx - 10, cy - 5, 2, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(cx + 10, cy - 5, 2, 0, Math.PI * 2); ctx.fill();

    // Mouth
    ctx.strokeStyle = colors.secondary;
    ctx.beginPath();
    ctx.arc(cx, cy + 5, 8, 0, Math.PI, false);
    ctx.stroke();

    // Attack animation
    if (isAttacking) {
        ctx.strokeStyle = 'rgba(255, 255, 0, 0.8)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(cx + (bodyShape === 'tall' ? size * 0.4 : size * 0.5), cy);
        ctx.lineTo(cx + (bodyShape === 'tall' ? size * 0.4 : size * 0.5) + 20, cy);
        ctx.stroke();
    }

    // Level badge
    ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
    ctx.beginPath();
    ctx.arc(cx + size * 0.4, cy - size * 0.4, 12, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#FFF';
    ctx.font = 'bold 10px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(level, cx + size * 0.4, cy - size * 0.4);
}

function renderPetStatic(canvasId, petData) {
    renderPet(canvasId, petData, false, 0);
}

// Export
window.PetRenderer = {
    renderPet,
    renderPetStatic,
    TypeColors,
};
