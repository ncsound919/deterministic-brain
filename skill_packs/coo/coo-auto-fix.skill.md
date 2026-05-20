---
skill_id: coo-auto-fix
name: COO Auto-Fix Green Zone
version: 1.0
description: >
  Automatically executes green-zone fixes: cache clears, dependency updates, lint fixes, and server restarts.
tools:
  - code_executor
  - linter
  - file_io
inputs:
  action: str
  max_fixes_per_run: int
---

# COO Auto-Fix Green Zone

## Purpose
Execute low-risk, high-confidence fixes without human approval.

## Green Zone Actions

1. **Cache Clear**: Delete `.pytest_cache`, `.mypy_cache`, `node_modules/.cache`
2. **Dependency Update**: Run `npm update` or `pip install --upgrade` for non-breaking versions
3. **Lint Fix**: Run `ruff check --fix` or `biome check --apply`
4. **Server Restart**: Restart staging services that have been idle >30 min
5. **Typo Fix**: Fix obvious typos in comments and docstrings

## Safety Rules

- Never touch `auth/`, `billing/`, `legal/`, `security/` directories
- Never run destructive commands (`rm -rf`, `DROP TABLE`, etc.)
- Max 5 fixes per run to avoid cascading failures
- Log all actions to `.coo_fix_log.jsonl`

## Output
```json
{
  "fixes_executed": 3,
  "fixes": [
    {"type": "cache_clear", "path": ".pytest_cache", "status": "success"},
    {"type": "lint_fix", "path": "coo/state.py", "status": "success"},
    {"type": "dependency_update", "package": "requests", "status": "success"}
  ],
  "timestamp": "2026-05-20T05:05:00Z"
}
```
