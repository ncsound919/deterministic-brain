"""Generic authenticated API client — reusable for all third-party integrations.

Replaces LLM calls to "fetch data from X API" with deterministic HTTP requests.
Token savings: ~500 tokens per API call that would otherwise go through an LLM.
"""

from __future__ import annotations
import json
import time
from typing import Dict, List
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode


class AuthenticatedClient:
    """API client with Bearer/API-Key auth, rate limiting, and retry."""

    def __init__(self, base_url: str, api_key: str = "",
                 auth_header: str = "Authorization",
                 auth_prefix: str = "Bearer "):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.auth_header = auth_header
        self.auth_prefix = auth_prefix
        self._rate_limit_remaining = 100
        self._rate_limit_reset = 0.0

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json", "User-Agent": "deterministic-brain/2.5"}
        if self.api_key:
            h[self.auth_header] = f"{self.auth_prefix}{self.api_key}"
        return h

    def get(self, path: str, params: Dict = None) -> Dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, data: Dict = None) -> Dict:
        return self._request("POST", path, data=data)

    def put(self, path: str, data: Dict = None) -> Dict:
        return self._request("PUT", path, data=data)

    def delete(self, path: str) -> Dict:
        return self._request("DELETE", path)

    def _request(self, method: str, path: str,
                 params: Dict = None, data: Dict = None) -> Dict:
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urlencode(params)

        body = json.dumps(data).encode() if data else None
        req = Request(url, data=body, headers=self._headers(), method=method)

        for attempt in range(3):
            try:
                with urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read().decode())
                    # Track rate limits
                    reset = resp.headers.get("X-RateLimit-Reset") or resp.headers.get("Retry-After")
                    if reset:
                        self._rate_limit_reset = time.time() + int(reset)
                    remaining = resp.headers.get("X-RateLimit-Remaining")
                    if remaining:
                        self._rate_limit_remaining = int(remaining)
                    return {"ok": True, "data": result, "status": resp.status}
            except HTTPError as e:
                if e.code == 429:
                    wait = max(1, self._rate_limit_reset - time.time())
                    time.sleep(min(wait, 5))
                    continue
                if e.code >= 500 and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return {"ok": False, "error": f"HTTP {e.code}: {e.reason}", "status": e.code}
            except URLError as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                return {"ok": False, "error": str(e), "status": 0}
            except json.JSONDecodeError:
                return {"ok": False, "error": "Invalid JSON response", "status": 0}

        return {"ok": False, "error": "Max retries exceeded", "status": 0}

    def paginate(self, path: str, params: Dict = None,
                 max_pages: int = 5) -> List[Dict]:
        """Auto-paginate through API results."""
        results = []
        page = 1
        while page <= max_pages:
            p = (params or {}) | {"page": page, "per_page": 100}
            resp = self.get(path, params=p)
            if not resp.get("ok"):
                break
            data = resp["data"]
            if isinstance(data, list):
                results.extend(data)
                if len(data) < 100:
                    break
            else:
                results.append(data)
                break
            page += 1
        return results
