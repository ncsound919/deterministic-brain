"""Webhook dispatcher — Slack, Discord, Teams, custom endpoints.

Posts deterministic skill results to team communication channels.
Token savings: ~300 tokens per notification vs LLM formatting.
"""

from __future__ import annotations
import json
import os
from typing import Dict, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class WebhookDispatcher:
    """Post structured messages to webhook URLs."""

    def slack(self, text: str, blocks: list = None, channel: str = "",
              username: str = "Deterministic Brain") -> Dict:
        url = os.environ.get("SLACK_WEBHOOK_URL", "")
        if not url:
            return {"ok": False, "error": "SLACK_WEBHOOK_URL not set"}

        payload = {
            "text": text,
            "username": username,
            "icon_emoji": ":brain:",
        }
        if channel:
            payload["channel"] = channel
        if blocks:
            payload["blocks"] = blocks

        return self._send(url, payload)

    def discord(self, content: str, embeds: list = None) -> Dict:
        url = os.environ.get("DISCORD_WEBHOOK_URL", "")
        if not url:
            return {"ok": False, "error": "DISCORD_WEBHOOK_URL not set"}

        payload = {"content": content}
        if embeds:
            payload["embeds"] = embeds

        return self._send(url, payload)

    def teams(self, title: str, text: str, color: str = "0076D7") -> Dict:
        url = os.environ.get("TEAMS_WEBHOOK_URL", "")
        if not url:
            return {"ok": False, "error": "TEAMS_WEBHOOK_URL not set"}

        payload = {
            "@type": "MessageCard",
            "title": title,
            "text": text,
            "themeColor": color,
        }
        return self._send(url, payload)

    def custom(self, url: str, payload: dict) -> Dict:
        return self._send(url, payload)

    def _send(self, url: str, payload: dict) -> Dict:
        data = json.dumps(payload).encode()
        req = Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urlopen(req, timeout=10) as r:
                return {"ok": True, "status": r.status}
        except HTTPError as e:
            return {"ok": False, "error": f"HTTP {e.code}", "status": e.code}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def notify_skill_result(self, skill: str, status: str, details: str = "",
                            channel: str = "slack") -> Dict:
        """Post skill execution result to configured channels."""
        msg = f"*[{status.upper()}]* `{skill}`\n{details}" if details else f"*[{status.upper()}]* `{skill}`"

        if channel in ("slack", "all"):
            r = self.slack(msg)
        if channel in ("discord", "all"):
            r = self.discord(msg)
        if channel in ("teams", "all"):
            r = self.teams(f"Skill: {skill} [{status}]", details or "No details")

        return {"ok": True, "message": msg}
