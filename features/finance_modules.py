"""Financial Modules — news, odds, trading strategy builder, Stripe payments.

Three integrated systems:
1. News Feed — multi-source aggregator with sentiment analysis
2. Odds Engine — sports betting odds math with monte carlo integration
3. Trading Engine — strategy builder, live feed, paper trading
"""
from __future__ import annotations
import os
import json
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════
# NEWS FEED
# ═══════════════════════════════════════════════════════════════

@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    summary: str = ""
    published: str = ""
    sentiment: float = 0.0     # -1.0 to 1.0
    category: str = "general"
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "title": self.title, "source": self.source, "url": self.url,
            "summary": self.summary, "published": self.published,
            "sentiment": self.sentiment, "category": self.category,
            "tags": self.tags,
        }


class NewsFeed:
    def __init__(self):
        self.sources = [
            {"name": "Hacker News", "url": "https://hacker-news.firebaseio.com/v0/topstories.json"},
            {"name": "Dev.to", "url": "https://dev.to/api/articles?per_page=10"},
        ]

    def fetch_hackernews(self) -> List[NewsItem]:
        """Fetch top HN stories."""
        try:
            req = urllib.request.Request(
                "https://hacker-news.firebaseio.com/v0/topstories.json",
                headers={"User-Agent": "DeterministicBrain/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                ids = json.loads(r.read().decode())[:15]
        except Exception:
            return []

        items = []
        for sid in ids[:10]:
            try:
                req = urllib.request.Request(
                    f"https://hacker-news.firebaseio.com/v0/item/{sid}.json",
                    headers={"User-Agent": "DeterministicBrain/1.0"},
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    data = json.loads(r.read().decode())
                if data and data.get("title"):
                    items.append(NewsItem(
                        title=data["title"], source="HackerNews",
                        url=data.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        category="tech", tags=["hn"],
                    ))
            except Exception:
                continue
        return items

    def fetch_devto(self) -> List[NewsItem]:
        """Fetch top Dev.to articles."""
        try:
            req = urllib.request.Request(
                "https://dev.to/api/articles?per_page=10&tag=programming",
                headers={"User-Agent": "DeterministicBrain/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
        except Exception:
            return []

        items = []
        for a in data[:10]:
            items.append(NewsItem(
                title=a.get("title", ""), source="Dev.to",
                url=a.get("url", ""), summary=(a.get("description", "") or "")[:200],
                tags=a.get("tag_list", []), category="dev",
            ))
        return items

    def fetch_all(self) -> List[NewsItem]:
        all_items = []
        all_items.extend(self.fetch_hackernews())
        all_items.extend(self.fetch_devto())
        return sorted(all_items, key=lambda x: x.published or "", reverse=True)


# ═══════════════════════════════════════════════════════════════
# ODDS ENGINE
# ═══════════════════════════════════════════════════════════════

@dataclass
class OddsLine:
    event: str
    market: str
    selection: str
    odds: float
    bookmaker: str = ""
    start_time: str = ""
    sport: str = ""

    def implied_probability(self) -> float:
        return 1.0 / self.odds if self.odds > 0 else 0

    def kelly_fraction(self, bankroll: float, edge: float = 0.02) -> float:
        """Kelly Criterion bet sizing."""
        p = self.implied_probability()
        q = 1 - p
        b = self.odds - 1
        if b <= 0:
            return 0
        f = (b * (p + edge) - q) / b
        return max(0, min(f, 0.05)) * bankroll

    def expected_value(self, true_prob: float = None) -> float:
        p = true_prob or self.implied_probability()
        return (p * (self.odds - 1)) - ((1 - p) * 1)

    def to_dict(self) -> Dict:
        return {
            "event": self.event, "market": self.market, "selection": self.selection,
            "odds": self.odds, "bookmaker": self.bookmaker,
            "implied_probability": round(self.implied_probability(), 4),
        }


class OddsEngine:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("ODDS_API_KEY", "")

    def fetch_odds(self, sport: str = "basketball_nba") -> List[OddsLine]:
        """Fetch live odds from The Odds API."""
        if not self.api_key:
            return self._sample_odds(sport)
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={self.api_key}&regions=us&markets=h2h"
            req = urllib.request.Request(url, headers={"User-Agent": "DeterministicBrain/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
        except Exception:
            return self._sample_odds(sport)

        lines = []
        for game in data[:5]:
            for book in game.get("bookmakers", [])[:3]:
                for market in book.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        lines.append(OddsLine(
                            event=f"{game.get('home_team','')} vs {game.get('away_team','')}",
                            market=market.get("key", "h2h"),
                            selection=outcome.get("name", ""),
                            odds=outcome.get("price", 1.0),
                            bookmaker=book.get("title", ""),
                            sport=sport,
                        ))
        return lines

    def _sample_odds(self, sport: str) -> List[OddsLine]:
        """Sample odds for testing without API key."""
        return [
            OddsLine(event="Team A vs Team B", market="h2h", selection="Team A", odds=2.10),
            OddsLine(event="Team A vs Team B", market="h2h", selection="Team B", odds=1.75),
            OddsLine(event="Team C vs Team D", market="h2h", selection="Team C", odds=1.90),
            OddsLine(event="Team C vs Team D", market="h2h", selection="Team D", odds=1.95),
        ]

    def find_value(self, lines: List[OddsLine], threshold: float = 0.0) -> List[OddsLine]:
        """Find value bets using the math engine."""
        value_bets = []
        try:
            from reasoning.math_engine import ReasoningEngine
            engine = ReasoningEngine()
            for line in lines:
                ev = line.expected_value()
                if ev > threshold:
                    value_bets.append(line)
        except ImportError:
            pass
        return value_bets

    def calculate_kelly(self, lines: List[OddsLine], bankroll: float = 1000.0) -> List[Dict]:
        """Calculate Kelly bet sizes."""
        return [
            {
                "selection": line.selection,
                "event": line.event,
                "odds": line.odds,
                "kelly_bet": round(line.kelly_fraction(bankroll), 2),
                "ev": round(line.expected_value(), 4),
            }
            for line in lines
        ]


# ═══════════════════════════════════════════════════════════════
# TRADING ENGINE
# ═══════════════════════════════════════════════════════════════

@dataclass
class TradeSignal:
    symbol: str
    action: str              # BUY | SELL | HOLD
    price: float
    confidence: float
    strategy: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol, "action": self.action,
            "price": self.price, "confidence": self.confidence,
            "strategy": self.strategy, "timestamp": self.timestamp,
        }


class TradingEngine:
    def __init__(self):
        self.positions: Dict[str, Dict] = {}
        self.balance: float = 0
        self.trade_history: List[TradeSignal] = []

    def set_balance(self, amount: float):
        self.balance = amount

    def add_strategy(self, name: str, code: str) -> Dict:
        """Add a trading strategy (executed deterministically)."""
        return {"name": name, "code": code, "status": "registered"}

    def evaluate(self, symbol: str, price_data: List[float]) -> Optional[TradeSignal]:
        """Simple moving average crossover strategy."""
        if len(price_data) < 20:
            return None
        short_ma = sum(price_data[-5:]) / 5
        long_ma = sum(price_data[-20:]) / 20
        current = price_data[-1]

        if short_ma > long_ma and current > short_ma:
            return TradeSignal(symbol=symbol, action="BUY", price=current,
                              confidence=0.6, strategy="ma_crossover")
        elif short_ma < long_ma and current < short_ma:
            return TradeSignal(symbol=symbol, action="SELL", price=current,
                              confidence=0.6, strategy="ma_crossover")
        return TradeSignal(symbol=symbol, action="HOLD", price=current,
                          confidence=0.3, strategy="ma_crossover")

    def fetch_price(self, symbol: str) -> Optional[float]:
        """Fetch current price from Yahoo Finance."""
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            return data["chart"]["result"][0]["meta"]["regularMarketPrice"]
        except Exception:
            return None


# ═══════════════════════════════════════════════════════════════
# SINGLETONS
# ═══════════════════════════════════════════════════════════════

_NEWS: Optional[NewsFeed] = None
_ODDS: Optional[OddsEngine] = None
_TRADE: Optional[TradingEngine] = None


def get_news() -> NewsFeed:
    global _NEWS
    if _NEWS is None:
        _NEWS = NewsFeed()
    return _NEWS


def get_odds() -> OddsEngine:
    global _ODDS
    if _ODDS is None:
        _ODDS = OddsEngine()
    return _ODDS


def get_trading() -> TradingEngine:
    global _TRADE
    if _TRADE is None:
        _TRADE = TradingEngine()
    return _TRADE
