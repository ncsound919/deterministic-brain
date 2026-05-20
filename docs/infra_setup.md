# Infrastructure Setup for Integration Tests

This document explains how to start the minimal external services required
for end-to-end integration testing: Qdrant (vector DB) and Neo4j (knowledge graph).

Run with Docker Compose (requires Docker):

```bash
docker compose -f docker-compose.infra.yml up -d
```

Environment variables used by tests and runtime:

- `QDRANT_ADDR` — default `localhost:6333` (host:port)
- `NEO4J_URI` — default `bolt://localhost:7687`
- `RUN_INTEGRATION` — set to `1` to enable integration tests

Example: start services and run integration tests:

```bash
docker compose -f docker-compose.infra.yml up -d
export RUN_INTEGRATION=1
export QDRANT_ADDR=localhost:6333
export NEO4J_URI=bolt://localhost:7687
python -m pytest tests/test_integration_services.py -q
```

Notes:

- The `docker-compose.infra.yml` uses minimal default credentials for Neo4j
  (`neo4j/test`) — change in production.
- The integration test is conservative: it simply checks service reachability
  and will be skipped by default unless `RUN_INTEGRATION=1`.
