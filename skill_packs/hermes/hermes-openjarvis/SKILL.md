---
name: hermes-openjarvis
description: Bridge local-first OpenJarvis skills into Hermes.
version: 0.1.0
author: Draymond-Orchestrator fleet
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [openjarvis, local-first, skills, eval, ollama]
    category: productivity
    related_skills: [curator]
    config:
      - skills.config.jarvis.model
      - skills.config.jarvis.cli_path
---

# OpenJarvis Skill

Use OpenJarvis-compatible skills and presets inside Hermes without vendoring OpenJarvis. This skill covers the interface surface only: skill catalog sync, honest local-first eval gating, and preset runner stubs. It never clones the upstream repo and never invents metrics.

## When to Use

- List or sync the OpenJarvis-compatible skill catalog for a task.
- Run a `morning-digest`, `deep-research`, or `code-assistant` preset.
- Probe local eval readiness (Ollama up, model set) before benchmarking.
- NOT for cloud model evals, costed API benchmarks, or full OpenJarvis installs.

## Prerequisites

- Hermes with standalone plugins enabled (`~/.hermes/plugins/` on PATH).
- This plugin installed (see `README.md` symlink step).
- Optional: `jarvis` CLI on PATH for preset runs (`skills.config.jarvis.cli_path` override).
- Optional: Ollama on `127.0.0.1:11434` plus a pulled model for live bench runs.
- Config keys live under `skills.config.jarvis` in `config.yaml`:
  ```yaml
  skills:
    config:
      jarvis:
        model: "llama3.1:8b"
        cli_path: ""  # optional absolute path to `jarvis`
  ```

## How to Run

All capability flows through three `jarvis` tools. Call them with the `terminal`-free tool calling path; every handler returns a JSON string.

```text
jarvis_skills(action="list")              # static catalog, no I/O
jarvis_skills(action="sync")              # merge local SKILL.md files
jarvis_bench(model="llama3.1:8b")         # eval probe, honest gating
jarvis_preset(preset="morning-digest")    # shell to `jarvis` CLI
jarvis_preset(preset="deep-research")
jarvis_preset(preset="code-assistant")
```

No new environment variables. Secrets stay in `~/.hermes/.env`; behavior stays in `config.yaml`.

## Quick Reference

| Task | Tool | Notes |
|---|---|---|
| List skill catalog | `jarvis_skills` | `action="list"`, offline-safe |
| Sync local skills | `jarvis_skills` | `action="sync"`, scans `~/.hermes/skills/` |
| Eval readiness probe | `jarvis_bench` | Energy/FLOPs `None` until instrumented |
| Morning digest | `jarvis_preset` | `preset="morning-digest"` |
| Deep research | `jarvis_preset` | `preset="deep-research"` |
| Code assistant | `jarvis_preset` | `preset="code-assistant"` |
| Check CLI presence | `read_file` | Inspect install path, not a tool |
| Measure latency live | `terminal` | Only via `ollama run`, never faked |
| View plugin manifest | `read_file` | `plugin.yaml` declares kind and tools |

## Procedure

1. **List first.** Call `jarvis_skills` with `action="list"` to see the three built-in entries and their presets.
2. **Sync when local skills exist.** Call `jarvis_skills` with `action="sync"`; it merges `SKILL.md` files from `~/.hermes/skills/` using the agentskills.io shape (`name` from directory, `description` from frontmatter).
3. **Probe before benchmarking.** Call `jarvis_bench` with a model id. Expect `available:false` when Ollama is down — that is the correct answer, not an error.
4. **Run presets through the CLI.** Call `jarvis_preset` with one of the three presets. Without the `jarvis` CLI it returns `available:false` with a reason; install the CLI and retry.
5. **Report honestly.** Surface `available`, `reason`, and `metrics` verbatim. Never fill `energy_j` or `flops` with estimates.
6. **Stay local-first.** Prefer `ollama run` and local files via `read_file`; do not exfiltrate prompts to hosted eval endpoints.

## Pitfalls

- Do NOT invent energy, FLOPs, or cost numbers when Ollama is unreachable. Return `available:false`.
- Do NOT clone `https://github.com/open-jarvis/OpenJarvis` into the plugin. Interface surface only, per upstream policy.
- Do NOT add `HERMES_*` env vars for `model` or `cli_path`. Use `skills.config.jarvis` in `config.yaml`.
- Do NOT shell to `jarvis` with unsanitized user text; pass short flags, keep `args` minimal.
- Do NOT treat `sync` as an install step. It lists local skills; it never downloads remote ones.
- Do NOT cache `check_fn` verdicts yourself; the registry TTL-caches them.
- `jarvis_bench` measures wall-clock latency only. Energy and FLOPs stay `None` until real instrumentation lands.

## Verification

- `plugin.yaml` parses as YAML and declares `kind: standalone` with all three tools in `provides_tools`.
- `python -c "import ast; ast.parse(open('__init__.py').read())"` exits 0.
- `jarvis_skills(action="list")` returns `success:true` with `count: 3`.
- `jarvis_bench({})` with Ollama stopped returns `available:false` and null metrics.
- `jarvis_preset(preset="morning-digest")` without the CLI returns `available:false` naming the missing binary.
- `install.ps1` is idempotent: re-running replaces the symlink without error.
- No file under `agents/hermes-agent-main/` is modified; the plugin lives only in `agents/hermes-integrations/hermes-openjarvis/`.
