"""URL safety validation — SSRF guard for outbound fetches.

Blocks: non-HTTP(S) schemes (file://, gopher://, ...), loopback, private,
link-local (169.254.169.254 cloud metadata), and reserved IP ranges.

Set ``BRAIN_ALLOW_PRIVATE_URLS=1`` only when a trusted local service must be
reachable (e.g. local Gemma server) — this disables the IP-range checks but
keeps the scheme restriction.
"""
from __future__ import annotations

import ipaddress
import os
import socket
import urllib.parse


class UrlBlockedError(ValueError):
    """Raised when a URL fails SSRF validation."""


def _allow_private() -> bool:
    return os.getenv("BRAIN_ALLOW_PRIVATE_URLS", "").lower() in ("1", "true", "yes")


def validate_url(url: str) -> str:
    """Validate an outbound URL. Returns the normalized URL string.

    Raises UrlBlockedError when the URL targets a disallowed scheme or host.
    """
    if not url or not isinstance(url, str):
        raise UrlBlockedError("Empty URL")

    parsed = urllib.parse.urlsplit(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise UrlBlockedError(f"Scheme not allowed: {scheme or '(none)'}")

    hostname = parsed.hostname
    if not hostname:
        raise UrlBlockedError("URL has no hostname")

    # Reject embedded credentials
    if parsed.username or parsed.password:
        raise UrlBlockedError("Embedded credentials not allowed")

    if _allow_private():
        return url.strip()

    # Literal IPs first, then DNS resolution (all resolved addrs must be public)
    candidates: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    try:
        candidates.append(ipaddress.ip_address(hostname))
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
        except socket.gaierror as e:
            raise UrlBlockedError(f"Cannot resolve host: {hostname}") from e
        for info in infos:
            try:
                candidates.append(ipaddress.ip_address(info[4][0]))
            except ValueError:
                continue

    for ip in candidates:
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UrlBlockedError(f"Host resolves to blocked address: {ip}")

    return url.strip()
