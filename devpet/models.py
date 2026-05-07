"""Data models for DevPet system."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class Tier(Enum):
    NOVICE = 1
    PRACTITIONER = 2
    EXPERT = 3
    MASTER = 4
    LEGEND = 5

    @property
    def display_name(self) -> str:
        return self.name.capitalize()

    @property
    def tier_score(self) -> int:
        return self.value


TIER_CD = {
    Tier.NOVICE: 6,
    Tier.PRACTITIONER: 5,
    Tier.EXPERT: 4,
    Tier.MASTER: 3,
    Tier.LEGEND: 2,
}


@dataclass
class ToolBranch:
    """A tool category branch (version_control, ci_cd, testing, etc.)."""
    name: str
    tier: Tier
    xp: int
    events: Dict[str, int] = field(default_factory=dict)
    signature_moves: List[str] = field(default_factory=list)

    def add_xp(self, amount: int) -> None:
        self.xp += amount
        # Auto-tier progression
        thresholds = [0, 1000, 3000, 7000, 15000]
        for i, t in enumerate(thresholds):
            if self.xp >= t:
                self.tier = Tier(i + 1)

    @property
    def tier_score(self) -> int:
        return self.tier.tier_score

    @property
    def cooldown(self) -> int:
        return TIER_CD.get(self.tier, 5)


@dataclass
class BattleStats:
    """Six-dimensional capability stats."""
    velocity: int = 0
    precision: int = 0
    breadth: int = 0
    depth: int = 0
    resilience: int = 0
    ingenuity: int = 0

    def to_dict(self) -> Dict[str, int]:
        return {
            "velocity": self.velocity,
            "precision": self.precision,
            "breadth": self.breadth,
            "depth": self.depth,
            "resilience": self.resilience,
            "ingenuity": self.ingenuity,
        }


@dataclass
class WorkFingerprint:
    """Work style and environment fingerprint."""
    session_count: int = 0
    total_coding_minutes: int = 0
    avg_task_completion_seconds: float = 0.0
    ci_pass_rate: float = 0.0
    tools_used_distinct: int = 0
    primary_language: str = ""
    languages: List[Dict[str, object]] = field(default_factory=list)
    environments: List[str] = field(default_factory=list)
    problem_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "session_count": self.session_count,
            "total_coding_minutes": self.total_coding_minutes,
            "avg_task_completion_seconds": self.avg_task_completion_seconds,
            "ci_pass_rate": self.ci_pass_rate,
            "tools_used_distinct": self.tools_used_distinct,
            "primary_language": self.primary_language,
            "languages": self.languages,
            "environments": self.environments,
            "problem_patterns": self.problem_patterns,
        }


# Tool branch → pet "type" mapping (like Pokemon types)
BRANCH_TYPE_MAP = {
    "version_control": "electric",   # Git = lightning
    "ci_cd": "steel",               # CI/CD = industrial/metal
    "testing": "fairy",             # Testing = protective/magical
    "containers": "water",          # Docker = fluid
    "databases": "grass",           # DB = organic/data growth
    "apis": "psychic",             # APIs = mind/connection
    "frontend": "fire",            # Frontend = flashy/energy
    "low_level": "dark",           # Low-level = shadows/binary
    "ai_ml": "dragon",            # AI/ML = powerful/rare
    "security": "ghost",           # Security = invisible/stealth
    "docs": "normal",              # Docs = standard
    "debugging": "fighting",       # Debugging = combat
    "performance": "rock",         # Performance = solid/enduring
}


@dataclass
class DevPet:
    """The complete DevPet state."""
    pet_name: str
    species: str  # Derived from primary tool branch
    archetype: str  # Derived from dominant stat
    developer_id: str
    display_name: str
    created_at: str
    last_updated: str

    battle_stats: BattleStats = field(default_factory=BattleStats)
    work_fingerprint: WorkFingerprint = field(default_factory=WorkFingerprint)
    tool_branches: Dict[str, ToolBranch] = field(default_factory=dict)

    level: int = 1
    xp_total: int = 0
    evolution_stage: int = 1  # 1-4, changes form at certain levels

    # Visual traits (derived from tool branches for procedural rendering)
    visual_traits: Dict[str, object] = field(default_factory=dict)

    def get_primary_branch(self) -> Optional[ToolBranch]:
        if not self.tool_branches:
            return None
        return max(self.tool_branches.values(), key=lambda b: b.xp)

    def get_pet_type(self) -> str:
        primary = self.get_primary_branch()
        if not primary:
            return "normal"
        return BRANCH_TYPE_MAP.get(primary.name, "normal")

    def update_visual_traits(self) -> None:
        """Update visual traits based on current tool branches."""
        primary = self.get_primary_branch()
        pet_type = self.get_pet_type()

        # Base color from primary branch type
        type_colors = {
            "electric": "#FFD700",
            "steel": "#A8A8C8",
            "fairy": "#FFB6C1",
            "water": "#6493EA",
            "grass": "#78C850",
            "psychic": "#F85888",
            "fire": "#F08030",
            "dark": "#705848",
            "dragon": "#7038F8",
            "ghost": "#705898",
            "normal": "#A8A878",
            "fighting": "#C03028",
            "rock": "#B8A038",
        }

        self.visual_traits = {
            "type": pet_type,
            "primary_color": type_colors.get(pet_type, "#A8A878"),
            "evolution_stage": self.evolution_stage,
            "level": self.level,
            "body_shape": self._calc_body_shape(),
            "aura_effects": self._calc_aura_effects(),
            "size": min(100, 40 + self.level * 3),
        }

    def _calc_body_shape(self) -> str:
        """Determine body shape based on stats."""
        bs = self.battle_stats
        if bs.breadth > bs.depth:
            return "wide"  # Versatile developer
        elif bs.depth > bs.breadth:
            return "tall"  # Specialist
        return "balanced"

    def _calc_aura_effects(self) -> List[str]:
        """Special visual effects based on high stats."""
        effects = []
        bs = self.battle_stats
        if bs.velocity >= 15:
            effects.append("speed_lines")
        if bs.precision >= 15:
            effects.append("sharp_aura")
        if bs.resilience >= 15:
            effects.append("shield_aura")
        if bs.ingenuity >= 15:
            effects.append("sparkle_aura")
        return effects

    def to_dict(self) -> Dict:
        return {
            "spec_version": "1.0",
            "identity": {
                "developer_id": self.developer_id,
                "display_name": self.display_name,
                "pet_name": self.pet_name,
                "pet_species": self.species,
                "created_at": self.created_at,
                "last_updated": self.last_updated,
            },
            "battle_stats": self.battle_stats.to_dict(),
            "work_fingerprint": self.work_fingerprint.to_dict(),
            "tool_branches": {
                name: {
                    "tier": branch.tier.display_name,
                    "tier_score": branch.tier_score,
                    "xp": branch.xp,
                    "events": branch.events,
                    "signature_moves": branch.signature_moves,
                    "cooldown": branch.cooldown,
                }
                for name, branch in self.tool_branches.items()
            },
            "level": self.level,
            "xp_total": self.xp_total,
            "evolution_stage": self.evolution_stage,
            "visual_traits": self.visual_traits,
            "pet_type": self.get_pet_type(),
        }
