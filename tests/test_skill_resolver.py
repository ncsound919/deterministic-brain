"""Tests for tools/skill_resolver.py"""

from unittest.mock import patch, MagicMock
from tools.skill_resolver import SkillResolver, get_resolver


class TestSkillResolver:
    def test_init(self):
        resolver = SkillResolver()
        assert resolver._cache == {}

    def test_resolve_cache(self):
        resolver = SkillResolver()
        resolver._cache["test-skill"] = "/path/to/test.md"
        result = resolver.resolve("test-skill")
        assert result == "/path/to/test.md"

    def test_matches_exact(self):
        resolver = SkillResolver()
        assert resolver._matches("audit_repo", "audit_repo", "audit-repo") is True
        assert resolver._matches("market_data", "market_data", "market-data") is True

    def test_resolve_with_gemma_falls_back(self):
        resolver = SkillResolver()
        with patch("tools.local_gemma.get_gemma") as mock_gemma:
            mock_client = MagicMock()
            mock_client.is_available.return_value = False
            mock_gemma.return_value = mock_client

            result = resolver.resolve_with_gemma("nonexistent-skill")
            assert result is None


class TestGetResolver:
    def test_singleton(self):
        r1 = get_resolver()
        r2 = get_resolver()
        assert r1 is r2