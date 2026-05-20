import os
import pytest

from infra.env_monitor import EnvMonitor


@pytest.mark.skipif(os.environ.get("RUN_INTEGRATION") != "1", reason="Integration tests disabled")
def test_qdrant_and_neo4j_up():
    em = EnvMonitor(timeout=1.0)
    cfg_q = os.environ.get("QDRANT_ADDR", "localhost:6333")
    host, port = cfg_q.split(":") if ":" in cfg_q else (cfg_q, "6333")
    qdrant = em.check_qdrant(host, int(port))
    assert qdrant.get("ok") is True, f"Qdrant not available: {qdrant}"

    neo_uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo = em.check_neo4j(neo_uri)
    assert neo.get("ok") is True, f"Neo4j not available: {neo}"
