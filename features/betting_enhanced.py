"""Enhanced Betting Engine — datasets, trends, circadian rhythm, custom formulas.

Extends the base betting engine with:
1. Public sports datasets (NBA, NFL, MLB stats)
2. Trend analysis (rolling averages, streaks, home/away, H2H)
3. Circadian rhythm adjustments (timezone jet lag factor)
4. Custom formula upload and execution
"""
from __future__ import annotations
import os
import json
import time
import hashlib
import urllib.request
import urllib.error
from typing import Dict, List, Optional
from dataclasses import dataclass


# ═══════════════════════════════════════════════════════════════
# SPORTS DATASETS (public APIs + local fallback)
# ═══════════════════════════════════════════════════════════════

@dataclass
class PlayerStats:
    name: str; sport: str; team: str
    games: int = 0; minutes: float = 0
    points: float = 0; rebounds: float = 0; assists: float = 0
    # Last 5 game averages
    l5_pts: float = 0; l5_reb: float = 0; l5_ast: float = 0
    # Home/away splits
    home_pts: float = 0; away_pts: float = 0
    # Streaks
    over_streak: int = 0; under_streak: int = 0
    # Season trends
    pts_trend: float = 0  # positive = trending up

    def to_dict(self): return {k:v for k,v in self.__dict__.items() if not k.startswith('_')}


class SportsDataFeed:
    """Fetches player stats from public APIs (NBA, NFL, MLB)."""

    def fetch_nba_player(self, player_name: str) -> Optional[PlayerStats]:
        """Fetch NBA player stats from balldontlie API (free, no key)."""
        try:
            q = player_name.replace(" ", "%20")
            url = f"https://www.balldontlie.io/api/v1/players?search={q}&per_page=1"
            req = urllib.request.Request(url, headers={"User-Agent": "DeterministicBrain/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            if not data.get("data"):
                return self._sample_nba(player_name)
            p = data["data"][0]

            # Fetch season averages
            pid = p["id"]
            url2 = f"https://www.balldontlie.io/api/v1/season_averages?season=2024&player_ids[]={pid}"
            req2 = urllib.request.Request(url2, headers={"User-Agent": "DeterministicBrain/1.0"})
            with urllib.request.urlopen(req2, timeout=10) as r:
                avgs = json.loads(r.read().decode())
            avg = avgs.get("data", [{}])[0] if avgs.get("data") else {}

            return PlayerStats(
                name=player_name, sport="NBA", team=p.get("team",{}).get("full_name",""),
                points=avg.get("pts",0), rebounds=avg.get("reb",0), assists=avg.get("ast",0),
                games=avg.get("games_played",0), minutes=avg.get("min","").split(":")[0] if avg.get("min") else 0,
            )
        except Exception:
            return self._sample_nba(player_name)

    def _sample_nba(self, name: str) -> PlayerStats:
        """Fallback sample data for testing."""
        samples = {
            "LeBron James": PlayerStats(name="LeBron James",sport="NBA",team="Lakers",points=25.7,rebounds=7.3,assists=8.3,l5_pts=28.2,l5_reb=8.1,l5_ast=9.1,home_pts=26.1,away_pts=25.3,over_streak=3,pts_trend=2.1),
            "Steph Curry": PlayerStats(name="Steph Curry",sport="NBA",team="Warriors",points=26.4,rebounds=4.5,assists=5.1,l5_pts=24.1,l5_reb=3.8,l5_ast=4.5,home_pts=27.8,away_pts=25.0,over_streak=1,pts_trend=-1.2),
            "Jayson Tatum": PlayerStats(name="Jayson Tatum",sport="NBA",team="Celtics",points=30.1,rebounds=8.8,assists=5.7,l5_pts=32.4,l5_reb=9.2,l5_ast=6.1,home_pts=31.5,away_pts=28.7,over_streak=4,pts_trend=3.5),
            "Kevin Durant": PlayerStats(name="Kevin Durant",sport="NBA",team="Suns",points=27.1,rebounds=6.6,assists=5.0,l5_pts=25.9,l5_reb=6.1,l5_ast=4.8,home_pts=27.8,away_pts=26.4,over_streak=2,pts_trend=0.5),
        }
        return samples.get(name, PlayerStats(name=name, sport="NBA", team="Unknown",
            points=20.0, rebounds=5.0, assists=4.0, l5_pts=20.5, l5_reb=5.2, l5_ast=4.1,
            home_pts=21.0, away_pts=19.0, over_streak=1, pts_trend=0.2))


# ═══════════════════════════════════════════════════════════════
# TREND ANALYSIS
# ═══════════════════════════════════════════════════════════════

class TrendAnalyzer:
    """Analyzes player trends: streaks, momentum, home/away splits, rest days."""

    def analyze(self, stats: PlayerStats, market: str, line: float) -> Dict:
        """Return trend signals for a given player + market + line."""
        val = {"points": stats.points, "rebounds": stats.rebounds, "assists": stats.assists}.get(market, 0)
        l5 = {"points": stats.l5_pts, "rebounds": stats.l5_reb, "assists": stats.l5_ast}.get(market, 0)

        signals = {}

        # Recent form (L5 vs season avg)
        if l5 > val * 1.05:
            signals["form"] = "hot"
            signals["form_score"] = 0.15
        elif l5 < val * 0.95:
            signals["form"] = "cold"
            signals["form_score"] = -0.10
        else:
            signals["form"] = "neutral"
            signals["form_score"] = 0.0

        # Streak signal
        if stats.over_streak >= 3:
            signals["streak"] = f"over_{stats.over_streak}g"
            signals["streak_score"] = 0.08
        elif stats.under_streak >= 3:
            signals["streak"] = f"under_{stats.under_streak}g"
            signals["streak_score"] = -0.08
        else:
            signals["streak_score"] = 0.0

        # Trend direction
        if stats.pts_trend > 0:
            signals["momentum"] = "up"
            signals["momentum_score"] = min(stats.pts_trend * 0.02, 0.12)
        else:
            signals["momentum"] = "down"
            signals["momentum_score"] = max(stats.pts_trend * 0.02, -0.12)

        # Percentage over/under the line
        if line > 0 and val > 0:
            pct_over = (val - line) / line
            signals["pct_vs_line"] = round(pct_over, 3)
            signals["line_score"] = pct_over * 0.3
        else:
            signals["line_score"] = 0.0

        # Combined trend signal (-1 to +1)
        combined = signals.get("form_score", 0) + signals.get("streak_score", 0) + signals.get("momentum_score", 0) + signals.get("line_score", 0)
        signals["combined"] = round(max(-1, min(1, combined)), 3)
        signals["recommendation"] = "over" if combined > 0 else "under"

        return signals


# ═══════════════════════════════════════════════════════════════
# CIRCADIAN RHYTHM FACTOR
# ═══════════════════════════════════════════════════════════════

CIRCADIAN_DATA = {
    # Team timezone offsets from Eastern
    "Lakers": -3, "Clippers": -3, "Warriors": -3, "Suns": -2, "Kings": -3,
    "Celtics": 0, "Knicks": 0, "Nets": 0, "76ers": 0, "Heat": 0,
    "Bulls": -1, "Cavaliers": 0, "Pistons": 0, "Pacers": 0, "Bucks": -1,
    "Nuggets": -2, "Jazz": -2, "Blazers": -3, "Thunder": -1, "Timberwolves": -1,
    "Mavericks": -1, "Rockets": -1, "Spurs": -1, "Grizzlies": -1, "Pelicans": -1,
    "Hawks": 0, "Hornets": 0, "Wizards": 0, "Magic": 0, "Raptors": 0,
}

class CircadianAnalyzer:
    """Factors in jet lag and circadian rhythm effects on performance."""

    def analyze(self, player_team: str, opponent_team: str, game_time: str = "19:00") -> Dict:
        """Return circadian adjustment factor."""
        player_tz = CIRCADIAN_DATA.get(player_team, -1)
        opponent_tz = CIRCADIAN_DATA.get(opponent_team, 0)

        # Timezone difference
        tz_diff = abs(player_tz - opponent_tz)
        jet_lag = 0.0
        if tz_diff >= 3:
            jet_lag = -0.08  # significant jet lag
        elif tz_diff >= 2:
            jet_lag = -0.04
        elif tz_diff >= 1:
            jet_lag = -0.02

        # Time of day adjustment (peak performance ~4-8 PM local)
        try:
            hour = int(game_time.split(":")[0])
            if 16 <= hour <= 20:
                peak_bonus = 0.03
            elif 12 <= hour <= 15 or 21 <= hour <= 22:
                peak_bonus = 0.01
            else:
                peak_bonus = -0.02  # late night / early afternoon
        except (ValueError, IndexError):
            peak_bonus = 0.0

        # Home/away (home court advantage ~3-5% edge)
        home_edge = 0.03  # assume home if we're analyzing this team's player

        return {
            "timezone_diff": tz_diff,
            "jet_lag_factor": round(jet_lag, 3),
            "peak_performance": round(peak_bonus, 3),
            "circadian_adjustment": round(jet_lag + peak_bonus + home_edge, 3),
        }


# ═══════════════════════════════════════════════════════════════
# CUSTOM FORMULA ENGINE
# ═══════════════════════════════════════════════════════════════

class FormulaEngine:
    """Stores and executes custom user-uploaded betting formulas.

    Formulas are Python expressions evaluated in a sandbox with access
    to stats, trends, and circadian data. Results are scored and ranked.
    """

    def __init__(self, formulas_path: str = "formulas.json"):
        self.formulas_path = formulas_path
        self.formulas: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.formulas_path):
            try:
                with open(self.formulas_path) as f:
                    self.formulas = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

    def _save(self):
        with open(self.formulas_path, "w") as f:
            json.dump(self.formulas, f, indent=2)

    def upload(self, name: str, expression: str, description: str = "") -> Dict:
        """Upload a custom formula. Expression uses: pts, reb, ast, l5_pts, line, trend, circadian"""
        fid = hashlib.sha256(name.encode()).hexdigest()[:8]
        self.formulas[fid] = {
            "name": name, "expression": expression, "description": description,
            "created": time.strftime("%Y-%m-%d %H:%M"), "runs": 0,
        }
        self._save()
        return {"id": fid, **self.formulas[fid]}

    def list_all(self) -> List[Dict]:
        return [{"id": k, **v} for k, v in self.formulas.items()]

    def delete(self, fid: str) -> bool:
        if fid in self.formulas:
            del self.formulas[fid]; self._save(); return True
        return False

    def evaluate(self, fid: str, context: Dict) -> Optional[float]:
        """Evaluate a formula against player context. Hardened against escape."""
        f = self.formulas.get(fid)
        if not f:
            return None

        expr = f["expression"]
        # Security Check 1: Length limit
        if len(expr) > 200:
            return None
            
        # Security Check 2: Character whitelist (letters, numbers, basic math, spaces)
        import re
        if not re.match(r"^[a-zA-Z0-9\s\+\-\*\/\(\)\.\,]+$", expr):
            return None
            
        # Security Check 3: Keyword blacklist (prevent reaching builtins/classes)
        blacklist = ["__", "class", "def", "import", "exec", "eval", "lambda", "yield"]
        if any(b in expr for b in blacklist):
            return None

        # Safe variables
        safe_vars = {
            "pts": float(context.get("pts", 0)), "reb": float(context.get("reb", 0)),
            "ast": float(context.get("ast", 0)), "l5_pts": float(context.get("l5_pts", 0)),
            "l5_reb": float(context.get("l5_reb", 0)), "l5_ast": float(context.get("l5_ast", 0)),
            "line": float(context.get("line", 0)), "trend": float(context.get("trend", 0)),
            "circadian": float(context.get("circadian", 0)), "home_pts": float(context.get("home_pts", 0)),
            "away_pts": float(context.get("away_pts", 0)), "streak": float(context.get("streak", 0)),
            "abs": abs, "max": max, "min": min, "round": round,
        }
        
        try:
            # Use empty dict for globals and builtins to prevent escape
            result = eval(expr, {"__builtins__": {}}, safe_vars)
            f["runs"] = f.get("runs", 0) + 1; self._save()
            return float(result)
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════
# ENHANCED BET SHEET (combines everything)
# ═══════════════════════════════════════════════════════════════

class EnhancedBetSheet:
    """Combines datasets, trends, circadian, and formulas into enriched picks."""

    def __init__(self):
        self.data_feed = SportsDataFeed()
        self.trends = TrendAnalyzer()
        self.circadian = CircadianAnalyzer()
        self.formulas = FormulaEngine()

    def generate(self, sport: str = "basketball_nba", bankroll: float = 1000.0) -> Dict:
        """Generate an enhanced bet sheet with all factors considered."""
        from features.betting_engine import get_bet_sheet
        base = get_bet_sheet()
        raw = base.fetcher.fetch(sport)
        games = raw.get("games", []) if isinstance(raw, dict) else raw
        bets = base._parse_bets(games)

        enriched = []
        for b in bets:
            stats = self.data_feed.fetch_nba_player(b.player)
            if not stats:
                continue

            trends = self.trends.analyze(stats, b.market, b.line)
            circ = self.circadian.analyze(stats.team, "opponent", "19:00")

            # Adjust EV with trend + circadian signals
            base_ev = b.ev("over") if trends["combined"] > 0 else b.ev("under")
            adjusted_ev = base_ev + trends["combined"] * 0.05 + circ["circadian_adjustment"] * 0.03

            # Evaluate custom formulas
            formula_results = {}
            for fid in self.formulas.list_all():
                ctx = {"pts": stats.points, "reb": stats.rebounds, "ast": stats.assists,
                       "l5_pts": stats.l5_pts, "line": b.line, "trend": trends["combined"],
                       "circadian": circ["circadian_adjustment"], "home_pts": stats.home_pts,
                       "away_pts": stats.away_pts, "streak": stats.over_streak}
                result = self.formulas.evaluate(fid["id"], ctx)
                if result is not None:
                    formula_results[fid["name"]] = round(result, 3)

            enriched.append({
                "player": b.player, "sport": b.sport, "team": stats.team,
                "market": b.market, "line": b.line,
                "pick": "over" if trends["recommendation"] == "over" else "under",
                "season_avg": getattr(stats, b.market, stats.points),
                "l5_avg": {"points": stats.l5_pts, "rebounds": stats.l5_reb, "assists": stats.l5_ast}.get(b.market, 0),
                "trends": trends,
                "circadian": circ,
                "base_ev": round(base_ev, 4),
                "adjusted_ev": round(adjusted_ev, 4),
                "formula_results": formula_results,
                "confidence": round(min(abs(adjusted_ev) * 8 + trends["combined"] * 0.3, 0.95), 2),
            })

        enriched.sort(key=lambda x: -x["adjusted_ev"])
        return {
            "sport": sport, "bankroll": bankroll,
            "total_analyzed": len(enriched),
            "picks": enriched[:15],
            "top_pick": enriched[0] if enriched else None,
        }


# Singleton
_ENHANCED: Optional[EnhancedBetSheet] = None
def get_enhanced_betting() -> EnhancedBetSheet:
    global _ENHANCED
    if _ENHANCED is None: _ENHANCED = EnhancedBetSheet()
    return _ENHANCED
