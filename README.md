# Lane-First Deterministic Brain

A neuro-symbolic AI reasoning engine organized around a shared executive brain and five specialized processing lanes. Built on LangGraph orchestration, MCTS candidate ranking, Z3 constraint verification, PyReason graph reasoning, and hybrid Qdrant + Neo4j + Tavily retrieval.

---

## Architecture

```
Query
  └─► input_parser   (intent detection)
        └─► lane_selector  (keyword routing + Karpathy-style plan)
              └─► retriever  (Qdrant + Neo4j + Tavily)
                    └─► pyreason  (neuro-symbolic graph reasoning)
                          └─► lane_runner  (one of 5 lanes)
                                └─► mcts_ranker  (seeded MCTS candidate ranking)
                                      └─► verifier  (Z3 + heuristic)
                                            ├─► composer  → final_output
                                            ├─► lane_runner  (retry, up to max_retries)
                                            └─► fallback_llm  (low-confidence path)
```

### The 5 Lanes

| Lane | Trigger Keywords | Output Mode |
|---|---|---|
| `coding` | python, code, refactor, debug, implement | `code` |
| `business_logic` | policy, approval, compliance, workflow, budget request | `plan` |
| `agent_brain` | browser agent, navigate to, click, dashboard | `action` |
| `tool_calling` | qdrant, neo4j, invoke, validate data, run tool | `action` |
| `cross_domain` | *(default fallback)* | `answer` |

---

## Quickstart

### 1. Install dependencies

```bash
pip install -r requirements.txt

# Install Playwright browsers (required for agent_brain lane)
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys and model paths
```

### 3. Run a query

```bash
# Auto-route to best lane
python main.py "write a binary search in Python"

# Force a specific lane
python main.py --lane coding "implement quicksort"

# Full trace output
python main.py --verbose "create a budget approval policy"

# Run all 5 demo queries
python main.py --demo
```

### 4. Start the API server

```bash
python main.py --serve
# Server starts at http://0.0.0.0:8000
```

---

## CLI Reference

```
python main.py "query"                  Run a query (auto-lane)
python main.py --lane LANE "query"      Override lane selection
python main.py --verbose                Show full verification + history trace
python main.py --demo                   Run all 5 built-in demo queries
python main.py --serve                  Start FastAPI server
python main.py --sessions               List all stored session IDs
python main.py --trace SESSION_ID       Print full trace for a session
python main.py --config                 Print current config summary
```

---

## API Reference

Once running (`python main.py --serve`), the OpenAPI docs are at `http://localhost:8000/docs`.

### `POST /run`

```json
{
  "query": "write a binary search",
  "lane_override": null
}
```

Response:
```json
{
  "session_id": "a1b2c3d4e5f6",
  "lane": "coding",
  "status": "ok",
  "output_mode": "code",
  "final_output": "...",
  "confidence": 0.95,
  "elapsed_ms": 312.5
}
```

### `GET /trace/{session_id}`

Returns the full reasoning trace (all checkpoints) for a prior session.

### `GET /sessions`

Lists all stored session IDs.

### `GET /health`

Returns service status and non-sensitive config summary.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `QDRANT_URL` | *(empty)* | Qdrant server URL (e.g. `http://localhost:6333`) |
| `QDRANT_API_KEY` | *(empty)* | Qdrant API key |
| `RETRIEVAL_TOP_K` | `5` | Max contexts per retrieval |
| `NEO4J_URI` | *(empty)* | Neo4j bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | *(empty)* | Neo4j password |
| `NEO4J_DEPTH` | `1` | Graph traversal depth |
| `TAVILY_API_KEY` | *(empty)* | Tavily web search key |
| `TAVILY_MAX_RESULTS` | `3` | Max Tavily results |
| `QWEN_MODEL_PATH` | *(empty)* | Path to GGUF model file for llama.cpp |
| `LLM_CTX_SIZE` | `4096` | LLM context window size |
| `LLM_MAX_TOKENS` | `512` | Max tokens per generation |
| `LLM_SEED` | `42` | Deterministic seed for LLM |
| `EXECUTOR_TIMEOUT` | `5` | Code execution timeout (seconds) |
| `MCTS_SIMULATIONS` | `20` | MCTS simulation count |
| `MCTS_BRANCH_FACTOR` | `3` | MCTS branching factor |
| `MCTS_MAX_DEPTH` | `4` | MCTS max tree depth |
| `TRACING_ENABLED` | `true` | Enable session checkpointing |
| `CHECKPOINT_DIR` | `.checkpoints` | Directory for trace storage |
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI bind port |

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Docker

```bash
# Build and run
docker compose up --build

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

Or manually:

```bash
docker build -t deterministic-brain .
docker run -p 8000:8000 --env-file .env deterministic-brain
```

---

## Project Structure

```
deterministic-brain/
├── main.py                    # CLI entry point
├── config.py                  # Centralised config (env-driven)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── api/
│   └── server.py              # FastAPI app
├── brain/
│   ├── executive.py           # ExecutiveBrain class
│   ├── memory.py              # init_state()
│   ├── router.py              # route_lane()
│   └── permissions.py        # default_permissions()
├── orchestration/
│   └── langgraph_app.py       # 9-node LangGraph pipeline
├── lanes/
│   ├── coding/                # lane.py, analysis.py, repair.py
│   ├── business_logic/        # lane.py, rule_engine.py, conflict_detector.py
│   ├── agent_brain/           # lane.py, goal_stack.py, observer.py
│   ├── tool_calling/          # lane.py, executor.py, validator.py
│   └── cross_domain/          # lane.py, evidence_fusion.py, trend_scorer.py
├── reasoning/
│   ├── mcts_search.py         # Seeded MCTS candidate ranker
│   ├── z3_constraints.py      # Z3 SMT verification
│   └── pyreason_adapter.py    # Neuro-symbolic graph reasoning
├── retrieval/
│   └── hybrid.py              # Qdrant + Neo4j + Tavily retrieval
├── planners/
│   ├── karpathy_planner.py
│   ├── browser_planner.py
│   └── code_planner.py
├── tools/
│   ├── code_executor.py
│   ├── registry.py
│   ├── tracing.py
│   ├── browser/               # controller.py, session.py, policies.py
│   └── llm/                   # qwen_coder.py
├── schemas/
│   ├── state.py
│   ├── api.py
│   ├── plans.py
│   └── tools.py
└── tests/
    └── test_brain.py
```
