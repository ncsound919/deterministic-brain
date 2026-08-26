"""API key authentication middleware.

Enforcement is controlled by the ``BRAIN_API_KEY`` environment variable:

- **BRAIN_API_KEY unset** — open access, intended for local development.
  In this mode bind the server to loopback (127.0.0.1) only.
- **BRAIN_API_KEY set** — every request must present an ``X-API-Key`` header
  whose value matches (constant-time comparison). Health probes, OpenAPI
  docs, and CORS preflight requests are exempt.

Set ``BRAIN_PUBLIC_PATHS`` (comma-separated) to expose additional paths.
"""
from __future__ import annotations

import hmac
import os
from typing import Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

API_KEY_HEADER = "X-API-Key"

_DEFAULT_PUBLIC_PATHS: Sequence[str] = (
    "/health",
    "/healthz",
    "/livez",
    "/readyz",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def get_api_key() -> str:
    """Return the configured API key ('' when unconfigured)."""
    return os.getenv("BRAIN_API_KEY", "").strip()


def is_auth_configured() -> bool:
    """True when BRAIN_API_KEY is set — middleware will enforce it."""
    return bool(get_api_key())


def _public_paths() -> frozenset:
    extra = [p.strip() for p in os.getenv("BRAIN_PUBLIC_PATHS", "").split(",") if p.strip()]
    return frozenset(_DEFAULT_PUBLIC_PATHS) | frozenset(extra)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Enforces X-API-Key on all routes when BRAIN_API_KEY is configured."""

    async def dispatch(self, request: Request, call_next):
        if (
            not is_auth_configured()
            or request.method == "OPTIONS"
            or request.url.path in _public_paths()
        ):
            return await call_next(request)

        provided = request.headers.get(API_KEY_HEADER, "")
        if not hmac.compare_digest(provided.encode("utf-8"), get_api_key().encode("utf-8")):
            return JSONResponse(
                {"detail": "Invalid or missing API key"}, status_code=401
            )
        return await call_next(request)
