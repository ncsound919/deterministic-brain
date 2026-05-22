"""Odds client — fetch sports betting lines from free APIs.

Feeds Monte Carlo bettor with real implied probabilities.
The-Odds-API free tier: 500 req/month. No key = synthetic fallback.

Token savings: ~500 tokens per odds query vs LLM scraping approach.
"""

from __future__ import annotations
import json
import os
from typing import Dict
from urllib.request import urlopen

from tools.circuit_breaker import circuit_breaker


class OddsClient:
    """Fetch sports betting odds from free APIs."""

    BASE_URL = "https://api.the-odds-api.com/v4/sports"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("ODDS_API_KEY", "")

    def fetch_odds(self, sport: str = "basketball_nba",
                   region: str = "us", markets: str = "h2h,spreads") -> Dict:
        """Fetch live odds for a sport."""
        if not self.api_key:
            return self._synthetic_odds(sport)

        url = (f"{self.BASE_URL}/{sport}/odds/"
               f"?apiKey={self.api_key}&regions={region}&markets={markets}&oddsFormat=american")
        try:
            with urlopen(url, timeout=15) as r:
                data = json.loads(r.read())
            remaining = r.headers.get("x-requests-remaining", "?")
            return {"ok": True, "data": data, "requests_remaining": remaining}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _synthetic_odds(self, sport: str) -> Dict:
        """Synthetic odds for testing when no API key."""
        nba_lines = [
            {"name": "Lakers -5.5", "bookmaker": "synthetic", "american_odds": -110},
            {"name": "Celtics ML", "bookmaker": "synthetic", "american_odds": +150},
            {"name": "Warriors O225.5", "bookmaker": "synthetic", "american_odds": -105},
            {"name": "Nuggets +2.5", "bookmaker": "synthetic", "american_odds": +105},
        ]
        nfl_lines = [
            {"name": "Chiefs -3", "bookmaker": "synthetic", "american_odds": -120},
            {"name": "49ers ML", "bookmaker": "synthetic", "american_odds": +180},
        ]
        lines = nba_lines if "nba" in sport else nfl_lines
        return {"ok": True, "data": lines, "source": "synthetic",
                "note": "Set ODDS_API_KEY for live odds from the-odds-api.com"}


@circuit_breaker(name="odds_api", threshold=3, cooldown_s=60, retries=1)
def fetch_odds(sport: str = "basketball_nba") -> Dict:
    """Convenience function for tool registry."""
    return OddsClient().fetch_odds(sport)
