"""Market data client — crypto prices (Coinbase public API) + stock prices (Yahoo).

All data-in only — no trading, no auth required for public endpoints.
Feeds the Monte Carlo bettor and dashboard stat cards.

Token savings: ~400 tokens per market data query vs LLM.
"""

from __future__ import annotations
import json
import time
from typing import Dict, List
from urllib.request import urlopen


class MarketDataClient:
    """Free, no-auth market data for crypto and stocks."""

    # Coinbase public API — no key needed for spot prices
    COINBASE_BASE = "https://api.coinbase.com/v2"

    def crypto_price(self, pair: str = "BTC-USD") -> Dict:
        try:
            url = f"{self.COINBASE_BASE}/prices/{pair}/spot"
            with urlopen(url, timeout=10) as r:
                data = json.loads(r.read())
            return {"ok": True, "pair": pair, "price": data["data"]["amount"],
                    "currency": data["data"]["currency"]}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def crypto_prices(self) -> List[Dict]:
        pairs = ["BTC-USD", "ETH-USD", "SOL-USD", "USDT-USD", "DOGE-USD"]
        results = []
        for pair in pairs:
            r = self.crypto_price(pair)
            if r.get("ok"):
                results.append(r)
            time.sleep(0.1)  # rate limit
        return results

    def exchange_rates(self, currency: str = "USD") -> Dict:
        try:
            url = f"{self.COINBASE_BASE}/exchange-rates?currency={currency}"
            with urlopen(url, timeout=10) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def stock_prices(self, symbols: List[str] = None) -> Dict:
        """Yahoo Finance free lookup via yfinance package."""
        try:
            import yfinance as yf
            syms = symbols or ["AAPL", "GOOGL", "MSFT", "NVDA", "TSLA", "SPY"]
            results = {}
            for sym in syms:
                try:
                    t = yf.Ticker(sym)
                    info = t.fast_info
                    results[sym] = {
                        "price": getattr(info, "last_price", None),
                        "day_high": getattr(info, "day_high", None),
                        "day_low": getattr(info, "day_low", None),
                    }
                except Exception:
                    results[sym] = {"error": "unavailable"}
            return {"ok": True, "data": results, "timestamp": time.time()}
        except ImportError:
            return {"ok": False, "error": "yfinance not installed. Run: pip install yfinance"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def market_summary(self) -> Dict:
        """One call to get all market data for dashboard display."""
        return {
            "crypto": self.crypto_prices(),
            "rates": self.exchange_rates(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
