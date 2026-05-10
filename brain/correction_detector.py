"""Correction detector — identifies regressions, drifts, and config errors.

Compares current skill execution outcomes against historical patterns to detect
anomalies that need healing. Writes corrections to .autodream_corrections.jsonl
for the runtime healer to process.
"""

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CORRECTIONS_FILE = Path(".autodream_corrections.jsonl")


def detect_corrections(session_trace: List[Dict]) -> List[Dict]:
    """Analyze session traces and detect correction-worthy anomalies.

    Args:
        session_trace: List of skill execution records from traces.db.
            Each record has: skill, status, timestamp, error (if any)

    Returns:
        List of correction dicts to be written to .autodream_corrections.jsonl
    """
    corrections = []
    error_skills = {}
    partial_skills = {}

    for entry in session_trace:
        skill = entry.get("skill", "unknown")
        status = entry.get("status", "unknown")

        if status == "error":
            if skill not in error_skills:
                error_skills[skill] = []
            error_skills[skill].append(entry)
        elif status == "partial":
            if skill not in partial_skills:
                partial_skills[skill] = []
            partial_skills[skill].append(entry)

    for skill, errors in error_skills.items():
        if len(errors) >= 1:
            correction = {
                "type": "regression",
                "skill": skill,
                "count": len(errors),
                "reason": f"Skill '{skill}' produced {len(errors)} error(s)",
                "examples": [
                    {
                        "status": e.get("status"),
                        "timestamp": e.get("timestamp", "").isoformat() if isinstance(e.get("timestamp"), datetime) else str(e.get("timestamp", "")),
                    }
                    for e in errors[:3]
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            corrections.append(correction)
            logger.warning("Correction detected: %s - %s", skill, correction["reason"])

    for skill, partials in partial_skills.items():
        if len(partials) >= 3:
            correction = {
                "type": "drift",
                "skill": skill,
                "count": len(partials),
                "reason": f"Skill '{skill}' consistently returning partial (possible drift)",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            corrections.append(correction)
            logger.warning("Drift detected: %s - %s", skill, correction["reason"])

    return corrections


def write_corrections(corrections: List[Dict]) -> int:
    """Append corrections to the corrections file.

    Returns the number of corrections written.
    """
    if not corrections:
        return 0

    try:
        with open(CORRECTIONS_FILE, "a") as f:
            for corr in corrections:
                f.write(json.dumps(corr) + "\n")
        return len(corrections)
    except Exception as e:
        logger.error("Failed to write corrections: %s", e)
        return 0


def run_correction_detection(session_trace: List[Dict]) -> int:
    """Full correction detection pipeline: detect and write.

    Returns number of corrections written.
    """
    corrections = detect_corrections(session_trace)
    return write_corrections(corrections)


def get_recent_corrections(limit: int = 10) -> List[Dict]:
    """Read recent corrections from the corrections file."""
    if not CORRECTIONS_FILE.exists():
        return []

    try:
        lines = CORRECTIONS_FILE.read_text().strip().split("\n")
        corrections = [json.loads(line) for line in lines if line.strip()]
        return corrections[-limit:]
    except Exception as e:
        logger.error("Failed to read corrections: %s", e)
        return []


def clear_corrections() -> None:
    """Clear the corrections file."""
    try:
        if CORRECTIONS_FILE.exists():
            CORRECTIONS_FILE.unlink()
    except Exception as e:
        logger.error("Failed to clear corrections: %s", e)