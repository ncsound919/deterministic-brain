"""Shorthand DSL parser — terse typed intent language for the brain.

Syntax:
    verb:domain[param:value, param:value, ...]

Examples:
    build:web[canvas, pets:2, battle:turnbased, lang:html5]
    build:api[crud, auth:jwt, lang:python, db:postgres]
    create:component[name:BattleCard, lang:tsx, props:{pet, hp, turn}]
    deploy:web[target:vercel, env:prod]
    debug:test[lang:python, framework:pytest]
    scaffold:project[type:rest-api, name:devpets]

No LLM. No grammar library. ~50 lines of pure regex Python.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, Optional


# ── DSL Grammar ────────────────────────────────────────────────

# verb:domain[params]
DSL_PATTERN = re.compile(
    r"^(\w+):(\w+)\[(.*)\]$"
)

# params are comma-separated key:value or bare flags
PARAM_PATTERN = re.compile(
    r'(?:(\w+):([\w{}":.,\-]+)|(\w+))'
)

# Fallback: natural language keyword extraction
VERB_KEYWORDS = {
    "build": 0.9, "create": 0.9, "scaffold": 0.8,
    "deploy": 0.8, "debug": 0.7, "test": 0.7,
    "fix": 0.7, "generate": 0.7, "analyze": 0.7,
    "design": 0.6, "write": 0.6, "add": 0.5,
    "audit": 0.6, "review": 0.3, "run": 0.4,
}
DOMAIN_KEYWORDS = {
    "web": 0.9, "api": 0.9, "component": 0.8, "function": 0.7,
    "dockerfile": 0.8, "test": 0.7, "website": 0.8,
    "rest": 0.8, "graphql": 0.8, "database": 0.7,
    "auth": 0.7, "deploy": 0.7, "notebook": 0.6,
    "design": 0.6, "canvas": 0.7, "pdf": 0.6,
}


@dataclass
class IntentToken:
    """Canonical intent extracted from shorthand or natural language."""
    verb: str = ""
    domain: str = ""
    params: Dict[str, str] = field(default_factory=dict)
    raw: str = ""
    is_shorthand: bool = False
    confidence: float = 0.0


class ShorthandParser:
    """Parse shorthand DSL and natural language into IntentToken."""

    def parse(self, text: str) -> IntentToken:
        text = text.strip()

        # Attempt DSL parse
        token = self._try_dsl(text)
        if token:
            token.raw = text
            token.is_shorthand = True
            token.confidence = 0.95
            return token

        # Fallback: keyword extraction from natural language
        return self._extract_keywords(text)

    def _try_dsl(self, text: str) -> Optional[IntentToken]:
        m = DSL_PATTERN.match(text)
        if not m:
            return None

        verb = m.group(1).lower()
        domain = m.group(2).lower()
        params_str = m.group(3).strip()

        params = {}
        if params_str:
            for pm in PARAM_PATTERN.finditer(params_str):
                if pm.group(1):  # key:value pair
                    key = pm.group(1)
                    val = pm.group(2).strip("'\"")
                    params[key] = val
                elif pm.group(3):  # bare flag
                    params[pm.group(3)] = "true"

        return IntentToken(verb=verb, domain=domain, params=params)

    def _extract_keywords(self, text: str) -> IntentToken:
        """Extract verb + domain from natural language via keyword scoring."""
        text_lower = text.lower()

        verb = ""
        verb_conf = 0.0
        for v, c in VERB_KEYWORDS.items():
            if v in text_lower and c > verb_conf:
                verb = v
                verb_conf = c

        domain = ""
        domain_conf = 0.0
        for d, c in DOMAIN_KEYWORDS.items():
            if d in text_lower and c > domain_conf:
                domain = d
                domain_conf = c

        return IntentToken(
            verb=verb,
            domain=domain,
            raw=text,
            confidence=(verb_conf + domain_conf) / 2.0,
        )


# ── Intent → Skill mapping ─────────────────────────────────────

INTENT_TO_SKILL = {
    ("build", "web"): "web-artifacts-builder",
    ("build", "api"): "scaffold-rest-api",
    ("build", "rest"): "scaffold-rest-api",
    ("create", "component"): "create-react-component",
    ("scaffold", "project"): "scaffold-rest-api",
    ("deploy", "web"): "vercel-deploy",
    ("build", "dockerfile"): "generate-dockerfile",
    ("debug", "test"): "systematic-debugging",
    ("design", "canvas"): "canvas-design",
    ("design", "web"): "frontend-design",
    ("write", "test"): "test-driven-development",
    ("analyze", "web"): "webapp-testing",
    ("build", "canvas"): "canvas-design",
    ("build", "website"): "web-artifacts-builder",
    ("design", "website"): "frontend-design",
    ("create", "notebook"): "jupyter-notebook",
    ("create", "pdf"): "pdf",
}


def intent_to_skill(token: IntentToken) -> Optional[str]:
    """Map an IntentToken to a known skill ID."""
    return INTENT_TO_SKILL.get((token.verb, token.domain))
