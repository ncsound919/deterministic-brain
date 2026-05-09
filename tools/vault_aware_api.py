"""Unified credential resolver for API clients.

Every tool client should use `get_key()` to resolve credentials:
  1. Check the given argument (explicit)
  2. Check env var (OS environment)
  3. Check the encrypted credential vault (fallback)

This eliminates the naming mismatch problem — clients ask by vault
category/key and get the right value regardless of env var name.
"""

from __future__ import annotations

import os


def get_key(*, vault_category: str, vault_key: str,
            env_var: str = "", explicit: str = "") -> str:
    """Resolve an API key from explicit arg → env var → credential vault.

    Args:
        vault_category: Category in the credential vault (e.g. "cloudflare")
        vault_key: Key within that category (e.g. "api_token")
        env_var: Environment variable name to check (e.g. "CF_API_TOKEN")
        explicit: Explicit value provided by caller (wins if set)
    """
    if explicit:
        return explicit

    if env_var:
        val = os.getenv(env_var, "")
        if val:
            return val

    try:
        from config.credentials import get_credential_vault
        vault = get_credential_vault()
        val = vault.get(vault_category, vault_key)
        if val:
            return val
    except ImportError:
        pass

    return ""


def get_keys(*keys: tuple) -> dict:
    """Resolve multiple API keys at once. Each tuple is
    (vault_category, vault_key, env_var, explicit_value).
    Returns a dict of vault_key → resolved_value.
    """
    result = {}
    for cat, key, env, explicit in keys:
        result[key] = get_key(
            vault_category=cat, vault_key=key,
            env_var=env, explicit=explicit,
        )
    return result
