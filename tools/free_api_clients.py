"""Free API clients — Alpha Vantage, CoinGecko, OpenWeather, Odds API.

All clients read from the credential vault. Many free tiers don't need
API keys at all (CoinGecko public, Open-Meteo).
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List

from tools.vault_aware_api import get_key


# ═══════════════════════════════════════════════════════════════════════
# Alpha Vantage — Stock market data (free tier: 25 req/day)
# ═══════════════════════════════════════════════════════════════════════

class AlphaVantageClient:
    """Alpha Vantage — stocks, forex, crypto, indicators.
    https://www.alphavantage.co — FREE API key.
    """

    BASE = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str = ""):
        self.key = get_key(
            vault_category="alphavantage", vault_key="api_key",
            env_var="ALPHA_VANTAGE_API_KEY", explicit=api_key,
        )

    def _query(self, **params) -> Dict:
        params["apikey"] = self.key
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                      for k, v in params.items() if v)
        try:
            with urllib.request.urlopen(f"{self.BASE}?{qs}", timeout=15) as r:
                return json.loads(r.read())
        except Exception as e:
            return {"error": str(e)}

    def quote(self, symbol: str) -> Dict:
        return self._query(function="GLOBAL_QUOTE", symbol=symbol)

    def daily(self, symbol: str, outputsize: str = "compact") -> Dict:
        return self._query(function="TIME_SERIES_DAILY",
                          symbol=symbol, outputsize=outputsize)

    def intraday(self, symbol: str, interval: str = "5min") -> Dict:
        return self._query(function="TIME_SERIES_INTRADAY",
                          symbol=symbol, interval=interval)

    def forex(self, from_currency: str = "USD",
              to_currency: str = "EUR") -> Dict:
        return self._query(function="CURRENCY_EXCHANGE_RATE",
                          from_currency=from_currency,
                          to_currency=to_currency)

    def crypto(self, symbol: str = "BTC", market: str = "USD") -> Dict:
        return self._query(function="DIGITAL_CURRENCY_DAILY",
                          symbol=symbol, market=market)

    def news_sentiment(self, tickers: str = "",
                       topics: str = "", limit: int = 10) -> Dict:
        params = {"function": "NEWS_SENTIMENT", "limit": limit}
        if tickers:
            params["tickers"] = tickers
        if topics:
            params["topics"] = topics
        return self._query(**params)


# ═══════════════════════════════════════════════════════════════════════
# CoinGecko — Crypto prices, trends, exchanges (public API, no key)
# ═══════════════════════════════════════════════════════════════════════

class CoinGeckoClient:
    """CoinGecko — crypto market data.
    https://www.coingecko.com/en/api — FREE, no key for basic tier.
    """

    BASE = "https://api.coingecko.com/api/v3"

    def __init__(self, api_key: str = ""):
        self.key = get_key(
            vault_category="coingecko", vault_key="api_key",
            env_var="COINGECKO_API_KEY", explicit=api_key,
        )

    def _get(self, path: str, params: Dict = None) -> Dict:
        url = f"{self.BASE}{path}"
        if params:
            qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                          for k, v in params.items() if v)
            url += f"?{qs}"
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        if self.key:
            req.add_header("x-cg-demo-api-key", self.key)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def ping(self) -> Dict:
        return self._get("/ping")

    def price(self, ids: str = "bitcoin,ethereum", vs: str = "usd") -> Dict:
        return self._get("/simple/price", {"ids": ids, "vs_currencies": vs})

    def trending(self) -> Dict:
        return self._get("/search/trending")

    def top_coins(self, vs: str = "usd", per_page: int = 20) -> Dict:
        return self._get("/coins/markets", {
            "vs_currency": vs, "order": "market_cap_desc",
            "per_page": per_page, "page": 1,
            "sparkline": "false",
        })

    def coin_detail(self, coin_id: str = "bitcoin") -> Dict:
        return self._get(f"/coins/{coin_id}",
                        {"localization": "false", "tickers": "false",
                         "community_data": "false", "developer_data": "false"})

    def global_data(self) -> Dict:
        return self._get("/global")


# ═══════════════════════════════════════════════════════════════════════
# Open-Meteo — Weather (completely FREE, no API key needed)
# ═══════════════════════════════════════════════════════════════════════

class OpenMeteoClient:
    """Open-Meteo — free weather API, no key required.
    https://open-meteo.com — 10,000 req/day free.
    """

    BASE = "https://api.open-meteo.com/v1"

    def _get(self, path: str, params: Dict) -> Dict:
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                      for k, v in params.items() if v is not None)
        try:
            with urllib.request.urlopen(f"{self.BASE}/{path}?{qs}", timeout=10) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def forecast(self, latitude: float, longitude: float,
                 hourly: str = "temperature_2m,precipitation,weathercode",
                 daily: str = "temperature_2m_max,temperature_2m_min,precipitation_sum",
                 timezone: str = "auto") -> Dict:
        return self._get("forecast", {
            "latitude": latitude, "longitude": longitude,
            "hourly": hourly, "daily": daily, "timezone": timezone,
            "forecast_days": 3,
        })

    def current(self, latitude: float, longitude: float) -> Dict:
        return self._get("forecast", {
            "latitude": latitude, "longitude": longitude,
            "current_weather": "true",
        })


# ═══════════════════════════════════════════════════════════════════════
# OpenWeather — Weather (free tier: 1,000 req/day)
# ═══════════════════════════════════════════════════════════════════════

class OpenWeatherClient:
    """OpenWeather — current weather, forecast, air quality.
    https://openweathermap.org/api — FREE API key required.
    """

    BASE = "https://api.openweathermap.org/data/2.5"

    def __init__(self, api_key: str = ""):
        self.key = get_key(
            vault_category="openweather", vault_key="api_key",
            env_var="OPENWEATHER_API_KEY", explicit=api_key,
        )

    def _get(self, path: str, params: Dict) -> Dict:
        params["appid"] = self.key
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                      for k, v in params.items() if v)
        try:
            with urllib.request.urlopen(f"{self.BASE}/{path}?{qs}", timeout=10) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def current(self, city: str = "", lat: float = None,
                lon: float = None, units: str = "imperial") -> Dict:
        params = {"units": units}
        if lat is not None and lon is not None:
            params["lat"] = lat
            params["lon"] = lon
        elif city:
            params["q"] = city
        else:
            params["q"] = "New York"
        return self._get("weather", params)

    def forecast(self, city: str = "New York", units: str = "imperial") -> Dict:
        return self._get("forecast", {"q": city, "units": units})


# ═══════════════════════════════════════════════════════════════════════
# Odds API — Sports betting odds (free tier: 500 req/month)
# ═══════════════════════════════════════════════════════════════════════

class OddsAPIClient:
    """The Odds API — live sports betting odds.
    https://the-odds-api.com — FREE API key with 500 req/month.
    """

    BASE = "https://api.the-odds-api.com/v4"

    def __init__(self, api_key: str = ""):
        self.key = get_key(
            vault_category="odds", vault_key="api_key",
            env_var="ODDS_API_KEY", explicit=api_key,
        )

    def _get(self, path: str, params: Dict = None) -> Dict:
        url = f"{self.BASE}{path}"
        params = params or {}
        params["apiKey"] = self.key
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                      for k, v in params.items() if v)
        try:
            with urllib.request.urlopen(f"{url}?{qs}", timeout=15) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def sports(self) -> Dict:
        return self._get("/sports")

    def odds(self, sport: str = "basketball_nba",
             regions: str = "us", markets: str = "h2h,spreads") -> Dict:
        return self._get(f"/sports/{sport}/odds", {
            "regions": regions, "markets": markets,
        })

    def scores(self, sport: str = "basketball_nba",
               days_from: int = 1) -> Dict:
        return self._get(f"/sports/{sport}/scores",
                        {"daysFrom": days_from})


# ═══════════════════════════════════════════════════════════════════════
# Unified market data aggregator
# ═══════════════════════════════════════════════════════════════════════

def get_market_data() -> Dict:
    """Fetch market data from all configured providers in parallel."""
    result = {"timestamp": datetime.now(timezone.utc).isoformat()}

    try:
        cg = CoinGeckoClient()
        result["crypto"] = cg.top_coins(per_page=10)
    except Exception as e:
        result["crypto"] = {"error": str(e)}

    try:
        av = AlphaVantageClient()
        if av.key:
            result["stocks"] = {
                "SPY": av.quote("SPY"),
                "QQQ": av.quote("QQQ"),
                "AAPL": av.quote("AAPL"),
            }
    except Exception as e:
        result["stocks"] = {"error": str(e)}

    return result


# ═══════════════════════════════════════════════════════════════════════
# MORE FREE APIs — no keys needed for most
# ═══════════════════════════════════════════════════════════════════════

class FrankfurterClient:
    """Frankfurter — currency exchange rates (free, no key).
    https://www.frankfurter.app — European Central Bank rates.
    """

    BASE = "https://api.frankfurter.app"

    def _get(self, path: str) -> Dict:
        try:
            req = urllib.request.Request(f"{self.BASE}{path}")
            req.add_header("User-Agent", "DeterministicBrain/1.0")
            with urllib.request.urlopen(req, timeout=10) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def latest(self, base: str = "USD", symbols: str = "") -> Dict:
        path = f"/latest?from={base}"
        if symbols:
            path += f"&to={urllib.request.quote(symbols, safe=',')}"
        return self._get(path)

    def historical(self, date: str, base: str = "USD") -> Dict:
        return self._get(f"/{date}?from={base}")

    def currencies(self) -> Dict:
        return self._get("/currencies")


class HackerNewsClient:
    """HackerNews API (free, no key).
    https://github.com/HackerNews/API — Firebase-based.
    """

    BASE = "https://hacker-news.firebaseio.com/v0"

    def _get(self, path: str) -> Dict:
        try:
            with urllib.request.urlopen(f"{self.BASE}{path}", timeout=10) as r:
                return json.loads(r.read())
        except Exception:
            return {}

    def top_stories(self, limit: int = 20) -> List[Dict]:
        ids = self._get("/topstories.json")
        if isinstance(ids, list):
            stories = []
            for sid in ids[:limit]:
                s = self._get(f"/item/{sid}.json")
                if s:
                    stories.append({
                        "id": s.get("id"), "title": s.get("title", ""),
                        "url": s.get("url", ""), "score": s.get("score", 0),
                        "by": s.get("by", ""), "descendants": s.get("descendants", 0),
                    })
            return stories
        return []

    def new_stories(self, limit: int = 20) -> List[Dict]:
        ids = self._get("/newstories.json")
        if isinstance(ids, list):
            return [self._get(f"/item/{sid}.json") for sid in ids[:limit]]
        return []

    def best_stories(self, limit: int = 10) -> List[Dict]:
        ids = self._get("/beststories.json")
        if isinstance(ids, list):
            stories = []
            for sid in ids[:limit]:
                s = self._get(f"/item/{sid}.json")
                if s:
                    stories.append({
                        "id": s.get("id"), "title": s.get("title", ""),
                        "url": s.get("url", ""), "score": s.get("score", 0),
                    })
            return stories
        return []

    def ask_hn(self, limit: int = 10) -> List[Dict]:
        ids = self._get("/askstories.json")
        if isinstance(ids, list):
            return [self._get(f"/item/{sid}.json") for sid in ids[:limit]]
        return []

    def show_hn(self, limit: int = 10) -> List[Dict]:
        ids = self._get("/showstories.json")
        if isinstance(ids, list):
            return [self._get(f"/item/{sid}.json") for sid in ids[:limit]]
        return []


class WikipediaClient:
    """Wikipedia API (free, no key).
    https://en.wikipedia.org/api/rest_v1
    """

    BASE = "https://en.wikipedia.org/api/rest_v1"

    def _get(self, path: str) -> Dict:
        try:
            req = urllib.request.Request(f"{self.BASE}{path}")
            req.add_header("User-Agent", "DeterministicBrain/1.0")
            with urllib.request.urlopen(req, timeout=15) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def summary(self, title: str) -> Dict:
        """Get a short summary of any Wikipedia article."""
        return self._get(f"/page/summary/{urllib.request.quote(title)}")

    def search(self, query: str, limit: int = 10) -> Dict:
        """Search Wikipedia for articles."""
        try:
            url = f"{self.BASE}/page/summary/{urllib.request.quote(query)}"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "DeterministicBrain/1.0")
            with urllib.request.urlopen(req, timeout=15) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def on_this_day(self, month: int = 0, day: int = 0) -> Dict:
        """What happened on this day in history (from Wikipedia REST API)."""
        from datetime import datetime
        if not month or not day:
            now = datetime.now()
            month = now.month
            day = now.day
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/events/{month}/{day}"
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "DeterministicBrain/1.0")
            with urllib.request.urlopen(req, timeout=15) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def featured_article(self, date: str = "") -> Dict:
        """Wikipedia featured article for a given date."""
        if not date:
            from datetime import datetime
            date = datetime.now().strftime("%Y/%m/%d")
        return self._get(f"/feed/featured/{date}")


class DatamuseClient:
    """Datamuse — word relationships, rhymes, thesaurus (free, no key).
    https://www.datamuse.com/api
    """

    BASE = "https://api.datamuse.com/words"

    def _get(self, params: Dict) -> List[Dict]:
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                      for k, v in params.items())
        try:
            with urllib.request.urlopen(f"{self.BASE}?{qs}", timeout=10) as r:
                return json.loads(r.read())
        except Exception:
            return []

    def rhymes(self, word: str, max_results: int = 20) -> List[Dict]:
        return self._get({"rel_rhy": word, "max": max_results})

    def synonyms(self, word: str, max_results: int = 20) -> List[Dict]:
        return self._get({"ml": word, "max": max_results})

    def related(self, word: str, max_results: int = 20) -> List[Dict]:
        return self._get({"rel_jjb": word, "max": max_results})

    def sounds_like(self, word: str, max_results: int = 20) -> List[Dict]:
        return self._get({"sl": word, "max": max_results})


class JokeAPIClient:
    """JokeAPI — programming, dark, pun jokes (free, no key).
    https://v2.jokeapi.dev
    """

    BASE = "https://v2.jokeapi.dev/joke"

    def get(self, categories: str = "Any", blacklist: str = "nsfw,religious") -> Dict:
        try:
            url = f"{self.BASE}/{categories}?blacklistFlags={blacklist}&type=single,twopart"
            with urllib.request.urlopen(url, timeout=10) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}


class NumbersAPIClient:
    """NumbersAPI — fun facts about numbers (free, no key).
    http://numbersapi.com
    """

    BASE = "http://numbersapi.com"

    def fact(self, number: str = "random", kind: str = "trivia") -> Dict:
        try:
            url = f"{self.BASE}/{number}/{kind}?json"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
                return {"ok": True, "data": data}
        except Exception:
            try:
                url = f"{self.BASE}/{number}/{kind}?format=json"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read())
                    return {"ok": True, "data": data}
            except Exception:
                try:
                    url = f"{self.BASE}/{number}/{kind}"
                    with urllib.request.urlopen(url, timeout=10) as r:
                        text = r.read().decode("utf-8")
                        return {"ok": True, "data": {"text": text, "number": number, "type": kind}}
                except Exception as e2:
                    return {"ok": False, "error": str(e2)}


def get_free_dashboard() -> Dict:
    """Aggregate all free API data into a single dashboard snapshot."""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # HackerNews top 5
    try:
        hn = HackerNewsClient()
        result["hackernews"] = hn.top_stories(5)
    except Exception as e:
        result["hackernews"] = {"error": str(e)}

    # Exchange rates (EUR, GBP, JPY vs USD)
    try:
        ff = FrankfurterClient()
        result["exchange_rates"] = ff.latest("USD", "EUR,GBP,JPY,CAD,AUD")
    except Exception as e:
        result["exchange_rates"] = {"error": str(e)}

    # On this day in history
    try:
        wp = WikipediaClient()
        result["on_this_day"] = wp.on_this_day()
    except Exception as e:
        result["on_this_day"] = {"error": str(e)}

    return result

