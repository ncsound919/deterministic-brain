# Deterministic-Brain — Autonomous AI Ops

## Acquisition Role
**Core strategic asset.** NVIDIA / Palantir exit path. Central intelligence of the DCA swarm — replaces LLM calls with deterministic skill files, MoE routing, Monte Carlo planning, and MCP tool layers. Autonomous scheduler, self-learning loop, executive kernel, acquisition bridge. In the acquisition trap: this is the glue that makes BB-Tech and AetherDesk operationally viable control planes. Acquirer of any other asset MUST also acquire this to complete the stack.

## Current Status
- **Deploy Readiness:** 97.5%
- **Remaining:** Production cron + systemd for autonomous brain loop
- **Tests:** 229/229 passing (+35 tests added in last session), Playwright UX, API integration
- **Key Features:** Acquisition bridge, Executive Kernel (AGI layer), SkillMarketplace (TypeScript + CSS Modules), autonomous scheduler, self-learning, swarm dispatcher

## Superpowers Integration (Priority Order)

### Must-Use (Every Session)
1. **superpowers:using-superpowers** — Check applicable skills before any action
2. **superpowers:verification-before-completion** — 229 tests must pass. No exceptions. Run full suite before claiming anything
3. **superpowers:systematic-debugging** — Complex multi-agent system with acquisition bridge, self-learning, scheduler, executive kernel. Any bug could cascade across subsystems. Root cause before fixes

### Production Deployment
4. **superpowers:brainstorming** — Production deployment (cron + systemd + monitoring) needs design discussion. This is the most strategically important asset — deployment architecture matters
5. **superpowers:writing-plans** — Production deployment plan covering: cron scheduling, systemd service, health monitoring, log rotation, backup strategy, failure recovery
6. **superpowers:subagent-driven-development** — Execute deployment plan with subagents: one for systemd service file, one for cron config, one for monitoring, one for backup scripts. Review between each

### Feature Work / Enhancement
7. **superpowers:test-driven-development** — Any new feature or bugfix starts with a failing test. The 229-test baseline is the trust foundation
8. **superpowers:dispatching-parallel-agents** — Multiple independent subsystems (acquisition bridge, scheduler, self-learning, swarm, executive kernel) — parallel investigation when multiple things fail
9. **superpowers:requesting-code-review** — Before merging to main. This is the core asset — quality is non-negotiable

### Workflow
10. **superpowers:using-git-worktrees** — Isolate work on production deployment
11. **superpowers:finishing-a-development-branch** — Structured completion for production branches

## Tech Stack
- **Core:** Python 3.11+, FastAPI, async/await, threading
- **AI/LLM:** Skill files (YAML + Jinja), MoE router, Monte Carlo planner, ultraplan.py
- **Agents:** Swarm dispatcher, DCA engine, autonomous scheduler, self-learning loop
- **Storage:** SQLite (sovereign.db), JSON files, Qdrant (vector), Redis
- **Frontend:** React (aether-dashboard), TypeScript, CSS Modules, Recharts
- **Infra:** Docker, Docker Compose, systemd (target), cron, Nginx
- **Tests:** pytest (229 tests), Playwright (UX tests), API integration tests

## Key Commands
```bash
pytest -v                          # Run full test suite
python main.py --serve             # Start API server
python start_acquisition_brain.py  # Start acquisition brain
python main.py "describe the acquisition bridge"  # CLI mode
pytest tests/ --cov=./ --cov-report=term-missing  # Coverage
```

## Architecture
| Layer | Component | Purpose |
|-------|-----------|---------|
| CLI | `main.py` | Entry point, argparse, signal handling |
| Brain | `brain/` | Core intelligence: router, memory, soul, executive |
| Orchestration | `orchestration/` | Swarm dispatch, skill execution, DCA engine |
| Agents | `agi/` | Executive Kernel, acquisition bridge, self-learning |
| API | `api/` | FastAPI endpoints for dashboard integration |
| Scheduler | `.autonomous_scheduler/` | Cron-based autonomous task execution |
| Learning | `.self_learning/` | Pattern detection, skill evolution |
| UI | `aether-dashboard/` | React dashboard with SkillMarketplace |
| Acquisition | `acquisition_bridge.py` | Portfolio tracking, DAILY-LOG/PROGRESS/METRICS sync |
