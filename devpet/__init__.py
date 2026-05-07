"""DevPet — Pokemon-style developer pet that grows from deterministic-brain activity."""
from __future__ import annotations
from .models import DevPet, ToolBranch, BattleStats, WorkFingerprint
from .tracker import DevPetTracker
from .stats import calculate_stats, calculate_pet_level
from .battle import battle, simulate_battle_log
from .export import export_devpet_json, load_devpet_json

__version__ = "1.0.0"

__all__ = [
    "DevPet", "ToolBranch", "BattleStats", "WorkFingerprint",
    "DevPetTracker", "calculate_stats", "calculate_pet_level",
    "battle", "simulate_battle_log",
    "export_devpet_json", "load_devpet_json",
]
