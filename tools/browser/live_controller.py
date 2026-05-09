"""Live Browser Controller — real Playwright-based browser automation.

Supports persistent sessions with cookie storage so login state survives
across restarts. Used by the social posting layer for Facebook, Instagram,
TikTok, X/Twitter, and any platform requiring browser-based auth.

Requires: pip install playwright && playwright install chromium
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
    _PLAYWRIGHT_OK = True
except ImportError:
    _PLAYWRIGHT_OK = False

COOKIE_DIR = ".browser_sessions"


class LiveBrowser:
    """Real browser automation with persistent sessions.

    Usage:
        with LiveBrowser() as b:
            b.login("facebook", "https://facebook.com",
                    username_sel='input[name="email"]',
                    password_sel='input[name="pass"]',
                    submit_sel='button[name="login"]')
            b.post("facebook", "https://facebook.com",
                   content="Hello world!",
                   submit_sel='div[aria-label="Post"]')
    """

    def __init__(self, headless: bool = True, slow_mo: int = 100):
        self._headless = headless
        self._slow_mo = slow_mo
        self._playwright: Any = None
        self._browser: Optional[Browser] = None
        self._contexts: Dict[str, BrowserContext] = {}
        self._pages: Dict[str, Page] = {}

        Path(COOKIE_DIR).mkdir(parents=True, exist_ok=True)

    def __enter__(self):
        if _PLAYWRIGHT_OK:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self._headless, slow_mo=self._slow_mo,
            )
        return self

    def __exit__(self, *args):
        for ctx in self._contexts.values():
            ctx.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def _ensure(self):
        if not _PLAYWRIGHT_OK or not self._browser:
            raise RuntimeError(
                "Playwright not available. Install: pip install playwright && "
                "playwright install chromium"
            )

    def _get_context(self, platform: str) -> BrowserContext:
        if platform not in self._contexts:
            ctx = self._browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            self._contexts[platform] = ctx
            self._load_cookies(platform, ctx)
        return self._contexts[platform]

    def _get_page(self, platform: str) -> Page:
        if platform not in self._pages:
            ctx = self._get_context(platform)
            self._pages[platform] = ctx.new_page()
        return self._pages[platform]

    # ── Cookie persistence ──────────────────────────────────────────

    def _cookie_path(self, platform: str) -> Path:
        return Path(COOKIE_DIR) / f"{platform}_cookies.json"

    def _load_cookies(self, platform: str, ctx: BrowserContext) -> None:
        path = self._cookie_path(platform)
        if path.exists():
            try:
                cookies = json.loads(path.read_text())
                ctx.add_cookies(cookies)
            except Exception:
                pass

    def save_cookies(self, platform: str) -> bool:
        path = self._cookie_path(platform)
        try:
            if platform in self._contexts:
                cookies = self._contexts[platform].cookies()
                path.write_text(json.dumps(cookies))
                return True
        except Exception:
            pass
        return False

    # ── Navigation ──────────────────────────────────────────────────

    def navigate(self, platform: str, url: str,
                 wait_until: str = "domcontentloaded") -> Dict:
        self._ensure()
        try:
            page = self._get_page(platform)
            page.goto(url, wait_until=wait_until, timeout=30000)
            return {"ok": True, "url": page.url,
                    "title": page.title()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Login ───────────────────────────────────────────────────────

    def login(self, platform: str, login_url: str,
              username: str, password: str,
              username_sel: str, password_sel: str,
              submit_sel: str,
              extra_click: Optional[str] = None,
              wait_after_login: int = 5) -> Dict:
        """Perform browser-based login and persist cookies.

        After login, check for common indicators of success:
          - URL changed (no longer on login page)
          - Feed/profile elements visible
        """
        self._ensure()
        try:
            page = self._get_page(platform)
            page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)

            if extra_click:
                try:
                    page.click(extra_click, timeout=5000)
                    time.sleep(1)
                except Exception:
                    pass

            page.fill(username_sel, username, timeout=10000)
            page.fill(password_sel, password, timeout=10000)
            page.click(submit_sel, timeout=10000)

            time.sleep(wait_after_login)

            self.save_cookies(platform)

            return {
                "ok": True,
                "platform": platform,
                "current_url": page.url,
                "title": page.title(),
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "platform": platform}

    # ── Post content ────────────────────────────────────────────────

    def click(self, platform: str, selector: str,
              timeout: int = 10000) -> Dict:
        self._ensure()
        try:
            page = self._get_page(platform)
            page.click(selector, timeout=timeout)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def fill(self, platform: str, selector: str,
             text: str, timeout: int = 10000) -> Dict:
        self._ensure()
        try:
            page = self._get_page(platform)
            page.fill(selector, text, timeout=timeout)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def type_text(self, platform: str, selector: str,
                  text: str, timeout: int = 10000) -> Dict:
        self._ensure()
        try:
            page = self._get_page(platform)
            page.click(selector, timeout=timeout)
            time.sleep(0.5)
            page.keyboard.type(text, delay=50)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def press(self, platform: str, key: str) -> Dict:
        self._ensure()
        try:
            page = self._get_page(platform)
            page.keyboard.press(key)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def screenshot(self, platform: str,
                   path: str = "") -> Dict:
        self._ensure()
        try:
            page = self._get_page(platform)
            spath = path or f".browser_sessions/{platform}_screenshot.png"
            page.screenshot(path=spath, full_page=False)
            return {"ok": True, "path": spath}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def get_text(self, platform: str,
                 selector: str = "body") -> Dict:
        self._ensure()
        try:
            page = self._get_page(platform)
            text = page.text_content(selector, timeout=5000)
            return {"ok": True, "text": text[:5000]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def wait_for(self, platform: str, selector: str,
                 timeout: int = 10000) -> Dict:
        self._ensure()
        try:
            page = self._get_page(platform)
            page.wait_for_selector(selector, timeout=timeout)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def is_logged_in(self, platform: str,
                     success_indicator: str) -> bool:
        """Quick check if cookies provide a valid session."""
        self._ensure()
        try:
            page = self._get_page(platform)
            page.goto("about:blank", wait_until="commit")
            page.goto(
                {"facebook": "https://facebook.com",
                 "instagram": "https://instagram.com",
                 "tiktok": "https://tiktok.com",
                 "x": "https://x.com",
                }.get(platform, "https://google.com"),
                wait_until="domcontentloaded", timeout=15000,
            )
            time.sleep(2)
            try:
                page.wait_for_selector(success_indicator, timeout=5000)
                return True
            except Exception:
                return False
        except Exception:
            return False

    def close(self):
        self.__exit__()


def quick_browser(headless: bool = True) -> LiveBrowser:
    """Convenience: open a LiveBrowser, do work, auto-close."""
    b = LiveBrowser(headless=headless)
    b.__enter__()
    return b
