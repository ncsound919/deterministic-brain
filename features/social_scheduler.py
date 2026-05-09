"""Social Media Scheduler — queue posts, auto-post via browser.

Supports: Twitter/X, LinkedIn, Reddit, Discord webhooks.
Posts are queued with scheduled times and executed via the browser.
"""
from __future__ import annotations
import json
import os
import time
import hashlib
import urllib.request
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


PLATFORMS = ["twitter", "linkedin", "reddit", "discord", "slack"]


@dataclass
class SocialPost:
    id: str
    platform: str
    content: str
    scheduled_for: float         # unix timestamp
    status: str = "queued"       # queued | posted | failed
    media_url: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    posted_at: float = 0
    result: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "id": self.id, "platform": self.platform, "content": self.content,
            "scheduled_for": self.scheduled_for, "status": self.status,
            "media_url": self.media_url, "tags": self.tags,
            "created_at": self.created_at, "posted_at": self.posted_at,
        }


class SocialScheduler:
    def __init__(self, db_path: str = "social_posts.json"):
        self.db_path = db_path
        self.posts: Dict[str, SocialPost] = {}
        self.webhooks: Dict[str, str] = {}    # platform → webhook URL
        self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path) as f:
                    data = json.load(f)
                for item in data.get("posts", []):
                    p = SocialPost(**item)
                    self.posts[p.id] = p
                self.webhooks = data.get("webhooks", {})
            except Exception:
                pass

    def _save(self):
        with open(self.db_path, "w") as f:
            json.dump({
                "posts": [p.to_dict() for p in self.posts.values()],
                "webhooks": self.webhooks,
            }, f, indent=2)

    def schedule(self, platform: str, content: str, delay_minutes: int = 0,
                 media_url: str = "", tags: List[str] = None) -> SocialPost:
        pid = hashlib.sha256((platform + content + str(time.time())).encode()).hexdigest()[:12]
        scheduled = time.time() + delay_minutes * 60
        p = SocialPost(
            id=pid, platform=platform, content=content,
            scheduled_for=scheduled, media_url=media_url, tags=tags or [],
        )
        self.posts[pid] = p
        self._save()
        return p

    def get_due(self) -> List[SocialPost]:
        now = time.time()
        return [p for p in self.posts.values()
                if p.status == "queued" and p.scheduled_for <= now]

    def mark_posted(self, post_id: str, result: Dict = None):
        if post_id in self.posts:
            self.posts[post_id].status = "posted"
            self.posts[post_id].posted_at = time.time()
            if result:
                self.posts[post_id].result = result
            self._save()

    def mark_failed(self, post_id: str, error: str = ""):
        if post_id in self.posts:
            self.posts[post_id].status = "failed"
            self.posts[post_id].result = {"error": error}
            self._save()

    def list_all(self) -> List[SocialPost]:
        return sorted(self.posts.values(), key=lambda x: x.scheduled_for)

    def set_webhook(self, platform: str, url: str):
        self.webhooks[platform] = url
        self._save()

    def post_via_webhook(self, post: SocialPost) -> Dict:
        """Post to Discord/Slack via webhook."""
        webhook_url = self.webhooks.get(post.platform, "")
        if not webhook_url:
            return {"error": f"no webhook for {post.platform}"}
        try:
            body = json.dumps({"content": post.content}).encode()
            req = urllib.request.Request(
                webhook_url, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "DeterministicBrain/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                return {"status": "ok", "code": r.status}
        except Exception as e:
            return {"error": str(e)}

    def generate_content(self, topic: str, platform: str) -> str:
        """Generate post content from topic (deterministic, no LLM)."""
        templates = {
            "twitter": f"Just shipped: {topic} 🚀 Built with @deterministic_brain #buildinpublic #indiedev",
            "linkedin": f"Excited to share what I've been working on: {topic}. Built entirely with deterministic AI tooling — no black boxes, just reproducible code.\n\n#softwareengineering #ai",
            "reddit": f"[Project] {topic}\n\nJust finished building {topic}. Would love feedback from the community!\n\nTech stack: Python, React, FastAPI",
        }
        return templates.get(platform, f"Check out: {topic}")


_SCHEDULER: Optional[SocialScheduler] = None


def get_social() -> SocialScheduler:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = SocialScheduler()
    return _SCHEDULER
