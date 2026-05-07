from __future__ import annotations
"""
KAIROS_CHANNELS — Channel notifications.

Sends brain output summaries to configured notification channels:
- Slack (via webhook)
- Discord (via webhook)
- Email (via SMTP)
- Custom webhook

Each channel is configured via environment variables.
"""
import json
import os
from datetime import datetime
from typing import Any

_SLACK_WEBHOOK   = os.getenv('KAIROS_SLACK_WEBHOOK', '')
_DISCORD_WEBHOOK = os.getenv('KAIROS_DISCORD_WEBHOOK', '')
_CUSTOM_WEBHOOK  = os.getenv('KAIROS_CUSTOM_WEBHOOK', '')


def _post(url: str, payload: dict) -> dict:
    try:
        import httpx
        resp = httpx.post(url, json=payload, timeout=10)
        return {'status': resp.status_code, 'ok': resp.is_success}
    except Exception as exc:
        return {'error': str(exc)}


def notify_slack(message: str, channel: str = '#general') -> dict:
    if not _SLACK_WEBHOOK:
        return {'skipped': 'KAIROS_SLACK_WEBHOOK not set'}
    return _post(_SLACK_WEBHOOK, {'text': message, 'channel': channel})


def notify_discord(message: str) -> dict:
    if not _DISCORD_WEBHOOK:
        return {'skipped': 'KAIROS_DISCORD_WEBHOOK not set'}
    return _post(_DISCORD_WEBHOOK, {'content': message[:2000]})


def notify_custom(payload: dict) -> dict:
    if not _CUSTOM_WEBHOOK:
        return {'skipped': 'KAIROS_CUSTOM_WEBHOOK not set'}
    return _post(_CUSTOM_WEBHOOK, payload)


def broadcast(result: dict, channels: list[str] | None = None) -> dict:
    """Broadcast a brain result summary to all configured channels."""
    summary = (
        f'🧠 Brain Result | Lane: {result.get("lane", "?")} | '
        f'Confidence: {result.get("confidence", 0):.0%}\n'
        f'{result.get("final_output", "")[:300]}'
    )
    report: dict[str, Any] = {'ts': datetime.utcnow().isoformat()}
    report['slack']   = notify_slack(summary)
    report['discord'] = notify_discord(summary)
    if _CUSTOM_WEBHOOK:
        report['custom'] = notify_custom({'summary': summary, 'result': result})
    return report
