"""DevPet routes — Tamagotchi-style pet management (battling on website)."""
from __future__ import annotations
import json
import os
import glob
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Dict, List
from pathlib import Path

from orchestration.event_bus import event_bus

router = APIRouter(prefix="/devpets", tags=["devpets"])

DEVPETS_DIR = Path("devpets")
DEVPETS_DIR.mkdir(exist_ok=True)


class DevPetGenerateRequest(BaseModel):
    pet_name: str = "DevPet"
    db_path: str = "traces.db"


@router.get("")
def list_devpets() -> Dict[str, List[Dict]]:
    """List all DevPets from the devpets/ directory."""
    pets = []
    for fpath in glob.glob(str(DEVPETS_DIR / "*.json")):
        try:
            data = json.loads(Path(fpath).read_text())
            identity = data.get("identity", {})
            pets.append({
                "id": identity.get("developer_id", Path(fpath).stem),
                "pet_name": identity.get("pet_name", "Unknown"),
                "species": identity.get("pet_species", "Unknown"),
                "level": data.get("level", 1),
                "evolution_stage": data.get("evolution_stage", 1),
                "pet_type": data.get("pet_type", "normal"),
                "battle_stats": data.get("battle_stats", {}),
                "file": Path(fpath).name,
            })
        except Exception:
            continue
    return {"devpets": pets, "count": len(pets)}


@router.get("/{pet_id}")
def get_devpet(pet_id: str) -> Dict:
    """Get a single DevPet's full data."""
    for fpath in glob.glob(str(DEVPETS_DIR / "*.json")):
        try:
            data = json.loads(Path(fpath).read_text())
            identity = data.get("identity", {})
            if identity.get("developer_id") == pet_id or Path(fpath).stem == pet_id:
                return {"pet": data, "file": Path(fpath).name}
        except Exception:
            continue
    raise HTTPException(status_code=404, detail=f"DevPet '{pet_id}' not found")


@router.get("/{pet_id}/stats")
def get_devpet_stats(pet_id: str) -> Dict:
    """Get a DevPet's battle stats and work fingerprint."""
    for fpath in glob.glob(str(DEVPETS_DIR / "*.json")):
        try:
            data = json.loads(Path(fpath).read_text())
            if (data.get("identity", {}).get("developer_id") == pet_id
                    or Path(fpath).stem == pet_id):
                return {
                    "pet_name": data.get("identity", {}).get("pet_name"),
                    "level": data.get("level"),
                    "evolution_stage": data.get("evolution_stage"),
                    "pet_type": data.get("pet_type"),
                    "battle_stats": data.get("battle_stats", {}),
                    "work_fingerprint": data.get("work_fingerprint", {}),
                    "tool_branches": {
                        k: {"tier": v.get("tier"), "xp": v.get("xp"),
                            "signature_moves": v.get("signature_moves", [])}
                        for k, v in data.get("tool_branches", {}).items()
                    },
                }
        except Exception:
            continue
    raise HTTPException(status_code=404, detail=f"DevPet '{pet_id}' not found")


@router.post("/generate")
def generate_devpet(req: DevPetGenerateRequest) -> Dict:
    """Generate a .devpet file from the trace database."""
    from devpet.tracker import DevPetTracker
    from devpet.export import save_devpet_file

    tracker = DevPetTracker(db_path=req.db_path, pet_name=req.pet_name)
    pet = tracker.process_events()
    tracker.close()

    path = DEVPETS_DIR / f"{pet.developer_id}.json"
    save_devpet_file(pet, str(path))

    event_bus.emit("devpet_generated",
        pet_name=pet.pet_name, developer_id=pet.developer_id,
        level=pet.level, evolution_stage=pet.evolution_stage)

    return {
        "pet_name": pet.pet_name, "species": pet.species,
        "level": pet.level, "evolution_stage": pet.evolution_stage,
        "battle_stats": pet.battle_stats.to_dict(), "file": str(path),
    }


@router.post("/{pet_id}/image")
async def upload_devpet_image(pet_id: str, image: UploadFile = File(...)) -> Dict:
    """Upload card art for a DevPet."""
    for fpath in glob.glob(str(DEVPETS_DIR / "*.json")):
        try:
            data = json.loads(Path(fpath).read_text())
            if data.get("identity", {}).get("developer_id") == pet_id:
                break
        except Exception:
            continue
    else:
        raise HTTPException(status_code=404, detail=f"DevPet '{pet_id}' not found")

    img_dir = DEVPETS_DIR / "images"
    img_dir.mkdir(exist_ok=True)
    ext = Path(image.filename or "card.png").suffix or ".png"
    img_path = img_dir / f"{pet_id}{ext}"
    img_path.write_bytes(await image.read())

    return {"status": "ok", "image_path": str(img_path)}
