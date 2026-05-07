"""Stripe + Coinbase API clients — payments, subscriptions, crypto prices.

Token savings: ~400 tokens per payment/crypto call.
"""

from __future__ import annotations
import os
from typing import Dict

from tools.api_client import AuthenticatedClient


class StripeClient:
    """Stripe API — payments, subscriptions, invoices."""

    def __init__(self, api_key: str = ""):
        self.client = AuthenticatedClient(
            base_url="https://api.stripe.com/v1",
            api_key=api_key or os.environ.get("STRIPE_API_KEY", ""),
            auth_prefix="",
        )

    def list_customers(self) -> Dict:
        return self.client.get("/customers")

    def list_subscriptions(self, customer: str = "") -> Dict:
        params = {"customer": customer} if customer else None
        return self.client.get("/subscriptions", params=params)

    def create_payment_intent(self, amount_cents: int, currency: str = "usd") -> Dict:
        return self.client.post("/payment_intents",
                               data={"amount": amount_cents, "currency": currency})

    def list_invoices(self, limit: int = 10) -> Dict:
        return self.client.get("/invoices", params={"limit": limit})


class CoinbaseClient:
    """Coinbase API — spot prices, accounts, transactions."""

    BASE_URL = "https://api.coinbase.com/v2"

    def __init__(self, api_key: str = ""):
        self.key = api_key or os.environ.get("COINBASE_API_KEY", "")

    def spot_price(self, currency_pair: str = "BTC-USD") -> Dict:
        import urllib.request, json
        try:
            url = f"{self.BASE_URL}/prices/{currency_pair}/spot"
            with urllib.request.urlopen(url, timeout=10) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def exchange_rates(self, currency: str = "USD") -> Dict:
        import urllib.request, json
        try:
            url = f"{self.BASE_URL}/exchange-rates?currency={currency}"
            with urllib.request.urlopen(url, timeout=10) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}
