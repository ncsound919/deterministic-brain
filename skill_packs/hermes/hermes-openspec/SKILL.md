---
name: hermes-openspec
description: Propose and track OpenSpec change specs in Hermes.
version: 0.1.0
author: Draymond-Orchestrator fleet
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [spec-driven, openspec, planning, workflow, documentation]
    category: software-development
    related_skills: [plan, test-driven-development, requesting-code-review]
    config: {}
---

# OpenSpec Skill

Spec-driven development via Fission-AI OpenSpec. Draft change proposals as
markdown under `openspec/changes/<name>/`, then implement and archive them.
This skill never invents spec content — the model supplies real proposals.

## When to Use

- Starting a multi-step feature that deserves a written spec first.
- Converting a plan into `proposal.md` / `design.md` / `tasks.md` artifacts.
- Checking which spec changes are open, ready, or archived.
- Handing a spec to Recourse verify or the deterministic-brain planner.
- Archiving a finished change after implementation lands.

Do not use for one-line fixes, hotfixes, or exploratory spikes — just do them.

## Prerequisites

- Node.js 18+ with the OpenSpec CLI: `npm i -g @fission-ai/openspec`.
- A workspace containing (or about to contain) `openspec/changes/`.
- Hermes plugin installed (see `README.md`): symlink this directory to
  `~/.hermes/plugins/hermes-openspec` or run `install.ps1`.
- Without the CLI, the `openspec_*` tools still work file-first but report
  `available: false` — install the CLI for `validate` / `archive` parity.

## How to Run

Via tools (preferred in-session):

- `openspec_propose` with `name` + full `proposal` markdown.
- `openspec_apply` with `name` to check readiness (read-only).
- `openspec_status` with optional `name` to list or inspect changes.

Via CLI (operator terminal):

```bash
hermes openspec status
hermes openspec propose add-rate-limits --proposal-file ./proposal.md --tasks-file ./tasks.md
hermes openspec apply add-rate-limits
hermes openspec archive add-rate-limits
```

Via slash command: `/openspec status`, `/openspec apply <name>`,
`/openspec archive <name>`, `/openspec propose <name>` (tool-guided).

## Quick Reference

| Surface | Command | Maps to |
|---------|---------|---------|
| Tool | `openspec_propose(name, proposal, design?, tasks?)` | `openspec/changes/<name>/proposal.md` + optional files |
| Tool | `openspec_apply(name)` | Readiness check + `openspec validate` when CLI present |
| Tool | `openspec_status(name?)` | List `openspec/changes/` or inspect one change |
| CLI | `hermes openspec propose <n> --proposal-file <p>` | Same as `openspec_propose` from files |
| CLI | `hermes openspec archive <n>` | `openspec archive` or dated file move |
| Files | `openspec/changes/<n>/{proposal.md,design.md,tasks.md,specs/}` | Consumed by Recourse + planner |

## Procedure

1. **Name the change.** Pick a slug: lowercase, digits, `-`/`_` (max 80 chars),
   e.g. `add-rate-limits`. Check `/openspec status` for collisions first.
2. **Write the proposal.** Draft real `proposal.md` content (problem, approach,
   scope, risks). Never ask the plugin to invent it — pass full markdown.
3. **Add design/tasks when ready.** `design.md` for decisions, `tasks.md` with
   `- [ ]` checkboxes (one task per 2–5 minutes of work).
4. **Propose.** Call `openspec_propose` (or the CLI with `--proposal-file`).
   Confirm the returned `path` under `openspec/changes/<name>/`.
5. **Implement against the spec.** Work through `tasks.md` checkboxes in order.
6. **Apply-check.** Run `openspec_apply` — it is read-only and reports which
   files exist plus task counts (and CLI `validate` output when available).
7. **Hand off.** Point Recourse verify and the deterministic-brain planner at
   `openspec/changes/<name>/` — `proposal.md`, `specs/`, `design.md`, `tasks.md`.
8. **Archive.** After landing, run `archive` (CLI-backed, else dated file move
   to `openspec/archive/`).

## Pitfalls

- **Empty proposals are rejected.** `propose` requires non-empty markdown —
  placeholder calls return `success: false` rather than writing stubs.
- **No CLI means reduced parity.** `validate`/`archive` fall back to file
  operations with an `available: false` warning — install the CLI for parity.
- **Existing names collide.** Proposing over an existing change fails — pick a
  new slug or archive the old one first.
- **Shell utilities are wrapped.** Use `` `read_file` `` / `` `search_files` `` /
  `` `patch` `` / `` `terminal` `` for file work, not raw `cat`/`grep`/`sed`.
- **`apply` never edits code.** It only reports readiness — implement the tasks
  yourself, then archive.
- **Keep slugs stable.** Renaming a change mid-flight breaks Recourse/planner
  references — archive + re-propose instead.

## Verification

- `hermes openspec status` lists the change with `proposal: true`.
- `openspec/changes/<name>/proposal.md` exists on disk with your content.
- `openspec_apply` returns `ready: true` once `proposal.md` + `tasks.md` exist.
- After implementation, `archive` moves the change to `openspec/archive/` (or
  via the CLI) and `status` shows it under `archived`.
- AST check: `python -c "import ast; ast.parse(open('__init__.py').read())"`.
- Manifest check: `python -c "import yaml,sys; yaml.safe_load(open('plugin.yaml'))"`.
