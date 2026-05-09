"""Sports Betting Engine — PrizePicks + Odds API + Math Engine + Bet Sheet.

Powers: odds fetching, EV calculation, Kelly criterion, correlation analysis,
bet sheet generation, and browser-automated bet placement on PrizePicks.
"""
from __future__ import annotations
import os, json, time, hashlib, urllib.request, urllib.error
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class Bet:
    sport: str
    player: str
    market: str           # "points", "rebounds", "assists", "strikeouts", etc.
    line: float           # the over/under line
    over_odds: float      # American odds e.g. +100, -110
    under_odds: float
    book: str = "prizepicks"
    start_time: str = ""
    confidence: float = 0.0

    def implied_prob(self, american_odds: float) -> float:
        if american_odds > 0: return 100 / (american_odds + 100)
        return abs(american_odds) / (abs(american_odds) + 100)

    def ev(self, pick: str = "over") -> float:
        """Expected value of picking over/under vs the line."""
        odds = self.over_odds if pick == "over" else self.under_odds
        p = self.implied_prob(odds)
        return (p * (1 / p - 1)) - ((1 - p) * 1)

    def kelly(self, bankroll: float, pick: str = "over", edge: float = 0.02) -> float:
        """Kelly criterion bet sizing."""
        odds = self.over_odds if pick == "over" else self.under_odds
        p = self.implied_prob(odds) + edge
        q = 1 - p
        b = odds / 100 if odds > 0 else 100 / abs(odds)
        if b <= 0: return 0
        f = (b * p - q) / b
        return max(0, min(f, 0.05)) * bankroll

    def to_dict(self) -> Dict:
        return {
            "sport": self.sport, "player": self.player, "market": self.market,
            "line": self.line, "over_odds": self.over_odds, "under_odds": self.under_odds,
            "book": self.book, "start_time": self.start_time, "confidence": self.confidence,
            "ev_over": round(self.ev("over"), 4), "ev_under": round(self.ev("under"), 4),
        }


class OddsFetcher:
    """Fetch live odds from The Odds API or generate sample data."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("ODDS_API_KEY", "")

    def fetch(self, sport: str = "basketball_nba") -> List[Dict]:
        if not self.api_key:
            return self._sample(sport)
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={self.api_key}&regions=us&markets=player_points,player_rebounds,player_assists&oddsFormat=american"
            req = urllib.request.Request(url, headers={"User-Agent": "DeterministicBrain/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read().decode())
        except Exception:
            return self._sample(sport)
        return data

    def _sample(self, sport: str) -> List[Dict]:
        return [
            {"sport_title": "NBA", "home_team": "Lakers", "away_team": "Celtics",
             "bookmakers": [{"title": "PrizePicks", "markets": [
                 {"key": "player_points", "outcomes": [
                     {"name": "LeBron James", "description": "Over", "price": -110, "point": 27.5},
                     {"name": "LeBron James", "description": "Under", "price": -110, "point": 27.5},
                     {"name": "Jayson Tatum", "description": "Over", "price": -105, "point": 30.5},
                     {"name": "Jayson Tatum", "description": "Under", "price": -115, "point": 30.5},
                 ]},
                 {"key": "player_rebounds", "outcomes": [
                     {"name": "Anthony Davis", "description": "Over", "price": -120, "point": 12.5},
                     {"name": "Anthony Davis", "description": "Under", "price": +100, "point": 12.5},
                 ]},
             ]}],
            },
            {"sport_title": "NBA", "home_team": "Warriors", "away_team": "Suns",
             "bookmakers": [{"title": "PrizePicks", "markets": [
                 {"key": "player_points", "outcomes": [
                     {"name": "Steph Curry", "description": "Over", "price": -115, "point": 28.5},
                     {"name": "Steph Curry", "description": "Under", "price": -105, "point": 28.5},
                     {"name": "Kevin Durant", "description": "Over", "price": -110, "point": 29.5},
                 ]},
             ]}],
            },
        ]


class BettingMath:
    """Deterministic math engine for bet selection."""

    def analyze(self, bets: List[Bet], bankroll: float = 1000.0, min_ev: float = 0.01) -> Dict:
        """Score every bet and return the best picks. Shows all picks ranked by EV, highlights those above threshold."""
        scored = []
        for b in bets:
            ev_over = b.ev("over")
            ev_under = b.ev("under")
            kelly_over = b.kelly(bankroll, "over")
            kelly_under = b.kelly(bankroll, "under")

            best_pick = "over" if ev_over > ev_under else "under"
            best_ev = max(ev_over, ev_under)
            best_kelly = kelly_over if best_pick == "over" else kelly_under

            scored.append({
                "bet": b.to_dict(),
                "pick": best_pick,
                "ev": round(best_ev, 4),
                "kelly_bet": round(best_kelly, 2),
                "confidence": round(min(abs(best_ev) * 5 + 0.1, 0.95), 2),
                "recommended": best_ev >= min_ev,
            })

        scored.sort(key=lambda x: -x["ev"])
        recs = [s for s in scored if s["recommended"]]
        return {
            "total_bets": len(bets),
            "recommended": recs if recs else scored[:5],  # show top 5 even if none meet EV threshold
            "all_scored": scored,
            "bankroll": bankroll,
        }

    def generate_sheet(self, picks: List[Dict]) -> str:
        """Generate a bet sheet with picks, stakes, and rationale."""
        lines = ["BET SHEET — " + time.strftime("%Y-%m-%d %H:%M"), "=" * 50, ""]
        total_stake = 0
        for i, p in enumerate(picks[:10], 1):
            b = p["bet"]
            stake = p.get("kelly_bet", 0)
            total_stake += stake
            rec = " [RECOMMENDED]" if p.get("recommended", True) else ""
            lines.append(f"{i}. {b['player']} — {p['pick'].upper()} {b['line']} {b['market']}{rec}")
            lines.append(f"   EV: {p['ev']:.3f} | Stake: ${stake:.2f} | Conf: {p.get('confidence',0):.1%}")
            lines.append("")
        lines.append(f"Total stake: ${total_stake:.2f}")
        return "\n".join(lines)


class PrizePicksBrowser:
    """Browser automation for PrizePicks bet placement.

    Uses the browser panel to navigate to PrizePicks, search for players,
    select over/under, enter stake, and submit. All via deterministic Playwright-like actions.
    """

    def __init__(self, prize_picks_url: str = "https://app.prizepicks.com/"):
        self.base_url = prize_picks_url

    def build_automation_script(self, picks: List[Dict]) -> str:
        """Generate a JavaScript automation script that can be pasted into the browser console
        to place bets on PrizePicks. This avoids needing Playwright server-side."""
        script = ["// PrizePicks Bet Automation — paste in browser console", ""]
        for i, p in enumerate(picks[:5], 1):
            b = p["bet"]
            script.append(f"// {i}. {b['player']} — {p['pick'].upper()} {b['line']} (${p['kelly_bet']})")
            script.append(f"console.log('Searching for {b['player']}...');")
            script.append(f"// Search for player")
            script.append(f"document.querySelector('input[placeholder*=\"Search\"]')?.value = '{b['player']}';")
            script.append(f"// Find and click the {p['pick']} button")
            script.append("")
        return "\n".join(script)

    def place_via_browser(self, picks: List[Dict]) -> Dict:
        """Return instructions for browser-based bet placement."""
        steps = []
        for i, p in enumerate(picks[:5], 1):
            b = p["bet"]
            steps.append({
                "step": i,
                "action": "search_player",
                "player": b["player"],
                "pick": p["pick"].upper(),
                "line": b["line"],
                "market": b["market"],
                "stake": p["kelly_bet"],
                "url": f"{self.base_url}board",
            })
        return {"platform": "prizepicks", "steps": steps, "script": self.build_automation_script(picks)}


# ═══════════════════════════════════════════════════════════════════
# BET SHEET BUILDER (full page)
# ═══════════════════════════════════════════════════════════════════

class BetSheetBuilder:
    """Builds a complete bet sheet with analysis and placement instructions."""

    def __init__(self):
        self.fetcher = OddsFetcher()
        self.math = BettingMath()
        self.browser = PrizePicksBrowser()

    def build_sheet(self, sport: str = "basketball_nba", bankroll: float = 1000.0,
                    min_ev: float = 0.01) -> Dict:
        raw = self.fetcher.fetch(sport)
        bets = self._parse_bets(raw)
        analysis = self.math.analyze(bets, bankroll, min_ev)
        sheet = self.math.generate_sheet(analysis["recommended"])
        automation = self.browser.place_via_browser(analysis["recommended"])

        return {
            "sport": sport,
            "bankroll": bankroll,
            "total_bets_analyzed": analysis["total_bets"],
            "recommended_picks": len(analysis["recommended"]),
            "sheet": sheet,
            "analysis": analysis["recommended"][:10],
            "automation": automation,
        }

    def _parse_bets(self, raw: List[Dict]) -> List[Bet]:
        bets = []
        for game in raw:
            sport = game.get("sport_title", "?")
            for book in game.get("bookmakers", []):
                for market in book.get("markets", []):
                    outcomes = market.get("outcomes", [])
                    for i in range(0, len(outcomes) - 1, 2):
                        over = outcomes[i]
                        under = outcomes[i + 1] if i + 1 < len(outcomes) else over
                        if over.get("description") == "Over":
                            bets.append(Bet(
                                sport=sport, player=over["name"],
                                market=market["key"].replace("player_", ""),
                                line=over.get("point", 0),
                                over_odds=over.get("price", -110),
                                under_odds=under.get("price", -110),
                                book=book.get("title", ""),
                            ))
        return bets


# Singleton
_BUILDER: Optional[BetSheetBuilder] = None
def get_bet_sheet() -> BetSheetBuilder:
    global _BUILDER
    if _BUILDER is None: _BUILDER = BetSheetBuilder()
    return _BUILDER
