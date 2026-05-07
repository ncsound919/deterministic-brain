from __future__ import annotations
"""
DOWNLOAD_USER_SETTINGS — Remote settings sync.

Syncs user/team settings from a remote URL (JSON endpoint or GitHub Gist)
to the local .brain_settings.json file. Settings are merged with
local config, with remote values taking precedence.
"""
import json
import os
from pathlib import Path
from datetime import datetime

_LOCAL_SETTINGS = Path(os.getenv('SETTINGS_PATH', '.brain_settings.json'))
_REMOTE_URL = os.getenv('SETTINGS_REMOTE_URL', '')


def _load_local() -> dict:
    if _LOCAL_SETTINGS.exists():
        return json.loads(_LOCAL_SETTINGS.read_text())
    return {}


def _save_local(settings: dict) -> None:
    settings['_synced_at'] = datetime.utcnow().isoformat()
    _LOCAL_SETTINGS.write_text(json.dumps(settings, indent=2))


def sync(remote_url: str | None = None) -> dict:
    url = remote_url or _REMOTE_URL
    if not url:
        return {'error': 'SETTINGS_REMOTE_URL not configured'}
    try:
        import httpx
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        remote = resp.json()
    except Exception as exc:
        return {'error': str(exc)}
    local = _load_local()
    merged = {**local, **remote}
    _save_local(merged)
    return {'status': 'synced', 'keys': list(remote.keys()), 'merged_keys': list(merged.keys())}


def get(key: str, default=None):
    return _load_local().get(key, default)


def set_local(key: str, value) -> dict:
    settings = _load_local()
    settings[key] = value
    _save_local(settings)
    return {'key': key, 'value': value}


def all_settings() -> dict:
    return _load_local()
