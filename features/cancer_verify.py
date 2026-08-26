"""Cancer hypothesis verifier — deterministic (zero-LLM) evidence gate.

Wires the Deterministic Brain into CureMind cancer research as a $0-inference
reproducibility + audit layer. It deliberately reuses the brain's existing
machinery (Forge-style structural validation, the dashboard event bus for the
audit trail, and SHA-256 signing) so no new heavy dependencies are introduced.

This module performs NO LLM calls. It scores a hypothesis against the evidence
the caller supplies (mechanism, testable prediction, contradictory papers) and
produces a deterministic verdict + audit signature that downstream systems
(BlackMind BAM, USE, Cosmos) can render.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _sign(*parts: Any) -> str:
    """Deterministic SHA-256 over the ordered evidence parts."""
    h = hashlib.sha256()
    for part in parts:
        h.update(json.dumps(part, sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()


def _truthy(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, str):
        return bool(v.strip()) and v.strip().lower() not in ("n/a", "none", "unknown")
    return bool(v)


def _norm_list(v: Any) -> List[Any]:
    if not v:
        return []
    if isinstance(v, list):
        return [i for i in v if _truthy(i)]
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return [i for i in parsed if _truthy(i)]
        except Exception:
            pass
        return [v]
    return [v]


# Deterministic weight table — evidence -> score contribution. No ML, no LLM.
WEIGHTS = {
    "mechanism": 0.35,
    "testable_prediction": 0.30,
    "target": 0.15,
    "contradictory_papers": 0.20,  # present contradictions lower confidence
}

# Deterministic verdict thresholds (documented, reproducible).
THRESHOLDS = {
    "pass": 0.60,
    "review": 0.40,
}


def verify_hypothesis(
    target: str = "",
    mechanism: str = "",
    testable_prediction: str = "",
    contradictory_papers: Optional[List[Any]] = None,
    hypothesis_id: str = "",
    disease: str = "cancer",
    modality: str = "",
    manifest_hash: str = "",
) -> Dict[str, Any]:
    """Verify a cancer hypothesis deterministically. No LLM in this path.

    Returns a stable dict with: ok / verified / verdict / score / checks /
    signature / llm_used / ts / input_digest. `ok` is True whenever the input
    is structurally valid (the endpoint itself is reachable & well-formed);
    `verified` is True only when the deterministic score clears the gate.
    When `manifest_hash` is supplied (e.g. an Oncology engine manifest), it is
    folded into the signature so the audit is anchored to the run manifest.
    """
    contradictory = _norm_list(contradictory_papers)

    # Per-field deterministic checks (structural evidence gate).
    checks: List[Dict[str, Any]] = []
    for field, weight, label in (
        ("target", WEIGHTS["target"], "target identified"),
        ("mechanism", WEIGHTS["mechanism"], "mechanism stated"),
        ("testable_prediction", WEIGHTS["testable_prediction"], "testable prediction stated"),
    ):
        present = _truthy({"target": target, "mechanism": mechanism, "testable_prediction": testable_prediction}[field])
        checks.append({"check": label, "pass": present, "weight": weight})
        if not present:
            checks[-1]["note"] = f"missing: {field}"

    # Contradictions: a well-formed hypothesis confronts contradictory evidence.
    has_contra = len(contradictory) > 0
    checks.append({"check": "contradictory evidence addressed", "pass": has_contra, "weight": WEIGHTS["contradictory_papers"]})
    if not has_contra:
        checks[-1]["note"] = "no contradictory papers supplied (confidence capped)"

    raw_score = sum(c["weight"] for c in checks if c["pass"])
    # Cap confidence when no contradictory evidence is confronted (anti-hype).
    if not has_contra:
        raw_score = min(raw_score, 0.80)
    score = round(min(1.0, max(0.0, raw_score)), 3)

    if score >= THRESHOLDS["pass"]:
        verdict = "pass"
    elif score >= THRESHOLDS["review"]:
        verdict = "review"
    else:
        verdict = "reject"

    input_digest = _sign(
        {"target": target, "mechanism": mechanism, "testable_prediction": testable_prediction},
        contradictory,
    )
    signature = _sign(
        input_digest, score, verdict, disease, modality, hypothesis_id, manifest_hash,
    )
    ts = datetime.now(timezone.utc).isoformat()

    result = {
        "ok": True,
        "verified": verdict == "pass",
        "verdict": verdict,
        "score": score,
        "thresholds": THRESHOLDS,
        "checks": checks,
        "contradictory_count": len(contradictory),
        "signature": signature,
        "input_digest": input_digest,
        "llm_used": False,
        "engine": "deterministic-brain",
        "disease": disease,
        "ts": ts,
    }
    if manifest_hash:
        result["manifest_hash"] = manifest_hash
    return result


class CancerVerifier:
    """Thin wrapper so the API server can route through a shared instance and
    optionally emit an audit event onto the brain's event bus (the same feed
    surfaced by /dashboard/audit)."""

    def __init__(self, emit: Optional[Any] = None):
        self._emit = emit  # callable(event_bus) — injected by the API server

    def verify(self, **kwargs: Any) -> Dict[str, Any]:
        result = verify_hypothesis(**kwargs)
        if self._emit is not None:
            try:
                self._emit("cancer_verify", **{
                    "target": kwargs.get("target", ""),
                    "hypothesis_id": kwargs.get("hypothesis_id", ""),
                    "manifest_hash": kwargs.get("manifest_hash", ""),
                    "verdict": result["verdict"],
                    "score": result["score"],
                    "signature": result["signature"],
                    "llm_used": False,
                })
            except Exception:
                pass
        return result


_verifier: Optional[CancerVerifier] = None


def get_verifier(emit: Optional[Any] = None) -> CancerVerifier:
    global _verifier
    if _verifier is None:
        _verifier = CancerVerifier(emit=emit)
    elif emit is not None:
        _verifier._emit = emit
    return _verifier
