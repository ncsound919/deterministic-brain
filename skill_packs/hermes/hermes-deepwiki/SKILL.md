---
name: hermes-deepwiki
description: Generate repo wikis with DeepWiki-Open in Hermes.
version: 0.1.0
author: Draymond-Orchestrator fleet
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [documentation, wiki, deepwiki, knowledge-base, retrieval]
    category: software-development
    related_skills: [plan, requesting-code-review]
    config: {}
---

# DeepWiki Skill

AI repo wikis via AsyncFuncAI DeepWiki-Open. Queue a wiki build for any
`owner/repo`, URL, or local path; the real docker/Next.js pipeline renders
it and the tree lands under `deterministic-brain knowledge_bank/wiki/<repo>/`
for brain retrieval. This skill never invents wiki content — pages only
exist when the pipeline actually produced them.

## When to Use

- Onboarding to an unfamiliar repo with a full generated wiki.
- Refreshing architecture docs before a multi-step feature.
- Handing a wiki tree to deterministic-brain retrieval.
- Checking which repos already have generated wikis and page counts.
- Recording a wiki request when the pipeline is offline (manifest only).

Do not use for one-line fixes, live code search, or secret-bearing repos
without a self-hosted pipeline — just read the code.

## Prerequisites

- Docker Desktop (or Engine) with `docker compose` available.
- A DeepWiki-Open checkout: `git clone https://github.com/AsyncFuncAI/deepwiki-open`
  (or set `DEEPWIKI_OPEN_DIR`), with `.env` provider keys configured.
- A workspace containing (or about to contain)
  `deterministic-brain knowledge_bank/wiki/`.
- Hermes plugin installed (see `README.md`): symlink this directory to
  `~/.hermes/plugins/hermes-deepwiki` or run `install.ps1`.
- Without checkout/docker/keys, the `deepwiki_*` tools still respond but
  report `available: false` — install the pipeline for real generation.

## How to Run

Via tools (preferred in-session):

- `deepwiki_generate` with `repo` (optional `deepwiki_dir`, `cwd`).
- `deepwiki_status` with optional `repo` to list or inspect wiki trees.

Via CLI (operator terminal):

```bash
hermes deepwiki status
hermes deepwiki generate tap919/my-repo
hermes deepwiki status tap919/my-repo
```

Via slash command: `/deepwiki status`, `/deepwiki generate <repo>`.

## Quick Reference

| Surface | Command | Maps to |
|---------|---------|---------|
| Tool | `deepwiki_generate(repo, deepwiki_dir?, cwd?)` | `knowledge_bank/wiki/<repo>/request.json` + pipeline up |
| Tool | `deepwiki_status(repo?)` | List wiki trees or inspect one repo's real `*.md` pages |
| CLI | `hermes deepwiki generate <repo>` | Same as `deepwiki_generate` from the terminal |
| CLI | `hermes deepwiki status [repo]` | Same as `deepwiki_status` from the terminal |
| Files | `deterministic-brain knowledge_bank/wiki/<repo>/{request.json,*.md}` | Consumed by brain retrieval |

## Procedure

1. **Pick the repo.** Use `owner/repo`, a full https URL, or a local path,
   e.g. `tap919/my-repo`. Check `/deepwiki status` for an existing tree first.
2. **Generate.** Call `deepwiki_generate` (or the CLI). Confirm the returned
   `path` under `knowledge_bank/wiki/<repo>/` and the `request.json` manifest.
3. **Ensure the pipeline.** If `available: false`, follow the returned warning:
   clone DeepWiki-Open, configure `.env` keys, run `docker compose up -d`.
4. **Render the wiki.** Open `http://localhost:3000`, enter the repo URL, and
   export/save the resulting pages into the wiki dir (the plugin never writes
   page content itself).
5. **Status-check.** Run `deepwiki_status` — it counts only `*.md` files that
   actually exist on disk (`generated: true` once pages land).
6. **Hand off.** Point deterministic-brain retrieval at
   `knowledge_bank/wiki/<repo>/` — `request.json` plus every `*.md` page.
7. **Re-run on drift.** After major refactors, call `deepwiki_generate` again
   (manifest is overwritten; real pages are refreshed by the pipeline).

## Pitfalls

- **No pipeline means no pages.** `generate` without checkout/docker/keys
  records only `request.json` and returns `available: false` — install the
  pipeline instead of expecting wiki text.
- **Wiki content is never fabricated.** Empty trees report `pages_total: 0`
  with a warning rather than inventing documentation.
- **Slugs collide across URL forms.** `https://github.com/o/r` and `o/r` map
  to the same `o__r` dir — re-generating overwrites the manifest only.
- **Local paths are namespaced.** Filesystem repos land under `local--<name>/`
  to avoid clobbering GitHub slugs.
- **Shell utilities are wrapped.** Use `` `read_file` `` / `` `search_files` `` /
  `` `patch` `` / `` `terminal` `` for file work, not raw `cat`/`grep`/`sed`.
- **Keep wiki dirs stable.** Renaming a tree mid-flight breaks retrieval
  references — re-generate instead of moving folders.

## Verification

- `hermes deepwiki status` lists the repo with its real `pages_total`.
- `knowledge_bank/wiki/<repo>/request.json` exists with repo + probe details.
- `deepwiki_generate` returns `generated: true` once `*.md` pages exist.
- Brain retrieval can list `knowledge_bank/wiki/<repo>/*.md` on disk.
- AST check: `python -c "import ast; ast.parse(open('__init__.py').read())"`.
- Manifest check: `python -c "import yaml,sys; yaml.safe_load(open('plugin.yaml'))"`.
