"""Export/import DevPet JSON files with optional signing."""
from __future__ import annotations
import json
import hashlib
import hmac
from typing import Dict, Optional
from pathlib import Path

from .models import DevPet, ToolBranch, BattleStats, WorkFingerprint, Tier


def export_devpet_json(pet: DevPet, secret_key: Optional[bytes] = None) -> str:
    """
    Export DevPet to JSON string.
    If secret_key is provided, adds HMAC signature.
    """
    data = pet.to_dict()

    # Create history hash from tool branches (simplified)
    history_str = json.dumps(data["tool_branches"], sort_keys=True)
    data["history_hash"] = hashlib.sha256(history_str.encode()).hexdigest()

    # Add signature if key provided
    if secret_key:
        payload = json.dumps(data, sort_keys=True)
        sig = hmac.new(secret_key, payload.encode(), hashlib.sha256).hexdigest()
        data["signature"] = sig
    else:
        data["signature"] = None

    return json.dumps(data, indent=2)


def load_devpet_json(json_str: str, public_key: Optional[bytes] = None) -> DevPet:
    """
    Load DevPet from JSON string.
    If public_key is provided, verifies signature.
    """
    data = json.loads(json_str)

    # Verify signature if present
    if public_key and data.get("signature"):
        provided_sig = data.pop("signature")
        payload = json.dumps(data, sort_keys=True)
        expected_sig = hmac.new(public_key, payload.encode(), hashlib.sha256).hexdigest()
        if provided_sig != expected_sig:
            raise ValueError("Invalid signature — data may be tampered!")
        data["signature"] = provided_sig  # restore

    # Reconstruct DevPet
    identity = data.get("identity", {})
    battle_stats_data = data.get("battle_stats", {})
    work_fp_data = data.get("work_fingerprint", {})
    tool_branches_data = data.get("tool_branches", {})

    # Reconstruct battle stats
    battle_stats = BattleStats(**battle_stats_data)

    # Reconstruct work fingerprint
    work_fingerprint = WorkFingerprint(**work_fp_data)

    # Reconstruct tool branches
    tool_branches = {}
    tier_map = {1: Tier.NOVICE, 2: Tier.PRACTITIONER, 3: Tier.EXPERT,
                 4: Tier.MASTER, 5: Tier.LEGEND}
    for name, branch_data in tool_branches_data.items():
        tier = tier_map.get(branch_data.get("tier_score", 1), Tier.NOVICE)
        branch = ToolBranch(
            name=name,
            tier=tier,
            xp=branch_data.get("xp", 0),
            events=branch_data.get("events", {}),
            signature_moves=branch_data.get("signature_moves", []),
        )
        tool_branches[name] = branch

    # Create DevPet
    pet = DevPet(
        pet_name=identity.get("pet_name", "Unknown"),
        species=identity.get("pet_species", "BasicBlob"),
        archetype=data.get("archetype", "Novice"),
        developer_id=identity.get("developer_id", ""),
        display_name=identity.get("display_name", ""),
        created_at=identity.get("created_at", ""),
        last_updated=identity.get("last_updated", ""),
        battle_stats=battle_stats,
        work_fingerprint=work_fingerprint,
        tool_branches=tool_branches,
        level=data.get("level", 1),
        xp_total=data.get("xp_total", 0),
        evolution_stage=data.get("evolution_stage", 1),
        visual_traits=data.get("visual_traits", {}),
    )
    return pet


def save_devpet_file(pet: DevPet, path: str, secret_key: Optional[bytes] = None) -> None:
    """Save DevPet to .devpet file."""
    json_str = export_devpet_json(pet, secret_key)
    Path(path).write_text(json_str)


def load_devpet_file(path: str, public_key: Optional[bytes] = None) -> DevPet:
    """Load DevPet from .devpet file."""
    json_str = Path(path).read_text()
    return load_devpet_json(json_str, public_key)


def verify_devpet(data: Dict, public_key: bytes) -> bool:
    """Verify DevPet signature."""
    if not data.get("signature"):
        return False
    provided_sig = data.pop("signature")
    payload = json.dumps(data, sort_keys=True)
    expected_sig = hmac.new(public_key, payload.encode(), hashlib.sha256).hexdigest()
    data["signature"] = provided_sig  # restore
    return provided_sig == expected_sig
