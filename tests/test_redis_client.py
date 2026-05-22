"""Tests for tools/redis_client.py (in-memory fallback mode)."""
import time
from tools.redis_client import RedisClient, get_redis, reset_redis


class TestRedisClient:
    def setup_method(self):
        reset_redis()

    def test_available_false_by_default(self):
        r = RedisClient()
        assert r.available is False

    def test_connect_returns_false_when_not_distributed(self):
        r = RedisClient()
        result = r.connect(url="redis://localhost:6379")
        assert result is False

    def test_cache_get_set_in_memory(self):
        r = RedisClient()
        r.cache_set("k1", "v1", ttl=60)
        assert r.cache_get("k1") == "v1"

    def test_cache_get_missing_returns_none(self):
        r = RedisClient()
        assert r.cache_get("missing") is None

    def test_cache_delete_removes_key(self):
        r = RedisClient()
        r.cache_set("k2", "v2", ttl=60)
        r.cache_delete("k2")
        assert r.cache_get("k2") is None

    def test_cache_ttl_expiration(self):
        r = RedisClient()
        r.cache_set("k3", "v3", ttl=0.01)
        time.sleep(0.02)
        assert r.cache_get("k3") is None

    def test_cache_scan_delete_removes_by_prefix(self):
        r = RedisClient()
        r.cache_set("prefix_a_1", "1", ttl=60)
        r.cache_set("prefix_a_2", "2", ttl=60)
        r.cache_set("other_c", "3", ttl=60)
        r.cache_scan_delete("prefix_a_")
        assert r.cache_get("prefix_a_1") is None
        assert r.cache_get("prefix_a_2") is None
        assert r.cache_get("other_c") == "3"

    def test_get_singleton(self):
        r1 = get_redis()
        r2 = get_redis()
        assert r1 is r2

    def test_reset_redis_creates_new(self):
        r1 = get_redis()
        reset_redis()
        r2 = get_redis()
        assert r1 is not r2
