# Ability Checklist → Implementation Map

This file maps the requested abilities to concrete files and notes whether
they are implemented, distributed, or missing.

- Memory — FOUND: `brain/memory.py`, `vector_memory.py`, `brain/soul.py`
- Session Orchestrator / Executive — FOUND: `brain/executive.py`
- Deterministic Orchestrator / Skill Executor — FOUND: `orchestration/dca_engine.py`
- Policy / Governance / Pre-audit — FOUND: `reasoning/policy_engine.py`
- Decisioning (Bandits / MCTS / Rankers) — FOUND/DISTRIBUTED: `reasoning/contextual_bandit.py`, `planners/monte_carlo.py`, `reasoning/mcts_search.py`, `reasoning/math_engine.py`
- Planning / Planner — FOUND: `planners/karpathy_planner.py`, `planners/monte_carlo.py`
- Reward / Learning / Evolver — FOUND: `evolution/reward_tracker.py`, `evolution/skill_evolver.py`
- Audit / Tracing / Logs — FOUND: `.env` toggles, audit outputs, `api/notifications.py`
- Intent DSL / Shorthand Parser — FOUND: `brain/shorthand_parser.py`
- Correction / Self-healing Hooks — FOUND: `brain/correction_detector.py`, `self_healing/`
- API & UI — FOUND: `api/server.py`, `aether-dashboard/`
- Vector / Semantic Memory Backing — FOUND (external): `vector_memory.py` (Qdrant + sentence-transformers)
- Knowledge Graph (Neo4j) — PARTIAL: hooks and references present; runtime requires credentials

- Priority Engine — MISSING (added `reasoning/priority_engine.py` as a conservative wrapper)
- Resource Allocator — MISSING (added `orchestration/resource_allocator.py` semaphore-based allocator)
- Env / Service Monitor — MISSING (added `infra/env_monitor.py` simple probes)

Notes:
- The newly added modules are conservative adapters/stubs that wrap existing
  systems without changing runtime behavior. They are safe to import and use
  immediately for integration tests. Full productionization may require
  wiring these into the DCA and executive flows.
