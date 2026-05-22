"""Local Gemma client — wrapper around Ollama OpenAI-compatible API."""

from __future__ import annotations
import logging
import os
import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "hf.co/unsloth/gemma-4-E2B-it-GGUF:UD-IQ2_M"
DEFAULT_TIMEOUT = 120


class LocalGemmaClient:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str, n_predict: int = 128, temperature: float = 0.1) -> str:
        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": n_predict,
                    "temperature": temperature,
                    "stream": False,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except requests.exceptions.ConnectionError:
            logger.warning("Ollama unreachable at %s", self.base_url)
            return ""
        except Exception as e:
            logger.error("Gemma inference failed: %s", e)
            return ""

    def is_available(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False


_client: LocalGemmaClient | None = None

def get_gemma(base_url: str | None = None, model: str | None = None, timeout: int | None = None) -> LocalGemmaClient:
    global _client
    if _client is None:
        import config as _cfg
        url = base_url or _cfg.cfg.gemma_base_url
        m = model or os.getenv("LOCAL_MODEL_NAME", DEFAULT_MODEL)
        _client = LocalGemmaClient(base_url=url, model=m, timeout=timeout or DEFAULT_TIMEOUT)
    return _client


def reset_gemma() -> None:
    global _client
    _client = None