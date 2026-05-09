"""PrizePicks Player Props Scraper using Scrapling.

Uses PrizePicks' public API (https://api.prizepicks.com) to scrape all player props.
Note: The API provides projection lines but not over/under odds (those are dynamic per user).
Default odds of -110/-110 are used as the base, with historical backtest data providing edge estimation.
"""
from __future__ import annotations
import json
import time
from typing import List, Dict, Optional
from dataclasses import dataclass

try:
    from scrapling.fetchers import Fetcher
    _SCRAPLING_OK = True
except ImportError:
    _SCRAPLING_OK = False


STAT_TYPE_MAP = {
    "19": "points",
    "22": "rebounds",
    "20": "assists",
    "106": "PRA",
    "244": "PA",
    "243": "PR",
    "245": "RA",
    "31": "3PT_MADE",
    "23": "steals",
    "21": "blocks",
    "24": "turnovers",
    "117": "FG_MADE",
    "386": "FG_ATTEMPTED",
    "890": "FTA",
    "68": "FT_MADE",
    "403": "OFF_REB",
    "404": "DEF_REB",
    "387": "PF",
    "385": "DUNKS",
    "901": "2PT_MADE",
    "902": "2PT_ATTEMPTED",
    "392": "3PT_ATTEMPTED",
    "155": "DD",
}

PRIMARY_STATS = {"19", "22", "20", "106", "244", "243", "245"}


@dataclass
class PropPick:
    player: str
    team: str
    opponent: str
    market: str
    line: float
    over_odds: float = -110.0
    under_odds: float = -110.0
    start_time: str = ""
    status: str = "pre_game"
    game_id: str = ""
    description: str = ""

    def to_dict(self) -> Dict:
        return {
            "player": self.player, "team": self.team, "opponent": self.opponent,
            "market": self.market, "line": self.line,
            "over_odds": self.over_odds, "under_odds": self.under_odds,
            "start_time": self.start_time, "status": self.status,
        }


class PrizePicksScraper:
    """Scrape live player props from PrizePicks public API."""

    API_URL = "https://api.prizepicks.com/projections?league_id=7&sport_id=1"

    def __init__(self):
        self.fetcher = Fetcher() if _SCRAPLING_OK else None
        self.mode = "api_direct"
        self._props: List[PropPick] = []
        self._last_fetch: float = 0
        self._cache_ttl: float = 120.0

    def fetch(self, force_refresh: bool = False) -> List[PropPick]:
        if not force_refresh and self._props and (time.time() - self._last_fetch) < self._cache_ttl:
            return self._props

        self._props = self._fetch_api()
        self._last_fetch = time.time()
        return self._props

    def _fetch_api(self) -> List[PropPick]:
        try:
            resp = self.fetcher.get(self.API_URL)
            data = json.loads(resp.body)
            return self._parse(data)
        except Exception as e:
            self.mode = f"error_{type(e).__name__}"
            return []

    def _parse(self, data: Dict) -> List[PropPick]:
        props = []
        included = data.get("included", [])
        player_map, player_team_map, team_map, game_map, stat_map = {}, {}, {}, {}, {}

        for item in included:
            t = item.get("type", "")
            attrs = item.get("attributes", {})
            iid = item.get("id", "")
            if t == "new_player":
                player_map[iid] = attrs.get("display_name", attrs.get("name", "?"))
                player_team_map[iid] = attrs.get("team", "")
            elif t == "team":
                team_map[iid] = attrs.get("abbreviation", "")
            elif t == "game":
                game_map[iid] = {
                    "home": attrs.get("home_team", ""),
                    "away": attrs.get("away_team", ""),
                    "start": attrs.get("start_time", ""),
                }
            elif t == "stat_type":
                stat_map[iid] = attrs.get("name", "")

        for proj in data.get("data", []):
            attrs = proj.get("attributes", {})
            rel = proj.get("relationships", {})
            stat_id = rel.get("stat_type", {}).get("data", {}).get("id", "")
            player_id = rel.get("new_player", {}).get("data", {}).get("id", "")
            game_id = rel.get("game", {}).get("data", {}).get("id", "")
            event_type = attrs.get("event_type", "")

            if event_type != "team":
                continue

            stat_name = STAT_TYPE_MAP.get(stat_id, stat_map.get(stat_id, ""))
            if stat_id not in PRIMARY_STATS:
                continue

            player_name = player_map.get(player_id, "?")
            team_code = player_team_map.get(player_id, "")
            game_info = game_map.get(game_id, {})

            if team_code and game_info:
                home, away = game_info.get("home", ""), game_info.get("away", "")
                opponent = away if team_code == home else (home if team_code else "")
            else:
                opponent = ""

            props.append(PropPick(
                player=player_name, team=team_code, opponent=opponent,
                market=stat_name, line=float(attrs.get("line_score", 0)),
                over_odds=-110.0, under_odds=-110.0,
                start_time=attrs.get("start_time", ""),
                status=attrs.get("status", "pre_game"),
                game_id=game_id,
                description=attrs.get("description", ""),
            ))
        return props


_PPScraper: Optional[PrizePicksScraper] = None


def get_prizepicks_scraper() -> PrizePicksScraper:
    global _PPScraper
    if _PPScraper is None:
        _PPScraper = PrizePicksScraper()
    return _PPScraper


def scrape_prizepicks() -> List[PropPick]:
    return get_prizepicks_scraper().fetch()


if __name__ == "__main__":
    scraper = PrizePicksScraper()
    props = scraper.fetch()
    print(f"Mode: {scraper.mode} | Props: {len(props)}")

    by_market = {}
    for p in props:
        if p.market not in by_market:
            by_market[p.market] = []
        by_market[p.market].append(p)

    for mkt in ["points", "rebounds", "assists", "PRA", "PA", "PR"]:
        items = by_market.get(mkt, [])
        if items:
            print(f"\n  {mkt.upper()} ({len(items)} picks):")
            for p in items[:3]:
                print(f"    {p.player:25s} ({p.team}) | {p.line} | {p.start_time[:10]}")

    with open("backtesting/prizepicks_props.json", "w") as f:
        json.dump([p.to_dict() for p in props], f, indent=2)
    print(f"\nSaved {len(props)} props")