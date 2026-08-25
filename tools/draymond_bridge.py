"""
Draymond Bridge — Interconnects the Deterministic Brain with the Uplift Ecosystem.

Parses the Draymond registry (seed.ts) for entity metadata and enables real
cross-agent invocation + reporting:

  - `invoke(slug, payload, path)`  — live HTTP dispatch to a Draymond endpoint
    (default: the agent entity invoke route) so the brain can trigger Draymond
    entities/chains. Signed with the CRON_SECRET bearer when configured.
  - `report(...)` / `report_to_openchat(...)` — push a brain report through
    Draymond's Open-Chat connection (same ntfy topics Draymond uses).

Degrades gracefully: if Draymond is unreachable or unconfigured, returns an
error-shaped result and never throws.
"""
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from tools.ntfy import notify_openchat, report_brain  # type: ignore


def _draymond_url() -> str:
    return (os.environ.get("DRAYMOND_URL") or "http://localhost:3444").rstrip("/")


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    secret = os.environ.get("DRAYMOND_CRON_SECRET")
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    return headers


def _default_draymond_path() -> str:
    """Resolve the Draymond repo root for registry parsing.

    The brain lives at `<repo>/Draymond-Orchestrator/agents/deterministic-brain`,
    so the Draymond root is two levels up. `DRAYMOND_REGISTRY` (a seed.ts path)
    or `DRAYMOND_PATH` (a repo root) override it.
    """
    env_reg = os.environ.get("DRAYMOND_REGISTRY")
    if env_reg:
        return env_reg
    env_root = os.environ.get("DRAYMOND_PATH")
    if env_root:
        return os.path.join(env_root, "src/lib/draymond/seed.ts")
    # The brain lives at <Draymond-root>/agents/deterministic-brain, so parents[3]
    # IS the Draymond root. Fall back to the repo root layout when launched from
    # the ecosystem root (parents[4]) or a shallow cwd.
    candidates = [
        Path(__file__).resolve().parents[3] / "src" / "lib" / "draymond" / "seed.ts",
        Path(__file__).resolve().parents[4] / "Draymond-Orchestrator" / "src" / "lib" / "draymond" / "seed.ts",
        Path.cwd() / "Draymond-Orchestrator" / "src" / "lib" / "draymond" / "seed.ts",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return str(candidates[0])


class DraymondBridge:
    def __init__(self, draymond_path: str | None = None):
        self.base_path = draymond_path or ""
        self.registry_file = draymond_path or _default_draymond_path()
        self.entities: Dict[str, Dict] = {}
        self._load_registry()

    def _load_registry(self):
        """Parse seed.ts to extract agent/tool/skill metadata."""
        if not os.path.exists(self.registry_file):
            return

        try:
            with open(self.registry_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Extract blocks of entities using a simplified regex (heuristic).
            entity_pattern = re.compile(
                r'{\s*name:\s*\'(.*?)\',\s*slug:\s*\'(.*?)\',\s*kind:\s*\'(.*?)\',\s*description:\s*\'(.*?)\'',
                re.DOTALL,
            )
            for name, slug, kind, desc in entity_pattern.findall(content):
                self.entities[slug] = {
                    "name": name,
                    "kind": kind,
                    "description": desc.replace("\n", " ").strip(),
                    "source": "draymond",
                }
        except Exception:
            self.entities = {}

    def list_entities(self, kind: Optional[str] = None) -> List[Dict]:
        if kind:
            return [e for e in self.entities.values() if e["kind"] == kind]
        return list(self.entities.values())

    def invoke(self, slug: str, payload: Optional[Dict] = None, path: Optional[str] = None) -> Dict:
        """Live HTTP dispatch to Draymond.

        With `path` set, POST to `{DRAYMOND_URL}{path}` with `payload` (used to
        hit a specific route, e.g. /api/ops/brain). Otherwise POST to the agent
        entity invoke route `{DRAYMOND_URL}/api/agents/{slug}/invoke`. Always
        fail-soft: unreachable/unconfigured Draymond returns an error dict.
        """
        base = _draymond_url()
        body = dict(payload or {})
        if path:
            url = f"{base}{path if path.startswith('/') else '/' + path}"
        else:
            url = f"{base}/api/agents/{slug}/invoke"
            body.setdefault("description", body.get("query", ""))

        data = json.dumps(body).encode()
        req = Request(url, data=data, method="POST", headers=_headers())
        try:
            with urlopen(req, timeout=30) as resp:
                raw = resp.read().decode(errors="ignore")
                try:
                    result = json.loads(raw)
                except json.JSONDecodeError:
                    result = {"body": raw[:20000]}
                return {"status": "ok", "status_code": getattr(resp, "status", 200),
                        "entity": slug, "result": result}
        except HTTPError as exc:
            raw = exc.read().decode(errors="ignore")
            return {"status": "error", "status_code": exc.code, "entity": slug,
                    "error": f"HTTP {exc.code}", "detail": raw[:20000]}
        except (URLError, OSError) as exc:
            return {"status": "error", "entity": slug, "error": str(exc)}

    def report(self, task: str, summary: str, level: str = "info", speak: bool = False) -> Dict:
        """Send a brain report to the operator through Draymond's Open-Chat."""
        return report_brain(task, summary, level=level, speak=speak)

    def report_to_openchat(self, title: str, message: str, speak: bool = False, tags: Optional[List[str]] = None) -> Dict:
        """Publish a message directly to the Open-Chat Fleet Alerts topic."""
        return notify_openchat(title, message, tags=tags, speak=speak)


# Singleton instance
_BRIDGE: Optional[DraymondBridge] = None


def get_draymond_bridge() -> DraymondBridge:
    global _BRIDGE
    if _BRIDGE is None:
        _BRIDGE = DraymondBridge()
    return _BRIDGE
