"""Tests for tools/postgres.py."""
import pytest
from tools.postgres import PostgresPool, get_pg_pool, reset_pg_pool


class TestPostgresPool:
    def teardown_method(self):
        reset_pg_pool()

    def test_available_false_by_default(self):
        pool = PostgresPool()
        assert pool.available is False

    def test_connect_returns_false_when_not_distributed(self):
        pool = PostgresPool()
        result = pool.connect(dsn="postgres://localhost/test")
        assert result is False
        assert pool.available is False

    def test_execute_raises_when_not_available(self):
        pool = PostgresPool()
        with pytest.raises(RuntimeError, match="not available"):
            pool.execute("SELECT 1")

    def test_execute_many_raises_when_not_available(self):
        pool = PostgresPool()
        with pytest.raises(RuntimeError, match="not available"):
            pool.execute_many("INSERT INTO t VALUES %s", [(1,)])

    def test_get_pg_pool_singleton(self):
        p1 = get_pg_pool()
        p2 = get_pg_pool()
        assert p1 is p2

    def test_reset_pg_pool_clears_singleton(self):
        p1 = get_pg_pool()
        reset_pg_pool()
        p2 = get_pg_pool()
        assert p1 is not p2

    def test_available_stays_false_after_failed_connect(self):
        pool = PostgresPool()
        pool.connect(dsn="postgres://invalid:invalid@localhost:9999/test")
        assert pool.available is False
