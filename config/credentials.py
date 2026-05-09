"""Credential Vault — encrypted at-rest storage for API keys, tokens, logins.

Uses Fernet symmetric encryption. Master key from BRAIN_MASTER_KEY env var
or auto-generated on first boot and persisted to .brain_key.

Category-based typed access:
  - github      → token, webhook_secret
  - openrouter  → api_key
  - email_smtp  → host, port, user, password, from_addr
  - stripe      → secret_key, publishable_key, webhook_secret
  - social      → twitter_*, linkedin_*, bluesky_*
  - cloudflare  → api_token, zone_id, account_id
  - bank        → plaid_client_id, plaid_secret, plaid_access_token
  - qdrant      → url, api_key
  - neo4j       → uri, user, password
  - tavily      → api_key

Never logs or exposes values. __repr__ always redacts.
"""

from __future__ import annotations

import base64
import json
import os
import threading
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


_KEY_PATH = ".brain_key"
_VAULT_PATH = ".credentials.enc"
_KEY_ENV = "BRAIN_MASTER_KEY"


def _derive_key(master_key: str) -> bytes:
    salt = b"deterministic_brain_v1"
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
    return base64.urlsafe_b64encode(kdf.derive(master_key.encode("utf-8")))


def _load_or_create_key() -> bytes:
    env_key = os.getenv(_KEY_ENV, "").strip()
    if env_key:
        return _derive_key(env_key)

    key_path = Path(_KEY_PATH)
    if key_path.exists():
        return key_path.read_bytes()

    key = Fernet.generate_key()
    key_path.write_bytes(key)
    key_path.chmod(0o600)
    return key


class CredentialVault:
    """Encrypted credential store with category-based typed access.

    Credential categories and their expected keys:

        github:       token, webhook_secret
        openrouter:   api_key
        email_smtp:   host, port, user, password, from_addr
        stripe:       secret_key, publishable_key, webhook_secret
        social:       twitter_api_key, twitter_api_secret,
                      twitter_access_token, twitter_access_secret,
                      linkedin_token, bluesky_handle, bluesky_app_password
        cloudflare:   api_token, zone_id, account_id
        bank:         plaid_client_id, plaid_secret, plaid_access_token
        qdrant:       url, api_key
        neo4j:        uri, user, password
        tavily:       api_key
    """

    def __init__(self, vault_path: str = _VAULT_PATH):
        self._vault_path = Path(vault_path)
        self._lock = threading.Lock()
        self._key = _load_or_create_key()
        self._fernet = Fernet(self._key)
        self._data: Dict[str, Dict[str, str]] = {}
        self._load()

    def _load(self) -> None:
        if not self._vault_path.exists():
            return
        try:
            encrypted = self._vault_path.read_bytes()
            decrypted = self._fernet.decrypt(encrypted)
            self._data = json.loads(decrypted)
        except (InvalidToken, json.JSONDecodeError, ValueError):
            pass

    def _save(self) -> None:
        plain = json.dumps(self._data, separators=(",", ":"))
        encrypted = self._fernet.encrypt(plain.encode("utf-8"))
        self._vault_path.write_bytes(encrypted)
        self._vault_path.chmod(0o600)

    def set_category(self, category: str, entries: Dict[str, str]) -> None:
        """Set all entries for a credential category."""
        with self._lock:
            self._data[category] = dict(entries)
            self._save()

    def set(self, category: str, key: str, value: str) -> None:
        """Set a single credential key in a category."""
        with self._lock:
            self._data.setdefault(category, {})[key] = value
            self._save()

    def get(self, category: str, key: str, default: str = "") -> str:
        with self._lock:
            return self._data.get(category, {}).get(key, default)

    def get_category(self, category: str) -> Dict[str, str]:
        with self._lock:
            return dict(self._data.get(category, {}))

    def delete(self, category: str, key: str) -> bool:
        with self._lock:
            cat = self._data.get(category)
            if cat and key in cat:
                del cat[key]
                if not cat:
                    del self._data[category]
                self._save()
                return True
            return False

    def delete_category(self, category: str) -> bool:
        with self._lock:
            if category in self._data:
                del self._data[category]
                self._save()
                return True
            return False

    def list_categories(self) -> list[str]:
        with self._lock:
            return sorted(self._data.keys())

    def list_keys(self, category: str) -> list[str]:
        with self._lock:
            return sorted(self._data.get(category, {}).keys())

    def categories(self) -> Dict[str, list[str]]:
        with self._lock:
            return {cat: sorted(sub.keys()) for cat, sub in self._data.items()}

    def sync_to_env(self) -> None:
        """Export known credentials to environment variables for libraries
        that read from env vars directly.

        Maps vault categories to the env var names that API clients expect.
        Some keys map to multiple env vars to support different client conventions.
        """
        env_map = {
            # GitHub
            ("github", "token"): "GITHUB_TOKEN",
            ("github", "webhook_secret"): "GITHUB_WEBHOOK_SECRET",
            # OpenRouter
            ("openrouter", "api_key"): "OPENROUTER_API_KEY",
            # Stripe (webhook and api_key for finance_client)
            ("stripe", "secret_key"): ["STRIPE_SECRET_KEY", "STRIPE_API_KEY"],
            ("stripe", "publishable_key"): "STRIPE_PUBLISHABLE_KEY",
            ("stripe", "webhook_secret"): "STRIPE_WEBHOOK_SECRET",
            # Cloudflare (api_token → both CF_API_TOKEN and CLOUDFLARE_API_TOKEN)
            ("cloudflare", "api_token"): ["CF_API_TOKEN", "CLOUDFLARE_API_TOKEN"],
            ("cloudflare", "zone_id"): ["CF_ZONE_ID", "CLOUDFLARE_ZONE_ID"],
            ("cloudflare", "account_id"): ["CF_ACCOUNT_ID", "CLOUDFLARE_ACCOUNT_ID"],
            # Tavily
            ("tavily", "api_key"): "TAVILY_API_KEY",
            # Qdrant
            ("qdrant", "url"): "QDRANT_URL",
            ("qdrant", "api_key"): "QDRANT_API_KEY",
            # Neo4j
            ("neo4j", "uri"): "NEO4J_URI",
            ("neo4j", "user"): "NEO4J_USER",
            ("neo4j", "password"): "NEO4J_PASSWORD",
            # Anthropic / Claude
            ("anthropic", "api_key"): "ANTHROPIC_API_KEY",
            # DeepSeek
            ("deepseek", "api_key"): "DEEPSEEK_API_KEY",
            # XAI / Grok
            ("xai", "api_key"): "XAI_API_KEY",
            # Discord
            ("discord", "bot_token"): "DISCORD_BOT_TOKEN",
            ("discord", "bot_id"): "DISCORD_BOT_ID",
            ("discord", "webhook_url"): "DISCORD_WEBHOOK_URL",
            # News APIs
            ("newsapi", "api_key"): "NEWSAPI_KEY",
            ("gnews", "api_key"): "GNEWS_API_KEY",
            ("worldnews", "api_key"): "WORLDNEWS_API_KEY",
            # Finance
            ("coinbase", "api_key"): "COINBASE_API_KEY",
            ("alphavantage", "api_key"): "ALPHA_VANTAGE_API_KEY",
            ("coingecko", "api_key"): "COINGECKO_API_KEY",
            ("odds", "api_key"): "ODDS_API_KEY",
            ("openweather", "api_key"): "OPENWEATHER_API_KEY",
            ("googlemaps", "api_key"): "GOOGLE_MAPS_API_KEY",
            # Email SMTP
            ("email_smtp", "host"): "SMTP_HOST",
            ("email_smtp", "port"): "SMTP_PORT",
            ("email_smtp", "user"): "SMTP_USER",
            ("email_smtp", "password"): "SMTP_PASS",
            ("email_smtp", "from_addr"): "SMTP_FROM",
            # Google (mirrors email_smtp for Gmail users)
            ("google", "email"): ["SMTP_USER", "SMTP_FROM"],
            ("google", "app_password"): "SMTP_PASS",
            ("google", "maps_api_key"): "GOOGLE_MAPS_API_KEY",
            ("google", "drive_api_key"): "GOOGLE_DRIVE_API_KEY",
            ("google", "youtube_api_key"): "YOUTUBE_API_KEY",
            ("google", "oauth_client_id"): "GOOGLE_CLIENT_ID",
            ("google", "oauth_client_secret"): "GOOGLE_CLIENT_SECRET",
            ("google", "refresh_token"): "GOOGLE_REFRESH_TOKEN",
            ("google", "calendar_id"): "GOOGLE_CALENDAR_ID",
        }
        with self._lock:
            for (cat, key), env_var in env_map.items():
                val = self._data.get(cat, {}).get(key)
                if val:
                    if isinstance(env_var, list):
                        for ev in env_var:
                            os.environ[ev] = val
                    else:
                        os.environ[env_var] = val

    def is_empty(self) -> bool:
        with self._lock:
            return not bool(self._data)

    def stats(self) -> Dict:
        with self._lock:
            return {
                "categories": len(self._data),
                "total_keys": sum(len(v) for v in self._data.values()),
                "categories_list": sorted(self._data.keys()),
            }

    def __repr__(self) -> str:
        return f"<CredentialVault categories={len(self._data)}>"

    def __str__(self) -> str:
        return repr(self)


_VAULT: Optional[CredentialVault] = None


def get_credential_vault() -> CredentialVault:
    global _VAULT
    if _VAULT is None:
        _VAULT = CredentialVault()
    return _VAULT


def reset_credential_vault() -> CredentialVault:
    global _VAULT
    _VAULT = CredentialVault()
    return _VAULT
