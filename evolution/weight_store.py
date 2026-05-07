"""Persistent weight storage with version history for skill evolution."""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Dict, List, Optional


class WeightStore:
    """Versioned, persistent store for skill routing weights."""

    def __init__(self, storage_path: str = ".skill_weights.json"):
        self.path = Path(storage_path)
        self._data: Dict = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, default=str))

    def get(self, skill_id: str, default: float = 1.0) -> float:
        entry = self._data.get(skill_id, {})
        w = entry.get("current_weight")
        return default if w is None else w

    def set(self, skill_id: str, weight: float) -> None:
        entry = self._data.setdefault(skill_id, {"current_weight": None, "history": []})
        old = entry["current_weight"]
        if old is not None and old != weight:
            entry["history"].append({
                "version": len(entry["history"]) + 1,
                "weight": weight,
                "ts": time.time(),
            })
            if len(entry["history"]) > 50:
                entry["history"] = entry["history"][-50:]
        entry["current_weight"] = weight
        self._save()

    def history(self, skill_id: str) -> List[Dict]:
        return self._data.get(skill_id, {}).get("history", [])

    def rollback(self, skill_id: str, version: int) -> bool:
        hist = self.history(skill_id)
        if 1 <= version <= len(hist):
            w = hist[version - 1]["weight"]
            self._data[skill_id]["current_weight"] = w
            self._save()
            return True
        return False

    def all_weights(self) -> Dict[str, float]:
        return {k: v.get("current_weight", 1.0) for k, v in self._data.items()}

    def export(self) -> Dict:
        return dict(self._data)

    def import_data(self, data: Dict) -> None:
        self._data = dict(data)
        self._save()
