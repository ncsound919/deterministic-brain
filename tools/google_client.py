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
        }

    # ── Gmail SMTP (delegates to email_sender) ─────────────────────

    def send_email(self, to: str, subject: str, body: str,
                   html: bool = False) -> Dict:
        from tools.email_sender import send_email as _send
        return _send(to, subject, body, html=html)

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
