"""Stripe + Coinbase API clients — payments, subscriptions, crypto.

Now vault-aware: checks explicit arg → env var → credential vault.
"""

from __future__ import annotations
from typing import Dict

from tools.api_client import AuthenticatedClient
from tools.vault_aware_api import get_key


class StripeClient:
    """Stripe API — payments, subscriptions, invoices."""

    def __init__(self, api_key: str = ""):
        key = get_key(
            vault_category="stripe", vault_key="secret_key",
            env_var="STRIPE_API_KEY", explicit=api_key,
        )
        self.client = AuthenticatedClient(
            base_url="https://api.stripe.com/v1",
            api_key=key,
            auth_header="Authorization",
            auth_prefix="Bearer ",
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

    def balance(self) -> Dict:
        return self.client.get("/balance")


class CoinbaseClient:
    """Coinbase API — spot prices, accounts, transactions."""

    BASE_URL = "https://api.coinbase.com/v2"

    def __init__(self, api_key: str = ""):
        self.key = get_key(
            vault_category="coinbase", vault_key="api_key",
            env_var="COINBASE_API_KEY", explicit=api_key,
        )

    def spot_price(self, currency_pair: str = "BTC-USD") -> Dict:
        import urllib.request
        import json
        try:
            url = f"{self.BASE_URL}/prices/{currency_pair}/spot"
            req = urllib.request.Request(url)
            if self.key:
                req.add_header("Authorization", f"Bearer {self.key}")
            with urllib.request.urlopen(req, timeout=10) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def exchange_rates(self, currency: str = "USD") -> Dict:
        import urllib.request
        import json
        try:
            url = f"{self.BASE_URL}/exchange-rates?currency={currency}"
            req = urllib.request.Request(url)
            if self.key:
                req.add_header("Authorization", f"Bearer {self.key}")
            with urllib.request.urlopen(req, timeout=10) as r:
                return {"ok": True, "data": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}
