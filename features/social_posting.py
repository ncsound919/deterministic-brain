"""Social Media Posting — real browser-based posting for all platforms.

Platforms supported:
  - Facebook   — browser login + post
  - Instagram  — browser login + post
  - TikTok     — browser login + post
  - X/Twitter  — browser login + tweet
  - Discord    — webhook (already works)

Uses LiveBrowser (Playwright) for platforms requiring browser automation.
Cookies are persisted in .browser_sessions/ so login happens once.

Credentials are read from the encrypted credential vault under the
'social' category.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.vault_aware_api import get_key

logger = logging.getLogger(__name__)

# ── Platform configs ──────────────────────────────────────────────────

PLATFORM_CONFIG = {
    "facebook": {
        "name": "Facebook",
        "login_url": "https://www.facebook.com/login",
        "home_url": "https://www.facebook.com",
        "post_url": "https://www.facebook.com",
        "username_sel": 'input[name="email"]',
        "password_sel": 'input[name="pass"]',
        "submit_sel": 'button[name="login"]',
        "post_trigger": 'div[aria-label="What\'s on your mind?"], div[aria-label="Create a post"]',
        "post_box": 'div[aria-label="What\'s on your mind?"][contenteditable="true"], div[contenteditable="true"][role="textbox"]',
        "post_submit": 'div[aria-label="Post"]:not([aria-disabled="true"]), div[aria-label="Post" i]',
        "success_indicator": '[aria-label="Facebook"]',
    },
    "instagram": {
        "name": "Instagram",
        "login_url": "https://www.instagram.com/accounts/login/",
        "home_url": "https://www.instagram.com",
        "post_url": "https://www.instagram.com",
        "username_sel": 'input[name="username"]',
        "password_sel": 'input[name="password"]',
        "submit_sel": 'button[type="submit"]',
        "post_trigger": 'svg[aria-label="New post"], a[href*="/create"]',
        "post_box": 'div[contenteditable="true"]',
        "post_submit": 'div[role="button"]:has-text("Share"), button:has-text("Share")',
        "success_indicator": 'svg[aria-label="Home"]',
        "extra_click": None,
    },
    "tiktok": {
        "name": "TikTok",
        "login_url": "https://www.tiktok.com/login",
        "home_url": "https://www.tiktok.com",
        "post_url": "https://www.tiktok.com/upload",
        "username_sel": 'input[name="username"], input[type="text"]',
        "password_sel": 'input[type="password"]',
        "submit_sel": 'button[type="submit"]',
        "post_trigger": 'a[href*="/upload"], button:has-text("Upload")',
        "post_box": 'div[contenteditable="true"], textarea',
        "post_submit": 'button:has-text("Post")',
        "success_indicator": 'div[data-e2e="recommend-list"]',
        "extra_click": None,
    },
    "x": {
        "name": "X / Twitter",
        "login_url": "https://x.com/login",
        "home_url": "https://x.com",
        "post_url": "https://x.com/compose/post",
        "username_sel": 'input[autocomplete="username"], input[name="text"]',
        "password_sel": 'input[type="password"]',
        "submit_sel": 'button[data-testid*="Login"] div, div[role="button"]:has-text("Next"), button:has-text("Log in")',
        "next_btn": 'div[role="button"]:has-text("Next"), button:has-text("Next")',
        "post_trigger": 'a[aria-label="Post"], a[href="/compose/post"]',
        "post_box": 'div[data-testid="tweetTextarea_0"] div[contenteditable="true"], div[contenteditable="true"][role="textbox"]',
        "post_submit": 'button[data-testid="tweetButton"]',
        "success_indicator": 'a[data-testid="AppTabBar_Home_Link"]',
        "extra_click": None,
    },
}


class SocialPoster:
    """Posts to Facebook, Instagram, TikTok, and X via browser automation.
    Discord uses webhooks (existing implementation).

    Login state is cached via browser cookies in .browser_sessions/.
    """

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._browser: Any = None
        self._logged_in: Dict[str, bool] = {}

    def _ensure_browser(self):
        if self._browser is None:
            from tools.browser.live_controller import LiveBrowser
            self._browser = LiveBrowser(headless=self._headless)
            self._browser.__enter__()
        return self._browser

    def close(self):
        if self._browser:
            self._browser.__exit__(None, None, None)
            self._browser = None

    # ── Credential resolution ──────────────────────────────────────

    def _get_credentials(self, platform: str) -> Dict[str, str]:
        return {
            "username": get_key(
                vault_category="social", vault_key=f"{platform}_username",
                env_var=f"{platform.upper()}_USERNAME",
            ),
            "password": get_key(
                vault_category="social", vault_key=f"{platform}_password",
                env_var=f"{platform.upper()}_PASSWORD",
            ),
            "email": get_key(
                vault_category="social", vault_key=f"{platform}_email",
                env_var=f"{platform.upper()}_EMAIL",
            ),
        }

    # ── Login ───────────────────────────────────────────────────────

    def login(self, platform: str) -> Dict:
        """Log into a platform via browser. Persists cookies on success."""
        cfg = PLATFORM_CONFIG.get(platform)
        if not cfg:
            return {"ok": False, "error": f"Unknown platform: {platform}"}

        creds = self._get_credentials(platform)
        username = creds.get("email") or creds.get("username")
        password = creds.get("password")

        if not username or not password:
            return {
                "ok": False, "platform": platform,
                "error": f"No credentials stored for {platform}. "
                         f"Add to vault: vault.set('social', '{platform}_username', '...') "
                         f"and vault.set('social', '{platform}_password', '...')",
            }

        browser = self._ensure_browser()

        result = browser.login(
            platform=platform,
            login_url=cfg["login_url"],
            username=username,
            password=password,
            username_sel=cfg["username_sel"],
            password_sel=cfg["password_sel"],
            submit_sel=cfg["submit_sel"],
            extra_click=cfg.get("extra_click"),
            wait_after_login=6,
        )

        if result.get("ok"):
            self._logged_in[platform] = True
            logger.info(f"Logged into {cfg['name']}")

        return result

    def ensure_logged_in(self, platform: str) -> Dict:
        """Ensure logged in. Uses cached session if available, otherwise login."""
        cfg = PLATFORM_CONFIG.get(platform)
        if not cfg:
            return {"ok": False, "error": f"Unknown platform: {platform}"}

        browser = self._ensure_browser()

        # Quick check: do we have valid cookies?
        if browser.is_logged_in(platform, cfg["success_indicator"]):
            self._logged_in[platform] = True
            return {"ok": True, "platform": platform, "method": "cached_session"}

        # Need to login
        return self.login(platform)

    # ── Post content ────────────────────────────────────────────────

    def post(self, platform: str, content: str,
             media_url: str = "", tags: List[str] = None) -> Dict:
        """Post content to a social platform via browser automation.

        For Discord, uses the webhook system instead.
        """
        if platform == "discord":
            return self._post_discord(content)

        cfg = PLATFORM_CONFIG.get(platform)
        if not cfg:
            return {"ok": False, "error": f"Unknown platform: {platform}"}

        login_result = self.ensure_logged_in(platform)
        if not login_result.get("ok"):
            return {"ok": False, "error": f"Login failed: {login_result.get('error')}"}

        browser = self._ensure_browser()

        try:
            # Navigate to post URL or home
            post_url = cfg["post_url"]
            browser.navigate(platform, post_url)
            time.sleep(3)

            # Click the post trigger (e.g., "What's on your mind?" on Facebook,
            # "Post" button on X)
            trigger = cfg["post_trigger"]
            try:
                browser.click(platform, trigger, timeout=8000)
                time.sleep(2)
            except Exception:
                pass

            # Find the post input box and type content
            post_sel = cfg["post_box"]
            try:
                browser.type_text(platform, post_sel, content, timeout=8000)
            except Exception:
                browser.fill(platform, post_sel, content, timeout=8000)

            time.sleep(1)

            # Add tags if provided
            if tags and platform in ("x", "instagram"):
                tag_text = " " + " ".join(f"#{t}" for t in tags)
                try:
                    page = browser._get_page(platform)
                    page.keyboard.type(tag_text, delay=30)
                except Exception:
                    pass

            # Click submit
            submit = cfg["post_submit"]
            result = browser.click(platform, submit, timeout=10000)

            time.sleep(3)

            # Take a confirmation screenshot
            browser.screenshot(platform, f".browser_sessions/{platform}_post.png")

            return {
                "ok": True,
                "platform": platform,
                "content": content[:200],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "platform": platform}

    # ── Discord (webhook-based, already works) ─────────────────────

    def _post_discord(self, content: str) -> Dict:
        """Post to Discord via webhook URL."""
        webhook_url = get_key(
            vault_category="discord", vault_key="webhook_url",
            env_var="DISCORD_WEBHOOK_URL",
        )
        if not webhook_url:
            return {"ok": False, "error": "No Discord webhook URL configured"}

        try:
            import urllib.request
            payload = json.dumps({"content": content}).encode("utf-8")
            req = urllib.request.Request(
                webhook_url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                if r.status in (200, 204):
                    return {"ok": True, "platform": "discord"}
                return {"ok": False, "error": f"HTTP {r.status}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Bulk posting ────────────────────────────────────────────────

    def post_all(self, content: str, platforms: List[str] = None,
                 tags: List[str] = None) -> Dict:
        """Post the same content to multiple platforms."""
        platforms = platforms or ["facebook", "instagram", "x", "discord"]
        results: Dict[str, Dict] = {}

        for platform in platforms:
            try:
                results[platform] = self.post(platform, content, tags=tags)
            except Exception as e:
                results[platform] = {"ok": False, "error": str(e)}

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": content[:200],
            "results": results,
            "success": sum(1 for r in results.values() if r.get("ok")),
            "total": len(platforms),
        }

    # ── Status ─────────────────────────────────────────────────────

    def status(self) -> Dict:
        return {
            "logged_in": self._logged_in,
            "headless": self._headless,
            "platforms_configured": [
                p for p in PLATFORM_CONFIG
                if any(self._get_credentials(p).values())
            ],
        }


# ── Convenience ─────────────────────────────────────────────────────────

def quick_post(platform: str, content: str,
               headless: bool = True) -> Dict:
    """One-shot: open browser, login, post, close."""
    sp = SocialPoster(headless=headless)
    try:
        return sp.post(platform, content)
    finally:
        sp.close()


def crosspost(content: str, platforms: List[str] = None,
              headless: bool = True) -> Dict:
    """Post to all configured platforms."""
    sp = SocialPoster(headless=headless)
    try:
        return sp.post_all(content, platforms)
    finally:
        sp.close()
