"""Google Services Client — Gmail, Drive, Calendar, Maps, YouTube.

All read from the credential vault's 'google' category.
Gmail SMTP sending is handled by tools/email_sender.py (already vault-aware).

For full OAuth access (Drive, Calendar, Gmail read), you need:
  1. A Google Cloud project with APIs enabled
  2. OAuth client ID + client secret
  3. A refresh token obtained via OAuth flow

For simple API key access (Maps, YouTube Data), just the key is enough.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from typing import Dict

from tools.vault_aware_api import get_key
from tools.browser.live_controller import LiveBrowser


class GoogleClient:
    """Unified Google services client. Uses API keys + OAuth from vault."""

    def __init__(self):
        self.email = get_key(
            vault_category="google", vault_key="email",
        )
        self.app_password = get_key(
            vault_category="google", vault_key="app_password",
        )
        self.maps_key = get_key(
            vault_category="google", vault_key="maps_api_key",
        )
        self.drive_key = get_key(
            vault_category="google", vault_key="drive_api_key",
        )
        self.youtube_key = get_key(
            vault_category="google", vault_key="youtube_api_key",
        )
        self.client_id = get_key(
            vault_category="google", vault_key="oauth_client_id",
        )
        self.client_secret = get_key(
            vault_category="google", vault_key="oauth_client_secret",
        )
        self.refresh_token = get_key(
            vault_category="google", vault_key="refresh_token",
        )
        self.calendar_id = get_key(
            vault_category="google", vault_key="calendar_id",
        )

    # ── Status ──────────────────────────────────────────────────────

    def status(self) -> Dict:
        return {
            "email_configured": bool(self.email),
            "smtp_configured": bool(self.email and self.app_password),
            "maps_configured": bool(self.maps_key),
            "drive_configured": bool(self.drive_key),
            "youtube_configured": bool(self.youtube_key),
            "oauth_configured": bool(self.client_id and self.client_secret and self.refresh_token),
            "calendar_configured": bool(self.calendar_id),
            "playwright_auth_available": True, # Available via .browser_sessions
        }

    # ── Gmail SMTP (delegates to email_sender) ─────────────────────

    def send_email(self, to: str, subject: str, body: str,
                   html: bool = False) -> Dict:
        from tools.email_sender import send_email as _send
        return _send(to, subject, body, html=html)

    # ── Gmail Reading (Playwright Fallback) ─────────────────────────

    def read_gmail(self, limit: int = 5) -> Dict:
        """Reads recent emails using Playwright session cookies."""
        try:
            with LiveBrowser(headless=True) as b:
                # Assuming google_auth_playwright.py saved cookies under 'google' platform
                res = b.navigate("google", "https://mail.google.com/mail/u/0/#inbox", wait_until="networkidle")
                if not res.get("ok"):
                    return {"ok": False, "error": res.get("error")}
                
                page = b._get_page("google")
                # Wait for any typical Gmail inbox element
                page.wait_for_selector("tr.zA", timeout=10000)
                
                # Simple extraction of email subjects (this relies on standard Gmail DOM)
                # The class 'bog' is often used for unread subjects, 'y6' for read, but we'll grab generic spans inside the row
                page = b._get_page("google")
                rows = page.locator("tr.zA").all()
                
                emails = []
                for row in rows[:limit]:
                    try:
                        subject = row.locator("span.bog").inner_text()
                        sender = row.locator("span.bA4 span[email]").get_attribute("name") or row.locator("span.zF").inner_text()
                        emails.append({"sender": sender, "subject": subject})
                    except Exception:
                        pass
                
                return {"ok": True, "emails": emails}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Google Drive (Playwright Fallback) ──────────────────────────

    def drive_list(self, limit: int = 5) -> Dict:
        """Lists recent Drive files using Playwright session cookies."""
        try:
            with LiveBrowser(headless=True) as b:
                res = b.navigate("google", "https://drive.google.com/drive/my-drive", wait_until="networkidle")
                if not res.get("ok"):
                    return {"ok": False, "error": res.get("error")}
                
                page = b._get_page("google")
                # Wait for rows to appear
                try:
                    page.wait_for_selector("div[role='row']", timeout=10000)
                except Exception:
                    pass
                
                page = b._get_page("google")
                rows = page.locator("div[role='row']").all()
                
                files = []
                for row in rows[:limit]:
                    try:
                        name = row.locator("div[aria-label]").first.get_attribute("aria-label")
                        if name:
                            files.append({"name": name.replace("File name: ", "").strip()})
                    except Exception:
                        pass
                
                return {"ok": True, "files": files}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Google Maps ─────────────────────────────────────────────────

    def geocode(self, address: str) -> Dict:
        if not self.maps_key:
            return {"ok": False, "error": "No Google Maps API key"}
        try:
            url = (
                "https://maps.googleapis.com/maps/api/geocode/json"
                f"?address={urllib.parse.quote(address)}"
                f"&key={self.maps_key}"
            )
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read())
                if data.get("status") == "OK" and data.get("results"):
                    loc = data["results"][0]["geometry"]["location"]
                    return {
                        "ok": True,
                        "lat": loc["lat"], "lng": loc["lng"],
                        "formatted": data["results"][0]["formatted_address"],
                    }
                return {"ok": False, "error": data.get("status", "unknown")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def places_search(self, query: str, lat: float = None,
                      lng: float = None, radius: int = 5000) -> Dict:
        if not self.maps_key:
            return {"ok": False, "error": "No Google Maps API key"}
        try:
            url = (
                "https://maps.googleapis.com/maps/api/place/textsearch/json"
                f"?query={urllib.parse.quote(query)}"
                f"&key={self.maps_key}"
            )
            if lat and lng:
                url += f"&location={lat},{lng}&radius={radius}"
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read())
                if data.get("status") == "OK":
                    places = []
                    for p in data.get("results", [])[:10]:
                        places.append({
                            "name": p.get("name", ""),
                            "address": p.get("formatted_address", ""),
                            "rating": p.get("rating", 0),
                            "types": p.get("types", []),
                        })
                    return {"ok": True, "places": places}
                return {"ok": False, "error": data.get("status", "unknown")}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Google Calendar (read-only via API key or OAuth) ────────────

    def calendar_events(self, max_results: int = 10) -> Dict:
        if not self.calendar_id:
            return {"ok": False, "error": "No Google Calendar ID configured"}
        if not self.maps_key:
            return {"ok": False, "error": "API key required for public calendar access"}
        try:
            url = (
                f"https://www.googleapis.com/calendar/v3/calendars/"
                f"{urllib.parse.quote(self.calendar_id)}/events"
                f"?key={self.maps_key}"
                f"&maxResults={max_results}&singleEvents=true"
                f"&orderBy=startTime"
                f"&timeMin={urllib.parse.quote(datetime.now(timezone.utc).isoformat())}"
            )
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read())
                events = []
                for e in data.get("items", []):
                    events.append({
                        "summary": e.get("summary", ""),
                        "start": e.get("start", {}).get("dateTime", e.get("start", {}).get("date", "")),
                        "end": e.get("end", {}).get("dateTime", ""),
                        "location": e.get("location", ""),
                        "description": (e.get("description", "") or "")[:200],
                    })
                return {"ok": True, "events": events}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── YouTube Data ─────────────────────────────────────────────────

    def youtube_search(self, query: str, max_results: int = 5) -> Dict:
        if not self.youtube_key:
            return {"ok": False, "error": "No YouTube API key"}
        try:
            url = (
                "https://www.googleapis.com/youtube/v3/search"
                f"?part=snippet&q={urllib.parse.quote(query)}"
                f"&maxResults={max_results}&type=video"
                f"&key={self.youtube_key}"
            )
            with urllib.request.urlopen(url, timeout=15) as r:
                data = json.loads(r.read())
                videos = []
                for item in data.get("items", []):
                    snip = item.get("snippet", {})
                    vid = item.get("id", {}).get("videoId", "")
                    videos.append({
                        "title": snip.get("title", ""),
                        "channel": snip.get("channelTitle", ""),
                        "url": f"https://youtube.com/watch?v={vid}" if vid else "",
                        "published": snip.get("publishedAt", ""),
                    })
                return {"ok": True, "videos": videos}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ── Convenience ─────────────────────────────────────────────────────────

def google_status() -> Dict:
    gc = GoogleClient()
    return gc.status()
