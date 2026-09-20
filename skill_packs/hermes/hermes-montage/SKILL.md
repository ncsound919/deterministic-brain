---
name: hermes-montage
description: Plan agentic video pipelines via OpenMontage bridge.
version: 0.1.0
author: Draymond-Orchestrator fleet
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [video, agentic-video, openmontage, planning, pipeline]
    category: media-production
    related_skills: [plan, requesting-code-review]
    config: {}
---

# Montage Skill

Dry-run agentic video pipeline planning via
[OpenMontage](https://github.com/calesthio/OpenMontage)
(research → proposal → script → scenes). This skill writes `plan.md` /
`plan.json` blueprints and reports render readiness — it never renders
video. Without `ffmpeg` + provider keys the plan returns
`can_render: false`.

## When to Use

- Turning a video idea into a staged pipeline (research/proposal/script/scenes).
- Checking which montage plans exist and whether any can render.
- Handing an approved plan to hermes-proxy media + the SMD agent.
- Verifying `ffmpeg` + key readiness before promising a render.
- Inspecting a single plan's scene breakdown.

Do not use for actual rendering, editing footage, or generating media —
this is the planner; the renderer lives downstream.

## Prerequisites

- A workspace containing (or about to contain) `montage/plans/`.
- For renders (downstream, not here): `ffmpeg` on PATH plus one of
  `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `MONTAGE_API_KEY`.
- Hermes plugin installed (see `README.md`): symlink this directory to
  `~/.hermes/plugins/hermes-montage` or run `install.ps1`.
- Planning itself needs no backend — `montage_plan` always writes the
  blueprint and honestly reports `can_render`.

## How to Run

Via tools (preferred in-session):

- `montage_plan` with `title` + full `brief` (+ `scenes`, `out_dir`).
- `montage_status` with optional `slug` to list or inspect plans.

Via CLI (operator terminal):

```bash
hermes montage status
hermes montage plan "Launch Teaser" --brief "30s teaser for ..." --scenes 4
```

Via slash command: `/montage status`, `/montage status <slug>`,
`/montage plan <title>` (tool-guided, brief required).

## Quick Reference

| Surface | Command | Maps to |
|---------|---------|---------|
| Tool | `montage_plan(title, brief, scenes?)` | `montage/plans/<slug>/{plan.md,plan.json}` |
| Tool | `montage_status(slug?)` | List `montage/plans/` or inspect one plan |
| CLI | `hermes montage plan "<t>" --brief "<b>"` | Same as `montage_plan` from argv |
| Files | `montage/plans/<slug>/{plan.md,plan.json}` | Consumed by hermes-proxy media + SMD agent |

## Procedure

1. **Name the video.** Pick a title; it slugifies to `montage/plans/<slug>/`.
   Check `/montage status` for collisions first.
2. **Write the brief.** Draft what the video is about (audience, beats,
   tone). Never ask the plugin to invent it — pass full text.
3. **Plan.** Call `montage_plan` with `title`, `brief`, `scenes` (1–20).
   Confirm the returned `path` and `can_render` flag.
4. **Fill the scenes.** Edit `plan.md` / `plan.json` prompts + durations —
   shipped scenes are `draft` placeholders, not scripts.
5. **Readiness-check.** Run `montage_status` — it reports `ffmpeg` presence
   and key visibility alongside each plan.
6. **Hand off.** Point hermes-proxy media + the SMD agent at the approved
   `plan.md` / `plan.json` — rendering happens there, not here.
7. **Iterate.** Re-plan under a new slug rather than overwriting a plan
   already handed downstream.

## Pitfalls

- **Plans are dry-runs.** `montage_plan` never renders — `can_render: true`
  only means `ffmpeg` + a key were detected, not that output exists.
- **Empty briefs are rejected.** Planning requires real title + brief text —
  placeholder calls return `success: false` rather than writing stubs.
- **Existing slugs collide.** Planning over an existing slug fails — pick a
  new title or remove the old plan first.
- **Shell utilities are wrapped.** Use `` `read_file` `` / `` `search_files` `` /
  `` `patch` `` / `` `terminal` `` for file work, not raw `cat`/`grep`/`sed`.
- **Scene prompts start empty.** Shipped scenes are structural placeholders;
  fill them before handing off or the renderer has nothing to shoot.
- **Keys are only probed, never printed.** Status reports presence booleans,
  never secret values.

## Verification

- `hermes montage status` lists the plan with `plan_md: true`.
- `montage/plans/<slug>/plan.md` exists with your brief content.
- `plan.json` parses and has the requested scene count.
- Downstream hermes-proxy media + SMD agent accept the plan paths.
- AST check: `python -c "import ast; ast.parse(open('__init__.py').read())"`.
- Manifest check: `python -c "import yaml,sys; yaml.safe_load(open('plugin.yaml'))"`.
