from __future__ import annotations
"""
Feature flag registry for deterministic-brain.

All 22 features ported from the Uplift Code feature flag system.
Enable/disable any feature via environment variables:

    FEATURE_KAIROS=true
    FEATURE_PROACTIVE=true
    ... etc

Or enable all at once:
    FEATURES_ALL=true
"""
import os

ALL_FLAGS = [
    'KAIROS',
    'PROACTIVE',
    'BRIDGE_MODE',
    'VOICE_MODE',
    'COORDINATOR_MODE',
    'TRANSCRIPT_CLASSIFIER',
    'BASH_CLASSIFIER',
    'BUDDY',
    'WEB_BROWSER_TOOL',
    'CHICAGO_MCP',
    'AGENT_TRIGGERS',
    'ULTRAPLAN',
    'MONITOR_TOOL',
    'TEAMMEM',
    'EXTRACT_MEMORIES',
    'MCP_SKILLS',
    'REVIEW_ARTIFACT',
    'CONNECTOR_TEXT',
    'DOWNLOAD_USER_SETTINGS',
    'MESSAGE_ACTIONS',
    'KAIROS_CHANNELS',
    'KAIROS_GITHUB_WEBHOOKS',
]

_FEATURES_ALL = os.getenv('FEATURES_ALL', 'false').lower() == 'true'

_ENABLED: set[str] = set()
for _f in ALL_FLAGS:
    if _FEATURES_ALL or os.getenv(f'FEATURE_{_f}', 'false').lower() == 'true':
        _ENABLED.add(_f)


def is_enabled(flag: str) -> bool:
    return flag in _ENABLED


def enabled_list() -> list[str]:
    return sorted(_ENABLED)


def all_flags() -> dict[str, bool]:
    return {f: f in _ENABLED for f in ALL_FLAGS}
