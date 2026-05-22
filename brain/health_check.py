"""Startup health check — validates critical dependencies at boot time.

Call `run_health_check()` at startup to surface missing packages,
misconfigured settings, and environment issues before the system
attempts to serve requests.
"""

from __future__ import annotations
import importlib
import logging
import os
import sys
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class HealthResult:
    passed: bool = True
    checks: List[dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


# ── Required packages (core functionality) ─────────────────────
CORE_PACKAGES = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "yaml",
    "httpx",
    "jinja2",
    "cryptography",
    "numpy",
]

# ── Optional packages (features degrade gracefully) ────────────
OPTIONAL_PACKAGES = [
    "qdrant_client",
    "neo4j",
    "sentence_transformers",
    "anthropic",
    "openai",
    "playwright",
    "loguru",
    "apscheduler",
    "faster_whisper",
    "pandas",
    "PIL",
    "sklearn",
]


def _check_import(name: str) -> bool:
    try:
        importlib.import_module(name)
        return True
    except ImportError:
        return False


def _check_env_var(key: str) -> bool:
    return bool(os.getenv(key))


def run_health_check() -> HealthResult:
    """Run all health checks and return structured results."""
    result = HealthResult()

    # ── Python version ───────────────────────────────────────────
    py_version = sys.version_info
    if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 10):
        result.errors.append(
            f"Python 3.10+ required, found {py_version.major}.{py_version.minor}"
        )
    else:
        result.checks.append({
            "check": "python_version",
            "status": "ok",
            "detail": f"{py_version.major}.{py_version.minor}.{py_version.micro}",
        })

    # ── Core packages ────────────────────────────────────────────
    for pkg in CORE_PACKAGES:
        if _check_import(pkg):
            result.checks.append({"check": f"pkg:{pkg}", "status": "ok"})
        else:
            result.errors.append(f"Missing core package: {pkg} (pip install {pkg})")
            result.checks.append({"check": f"pkg:{pkg}", "status": "missing"})

    # ── Optional packages ────────────────────────────────────────
    for pkg in OPTIONAL_PACKAGES:
        if _check_import(pkg):
            result.checks.append({"check": f"pkg:{pkg}", "status": "ok"})
        else:
            result.warnings.append(f"Optional package not installed: {pkg}")
            result.checks.append({"check": f"pkg:{pkg}", "status": "optional"})

    # ── Critical env vars ────────────────────────────────────────
    if _check_env_var("OPENROUTER_API_KEY"):
        result.checks.append({"check": "env:OPENROUTER_API_KEY", "status": "ok"})
    else:
        result.warnings.append("OPENROUTER_API_KEY not set — LLM features disabled")

    if _check_env_var("ANTHROPIC_API_KEY"):
        result.checks.append({"check": "env:ANTHROPIC_API_KEY", "status": "ok"})
    else:
        result.checks.append({"check": "env:ANTHROPIC_API_KEY", "status": "optional"})

    # ── Qdrant ───────────────────────────────────────────────────
    qdrant_url = os.getenv("QDRANT_URL", "")
    if qdrant_url:
        result.checks.append({"check": "qdrant_url", "status": "ok", "detail": qdrant_url})
    else:
        result.warnings.append("QDRANT_URL not set — vector search disabled")

    # ── .soul.yaml ───────────────────────────────────────────────
    soul_path = os.getenv("SOUL_PATH", ".soul.yaml")
    if os.path.exists(soul_path):
        result.checks.append({"check": "soul_config", "status": "ok"})
    else:
        result.warnings.append(
            f"{soul_path} not found — copy .soul.yaml.example to configure"
        )

    # ── Summary ──────────────────────────────────────────────────
    result.passed = len(result.errors) == 0
    return result


def print_health_report(result: HealthResult) -> None:
    """Print a formatted health report to stderr."""
    if result.passed:
        print("\n[HEALTH] All core checks passed.", file=sys.stderr)
    else:
        print(f"\n[HEALTH] {len(result.errors)} error(s) found:", file=sys.stderr)
        for err in result.errors:
            print(f"  ! {err}", file=sys.stderr)

    if result.warnings:
        print(f"\n[HEALTH] {len(result.warnings)} warning(s):", file=sys.stderr)
        for w in result.warnings:
            print(f"  ? {w}", file=sys.stderr)

    print(f"\n[HEALTH] {len(result.checks)} checks run", file=sys.stderr)


if __name__ == "__main__":
    result = run_health_check()
    print_health_report(result)
    sys.exit(0 if result.passed else 1)
