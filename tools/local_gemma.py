"""Local Gemma client — thin wrapper around llama-server HTTP API.

Gemma 3n E4B runs as a local llama-server process on localhost:8080.
This client provides a simple complete() method for synchronous inference.
"""

from __future__ import annotations
import logging
import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8080"
DEFAULT_TIMEOUT = 15


class LocalGemmaClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, prompt: str, n_predict: int = 128, temperature: float = 0.1) -> str:
        """Send a prompt to llama-server and return the completion text."""
        try:
            resp = requests.post(
                f"{self.base_url}/completion",
                json={
                    "prompt": prompt,
                    "n_predict": n_predict,
                    "temperature": temperature,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", "").strip()
            return content
        except requests.exceptions.ConnectionError:
            logger.warning("Gemma server unreachable at %s — is llama-server running?", self.base_url)
            return ""
        except Exception as e:
            logger.error("Gemma inference failed: %s", e)
            return ""

    def is_available(self) -> bool:
        """Check if the llama-server is running and responsive."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def server_info(self) -> dict:
        """Get server metadata."""
        try:
            resp = requests.get(f"{self.base_url}/info", timeout=5)
            if resp.status_code == 200:
                return resp.json()
            return {}
        except Exception:
            return {}


# Singleton
_client: LocalGemmaClient | None = None

def get_gemma(base_url: str | None = None) -> LocalGemmaClient:
    global _client
    if _client is None:
        import config as _cfg
        url = base_url or _cfg.cfg.gemma_base_url
        _client = LocalGemmaClient(base_url=url)
    return _client