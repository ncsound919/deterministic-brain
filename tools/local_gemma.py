"""Local Gemma client — wrapper around llama-server (llama.cpp) HTTP API."""

from __future__ import annotations
import logging
import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:8088"
DEFAULT_TIMEOUT = 120


class LocalGemmaClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def complete(self, prompt: str, n_predict: int = 128, temperature: float = 0.1) -> str:
        try:
            resp = requests.post(
                f"{self.base_url}/v1/completions",
                json={"prompt": prompt, "n_predict": n_predict, "temperature": temperature},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("choices", [{}])[0].get("text", "").strip()
        except requests.exceptions.ConnectionError:
            logger.warning("llama-server unreachable at %s", self.base_url)
            return ""
        except Exception as e:
            logger.error("Gemma inference failed: %s", e)
            return ""

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False


_client: LocalGemmaClient | None = None

def get_gemma(base_url: str | None = None, timeout: int | None = None) -> LocalGemmaClient:
    global _client
    if _client is None:
        import config as _cfg
        url = base_url or _cfg.cfg.gemma_base_url
        _client = LocalGemmaClient(base_url=url, timeout=timeout or DEFAULT_TIMEOUT)
    return _client


def reset_gemma() -> None:
    global _client
    _client = None