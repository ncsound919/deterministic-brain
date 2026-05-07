# DevPet Module

> Pokemon-style developer pets that grow from your deterministic-brain activity.

## Overview

DevPet turns your coding activity into a living, battling pet. Your pet's stats reflect your real capabilities:

- **Velocity** — How fast you ship
- **Precision** — Code quality, CI pass rate
- **Breadth** — Tool/language diversity
- **Depth** — Mastery in specific areas
- **Resilience** — Recovery from failures
- **Ingenuity** — Creative problem-solving

## Architecture

```
devpet/
├── __init__.py        # Package exports
├── models.py          # Data models (DevPet, ToolBranch, BattleStats)
├── tracker.py         # Hooks into tracing to build pet state
├── stats.py           # Deterministic stat calculation
├── battle.py         # Deterministic battle engine
└── export.py         # JSON export/import with HMAC signing
```

## Quick Start

### 1. Generate a DevPet from traces

```python
from devpet import DevPetTracker

tracker = DevPetTracker(db_path="traces.db", pet_name="MyPet")
pet = tracker.process_events()

# Export to file
from devpet import export_devpet_json
json_str = export_devpet_json(pet)
with open("my-pet.devpet", "w") as f:
    f.write(json_str)
```

### 2. Battle two pets (deterministic)

```python
from devpet import load_devpet_json, battle

pet_a = load_devpet_json(open("pet-a.devpet").read())
pet_b = load_devpet_json(open("pet-b.devpet").read())

result = battle(pet_a, pet_b, match_id="match_001")
print(f"Winner: {result['winner']}")
```

### 3. View in browser

Open `devpet-web/index.html` in a browser, upload two `.devpet` files, and watch them battle!

## Tool Branch Mapping

| Tool Category | Maps to Pet Type | Signature Moves |
|--------------|-----------------| -----------------|
| version_control | ⚡ Electric | CleanHistory, BisectBlitz |
| ci_cd | ⚙️ Steel | PipelineParry, GreenBuildGuard |
| testing | 🧚 Fairy | CoverageCloak, AssertAegis |
| containers | 🌊 Water | ContainerSwarm, ComposeShield |
| databases | 🌿 Grass | QueryQuake, MigrationMold |
| apis | 🔮 Psychic | EndpointEagle, SchemaShield |
| frontend | 🔥 Fire | ReactRampage, StyleStorm |
| low_level | 🌑 Dark | PointerPummel, MemoryMaelstrom |
| ai_ml | 🐉 Dragon | TensorTornado, NeuralNova |

## Pet Evolution

Pets evolve through 4 stages based on total XP:

- **Stage 1** (Level 1-9): Basic blob
- **Stage 2** (Level 10-19): Gains arms
- **Stage 3** (Level 20-29): Gains legs
- **Stage 4** (Level 30+): Gains wings/aura

## Battle Mechanics

Battles are **100% deterministic** — same pets + same match_id = identical outcome.

- **Initiative**: Higher velocity moves first
- **Damage**: `base_power + velocity * 0.5 - defender_precision * 0.2`
- **Critical Hits**: Chance based on ingenuity stat
- **Skills**: Tied to tool branches, with cooldowns based on tier

## Web Interface

The `devpet-web/` directory contains a static site:

- **Upload**: Drag-and-drop `.devpet` JSON files
- **Visualization**: Canvas-rendered pets with trait-based appearance
- **Battle Log**: Turn-by-turn log with "insight" annotations
- **Share**: Battle replays can be shared via URL parameters

```
devpet-web/
├── index.html          # Main page
├── css/style.css      # Styling
└── js/
    ├── battle.js      # Battle engine (JS port)
    ├── pet-renderer.js # Canvas pet rendering
    └── app.js        # UI logic
```

## Integration with Deterministic Brain

The tracker hooks into `tools/tracing.py` to capture events:

```python
# In your code, log events with tool info:
from tools.tracing import log_event

log_event("docker_build", {
    "tool": "docker",
    "language": "python",
    "environment": "Docker"
})
```

The DevPetTracker processes these events to build your pet.

## File Format (.devpet)

```json
{
  "spec_version": "1.0",
  "identity": { ... },
  "battle_stats": { ... },
  "tool_branches": { ... },
  "visual_traits": { ... },
  "history_hash": "...",
  "signature": "..."
}
```

Optional HMAC signature prevents tampering.

## License

Same as deterministic-brain (MIT).
