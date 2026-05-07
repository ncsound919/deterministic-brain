# deterministic-brain

> **Zero-LLM. Zero tokens. 100% reproducible.**

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
├── config.py                      # Env + path config
├── swarm.yaml                     # Bundle → lane routing config
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── brain/
│   ├── task_parser.py             # Regex/keyword task → structured dict
│   ├── router.py                  # MoE router: task → expert/skill path
│   └── memory.py                  # Session state (no LLM memory)
│
├── orchestration/
│   ├── dca_engine.py              # DeterministicCodingAgent (core loop)
│   └── swarm_dispatcher.py        # Parallel bundle/lane launcher
│
├── planners/
│   ├── monte_carlo.py             # MonteCarloScaffolder
│   └── scorer.py                  # DeterministicScorer (complexity, coverage, lines)
│
├── reasoning/
│   └── auditor.py                 # DeterministicAuditor (linters, static analysis)
│
├── retrieval/
│   └── tfidf_search.py            # TF-IDF semantic search (offline index)
│
├── tools/
│   ├── registry.py                # MCP tool registry
│   ├── file_io.py                 # file_write, file_read
│   ├── linter.py                  # run_linter (eslint, tsc, pylint, bandit)
│   └── tracing.py                 # Audit log / session trace
│
├── lanes/
│   ├── scaffold_rest_api.py
│   ├── live_docs_to_skill.py
│   └── audit_repo.py
│
├── skill_packs/
│   └── react/
│       ├── create-react-component.skill.md
│       └── templates/
│           └── react-component.tsx.j2
│
├── schemas/
│   └── skill.schema.yaml          # JSON Schema for skill.md validation
│
└── api/
    └── server.py                  # FastAPI MCP-compatible server
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

## No LLM. Ever.

There are no calls to OpenAI, Anthropic, Ollama, or any language model in this codebase. Every decision is made by:
1. Regex + keyword task parsing
2. Config-driven routing
3. YAML + Jinja skill execution
4. Subprocess-based linting and static analysis
5. Deterministic scoring (radon, pytest-cov, line counts)
