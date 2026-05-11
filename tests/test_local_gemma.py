"""Tests for tools/local_gemma.py"""

import pytest
from tools.local_gemma import LocalGemmaClient, get_gemma, DEFAULT_BASE_URL, DEFAULT_TIMEOUT


class TestLocalGemmaClient:
    def test_init_defaults(self):
        client = LocalGemmaClient()
        assert client.base_url == DEFAULT_BASE_URL
        assert client.timeout == DEFAULT_TIMEOUT

    def test_init_custom_url(self):
        client = LocalGemmaClient(base_url="http://localhost:9000", timeout=30)
        assert client.base_url == "http://localhost:9000"
        assert client.timeout == 30

    def test_is_available_returns_false_when_server_down(self):
        client = LocalGemmaClient(base_url="http://localhost:99999")
        assert client.is_available() is False

    def test_complete_returns_empty_when_server_down(self):
        client = LocalGemmaClient(base_url="http://localhost:99999")
        result = client.complete("hello", n_predict=10)
        assert result == ""


@pytest.mark.skip(reason="llama-server not running on port 8088 in CI")
class TestLiveGemma:
    def test_live_inference(self):
        client = LocalGemmaClient(base_url="http://localhost:8088")
        assert client.is_available(), "llama-server must be running at localhost:8088"
        result = client.complete("Hello", n_predict=32, temperature=0.1)
        assert result != "", "Gemma inference should return non-empty text"


class TestGetGemma:
    def test_get_gemma_returns_client(self):
        client = get_gemma()
        assert isinstance(client, LocalGemmaClient)

    def test_get_gemma_is_singleton(self):
        c1 = get_gemma()
        c2 = get_gemma()
        assert c1 is c2