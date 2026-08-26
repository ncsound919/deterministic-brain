"""ntfy.py — push reports/messages to Open-Chat through the ntfy pub/sub topics.

This is how the deterministic brain "uses Draymond's tools to report and
communicate". Draymond reaches the operator's phone by publishing JSON to an
ntfy topic that the Open-Chat app subscribes to (the topic lives in the JSON
body, posted to the ntfy root URL). This module mirrors Draymond's ntfy.ts
shape exactly, so the brain can:

  - `publish_ntfy(...)`   → low-level publish to any ntfy topic
  - `notify_openchat(...)` → publish to the Fleet Alerts topic (auto-speak with
                             the `call` tag) so the brain's reports land in
                             Open-Chat like Draymond's own recaps/alerts
  - `report_brain(...)`   → high-level "brain → operator" report helper

Deterministic + fail-soft: never throws, returns {ok, ...}. No LLM, no keys.
"""

from __future__ import annotations
import json
import os
from typing import Dict, List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

DEFAULT_NTFY_URL = "https://ntfy.sh"
# Open-Chat "Fleet Alerts" bot (matches Draymond NTFY_TOPIC_RESULTS).
DEFAULT_TOPIC_RESULTS = "ov365-mucwehxf720s"
# Open-Chat "Fleet Recaps" bot (matches Draymond NTFY_TOPIC_RECAPS).
DEFAULT_TOPIC_RECAPS = "ov365-fjuytxa530ml"
# Draymond's approvals topic (Open-Chat "Fleet Approvals" bot).
DEFAULT_TOPIC_APPROVALS = "ov365-yo1b73aleprc"


def _ntfy_url() -> str:
    return (os.environ.get("NTFY_URL") or DEFAULT_NTFY_URL).rstrip("/")


def _topic(env: str, default: str) -> str:
    return os.environ.get(env) or default


def publish_ntfy(
    title: str,
    message: str,
    tags: Optional[List[str]] = None,
    priority: int = 3,
    topic: Optional[str] = None,
    click: Optional[str] = None,
) -> Dict:
    """Publish a JSON message to an ntfy topic (Open-Chat pub/sub stream).

    Mirrors Draymond's ntfy.ts: POST the whole `{topic, title, message,
    priority, tags, click}` object to the ntfy ROOT URL. `tags` drives
    Open-Chat rendering/auto-speak; `click` sets the tap-through URL.
    """
    base = _ntfy_url()
    if not topic:
        return {"ok": False, "error": "topic is required"}
    if not title and not message:
        return {"ok": False, "error": "title and message are both empty"}

    payload = {
        "topic": topic,
        "title": title,
        "message": message,
        "priority": int(priority),
        "tags": tags or [],
    }
    if click:
        payload["click"] = click

    body = json.dumps(payload).encode()
    req = Request(
        base,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=15) as resp:
            status = getattr(resp, "status", 200)
            return {"ok": 200 <= status < 300, "status": status, "topic": topic}
    except HTTPError as exc:
        return {"ok": False, "status": exc.code, "topic": topic, "error": f"HTTP {exc.code}"}
    except (URLError, OSError) as exc:
        return {"ok": False, "topic": topic, "error": str(exc)}


def notify_openchat(
    title: str,
    message: str,
    tags: Optional[List[str]] = None,
    priority: int = 3,
    topic: Optional[str] = None,
    speak: bool = False,
) -> Dict:
    """Publish a report/message to the Open-Chat Fleet Alerts topic.

    Defaults to `NTFY_TOPIC_RESULTS` (the topic Draymond's own
    issues/alerts/recaps land on). When `speak` is True, adds the `call` tag so
    Open-Chat auto-speaks it on the phone (same as Draymond's evening_call_recap).
    """
    effective_tags = list(tags or [])
    if speak and "call" not in effective_tags:
        effective_tags.append("call")
    if "report" not in effective_tags:
        effective_tags.append("report")
    return publish_ntfy(
        title=title,
        message=message,
        tags=effective_tags,
        priority=priority,
        topic=topic or _topic("NTFY_TOPIC_RESULTS", DEFAULT_TOPIC_RESULTS),
        click=os.environ.get("DRAYMOND_PUBLIC_URL"),
    )


def report_brain(
    task: str,
    summary: str,
    level: str = "info",
    speak: bool = False,
    topic: Optional[str] = None,
) -> Dict:
    """High-level 'brain → operator' report through Open-Chat.

    Convenience wrapper: titles the message "Brain · <task>" and tags it with
    the severity level so Open-Chat renders it consistently with fleet alerts.
    """
    title = f"Brain · {task}"
    tags = [level if level in ("info", "ok", "warning", "error") else "info"]
    return notify_openchat(title, summary, tags=tags, speak=speak, topic=topic)
