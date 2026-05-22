# deterministic-brain

> **Deterministic core — hybrid LLM augmentation. 100% reproducible when LLM-free.**
> > **⚠️ HYBRID MODE:** The core DCA engine is LLM-free and fully deterministic. `ultraplan.py` selectively uses LLM routing for complex multi-step planning tasks. Set `ENABLE_ULTRAPLAN=false` to run in pure deterministic mode.


The deterministic-brain is the central intelligence of the DCA (Deterministic Coding Agent) swarm. It replaces every LLM call with:

- **Skill files** (`skill.md`) — YAML-declared, Jinja-templated, version-controlled actions
- **MoE Router** — deterministic decision tree, config-driven
- **Monte Carlo Planner** — exhaustive config-space search with deterministic scoring
- **MCP Tool Layer** — file I/O, linting, semantic search, code execution via JSON-RPC
- **Deterministic Auditor** — linters, static analysis, complexity scoring
- **Swarm Dispatcher** — parallel lane execution across agent bundles

---

## Structure

```
deterministic-brain/
├── main.py                        # CLI + FastAPI entrypoint
├── config/                        # Env + path config (BrainConfig, persist)
│   └── __init__.py
├── config.py                      # Legacy config alias
├── swarm.yaml                     # Bundle → lane routing config
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── brain/                         # Core intelligence
│   ├── task_parser.py             # Regex/keyword task → structured dict
│   ├── router.py                  # MoE router: task → expert/skill path
│   ├── memory.py                  # Session state (no LLM memory)
│   ├── soul.py                    # User identity/mission config (.soul.yaml)
│   ├── autodream.py               # Autonomous directive execution engine
│   ├── state_manager.py           # Session state persistence
│   ├── correction_detector.py     # Correction/refinement detector
│   ├── executive.py               # Task execution orchestration
│   ├── health_check.py            # 24/7 system health monitoring
│   └── __init__.py
│
├── orchestration/                 # Agent orchestration & dispatch
│   ├── dca_engine.py              # DeterministicCodingAgent (core loop)
│   ├── swarm_dispatcher.py        # Parallel bundle/lane launcher
│   ├── swarm_worker.py            # Long-running swarm worker
│   ├── resource_allocator.py      # Concurrent execution throttle
│   ├── skill_registry.py          # Skill file discovery
│   ├── skill_executor.py          # Skill execution harness
│   ├── intent_router.py           # Keyword-based intent routing
│   ├── langgraph_app.py           # LangGraph workflow integration
│   └── event_bus.py               # Cross-component event bus
│
├── reasoning/                     # Deterministic reasoning engines
│   ├── math_engine.py             # Algebraic/differential/quantum reasoners
│   ├── mcts_search.py             # MCTS planner
│   ├── auditor.py                 # DeterministicAuditor
│   ├── priority_engine.py         # Task priority scoring
│   ├── policy_engine.py           # Execution policy engine
│   └── z3_constraints.py          # Z3 constraint-based validation
│
├── planners/
│   ├── monte_carlo.py             # MonteCarloScaffolder
│   └── scorer.py                  # DeterministicScorer
│
├── retrieval/                     # Retrieval & knowledge
│   ├── tfidf_search.py            # TF-IDF semantic search
│   └── knowledge_graph.py         # Neo4j knowledge graph client
│
├── tools/                         # MCP tools & infrastructure
│   ├── registry.py                # Tool registry
│   ├── file_io.py                 # file_write, file_read
│   ├── linter.py                  # run_linter
│   ├── code_executor.py           # Sandboxed code execution
│   ├── code_formatter.py          # Code formatting
│   ├── code_generator.py          # Code generation
│   ├── tracing.py                 # Audit log / session trace (SQLite)
│   ├── dashboard.py               # Dashboard event feed
│   ├── relay.py                   # Inter-agent relay
│   ├── forge.py                   # Diff/apply forge
│   └── web_fetcher.py             # Web content fetcher
│
├── api/                           # FastAPI server
│   ├── server.py                  # Main API (2250+ lines)
│   ├── engine_api.py              # Engine API endpoints
│   ├── notifications.py           # Real-time notification system
│   ├── middleware.py              # Request logging middleware
│   └── routes/                    # Additional route modules
│
├── features/                      # Integrated feature modules
│   ├── github_manager.py          # GitHub integration
│   ├── scheduler.py               # Cron-style task scheduler
│   ├── systems_bridge.py          # External system bridge
│   └── repo_inventory.py          # Repository inventory mgmt
│
├── coo/                           # COO (Chief Operating Officer) brain
│   └── executor.py                # Ruff linting executor
│
├── skills/                        # Standalone skill definitions
│   ├── cli_anything.py
│   ├── content_creation.py
│   └── knowledge_synthesis.py
│
├── skill_packs/                   # Bundled skill packs (git submodules)
│   └── react/
│       ├── create-react-component.skill.md
│       └── templates/
│           └── react-component.tsx.j2
│
├── plugins/                       # Plugin system
│
├── streaming/                     # Streaming / WebSocket support
│
├── scripts/                       # Utility scripts
│   ├── import_skills.py
│   └── start_satellite_servers.py
│
├── tests/                         # Test suite
│   ├── test_config.py
│   ├── test_brain.py
│   └── e2e/
│       ├── test_determinism_smoke.py
│       └── test_metrics_e2e.py
│
├── docs/                          # Documentation
│
├── knowledge/                     # Local knowledge bank
│
├── schemas/
│   └── skill.schema.yaml          # JSON Schema for skill.md validation
│
└── repos/                         # External repo mirrors (git submodules)
```

---

## Quick Start

```bash
pip install -r requirements.txt

# Run a task
python main.py "create a react component named UserCard with props name, email"

# Start MCP-compatible API server
python main.py --serve

# Run a named bundle
python main.py --bundle scaffold-rest-api --inputs '{"resource": "User"}'

# Audit a local repo path
python main.py --bundle audit-repo --inputs '{"repo_path": "./my-project"}'
```

---

## Swarm Agents (external repos)

| Repo | Role |
|---|---|
| `tap919-middleman` | Middleware — signs + routes agent handoffs via REST |
| `browser-harness` | Web Agent — scrapes docs, feeds retrieval layer |
| `repoforge` | Forge UI — Tauri desktop, diffs, skill pack manager |
| `Social-Media-Dashboard` | Output Agent — live swarm feed, audit scores |

---

## Deterministic by Default, LLM-Augmented When Needed

The core DCA engine (`orchestration/dca_engine.py`) runs **100% LLM-free** — every decision is made by:
1. Regex + keyword task parsing
2. Config-driven routing (MoE)
3. YAML + Jinja skill execution
4. MCTS exhaustive config-space search
5. Deterministic scoring (algebraic, differential, quantum-probabilistic reasoners)
6. Subprocess-based linting and static analysis

For **complex multi-step planning** (`ultraplan.py`), LLM routing is optional via `ENABLE_ULTRAPLAN`. Set `ENABLE_ULTRAPLAN=false` for pure deterministic mode.
