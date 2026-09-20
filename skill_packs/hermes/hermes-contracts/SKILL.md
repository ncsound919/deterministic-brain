---
name: hermes-contracts
description: Scaffold and audit OpenZeppelin contracts in Hermes.
version: 0.1.0
author: Draymond-Orchestrator fleet
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [solidity, openzeppelin, erc20, erc721, erc1155, audit]
    category: software-development
    related_skills: [requesting-code-review, test-driven-development]
    config: {}
---

# Contracts Skill

Wizard-style ERC20 / ERC721 / ERC1155 generation on top of
[OpenZeppelin Contracts](https://github.com/OpenZeppelin/openzeppelin-contracts),
plus read-only audits via `slither` / `solhint`. This skill never invents an
installed toolchain — without `forge` or `@openzeppelin/contracts` the
scaffold tool returns `available: false`.

## When to Use

- Scaffolding a new ERC20, ERC721, or ERC1155 token contract.
- Checking whether the workspace has a usable OpenZeppelin backend.
- Auditing a generated (or existing) `.sol` file with local tools.
- Handing a contract to the Recourse sandboxed verifier (`/api/recourse/verify`).
- Verifying auditor output before sending code to review.

Do not use for proxy/upgradeable patterns, custom cryptography, or
production deployment — scaffold first, then review with a human.

## Prerequisites

- Node.js 18+ with `npm i @openzeppelin/contracts` in the workspace, OR
  Foundry `forge` with `forge install OpenZeppelin/openzeppelin-contracts`.
- Optional auditors: `pip install slither-analyzer` and/or `npm i -g solhint`.
- Hermes plugin installed (see `README.md`): symlink this directory to
  `~/.hermes/plugins/hermes-contracts` or run `install.ps1`.
- Without a backend, `contracts_scaffold` returns `available: false` with an
  install hint; without auditors, `contracts_audit` does the same.

## How to Run

Via tools (preferred in-session):

- `contracts_scaffold` with `kind` + `name` (+ `symbol`, `out_dir`).
- `contracts_audit` with `target` pointing at a `.sol` file.

Via CLI (operator terminal):

```bash
hermes contracts status
hermes contracts scaffold erc20 MyToken --symbol MTK --out-dir ./contracts
hermes contracts audit ./contracts/MyToken.sol
```

Via slash command: `/contracts status`, `/contracts audit <file>`,
`/contracts scaffold <kind> <Name>` (tool-guided for full options).

## Quick Reference

| Surface | Command | Maps to |
|---------|---------|---------|
| Tool | `contracts_scaffold(kind, name, symbol?, out_dir?)` | `<out_dir>/<Name>.sol` importing `@openzeppelin/contracts` |
| Tool | `contracts_audit(target)` | `slither` / `solhint` run over the file |
| CLI | `hermes contracts scaffold <k> <N> --symbol S` | Same as `contracts_scaffold` from argv |
| CLI | `hermes contracts audit <file>` | Same as `contracts_audit` from argv |
| Files | `<out_dir>/<Name>.sol` | Consumed by Recourse `/api/recourse/verify` |

## Procedure

1. **Check the backend.** Run `status` (tool-free CLI or `/contracts status`)
   to confirm `forge` or the npm package is visible.
2. **Pick kind + name.** `erc20` / `erc721` / `erc1155` plus a Solidity
   identifier (`MyToken`). Symbols are required for ERC20/721.
3. **Scaffold.** Call `contracts_scaffold` with `kind`, `name`, `symbol`,
   `out_dir`. Confirm the returned `path`.
4. **Audit locally.** Run `contracts_audit` on the emitted file — it shells
   out to real `slither` / `solhint` and reports raw output (truncated).
5. **Hand off.** POST the file at `path` to the Recourse sandboxed verifier
   (`/api/recourse/verify`) — never paste bytecode from memory.
6. **Review.** Treat generated code as a starting point: human review before
   deploy, especially around `Ownable` / mint authority.

## Pitfalls

- **No backend means no file.** Scaffold without `forge` or the npm package
  returns `success: false` + `available: false` rather than writing stubs.
- **No auditor means honest failure.** Audit without `slither`/`solhint`
  returns `available: false` — install one instead of trusting eyeballs.
- **Existing files are never overwritten.** Scaffold refuses when
  `<out_dir>/<Name>.sol` exists — pick a new name or move the old file.
- **Generated mint is owner-only.** The templates ship `Ownable` + owner
  `mint`; change authority deliberately, not accidentally.
- **Shell utilities are wrapped.** Use `` `read_file` `` / `` `search_files` `` /
  `` `patch` `` / `` `terminal` `` for file work, not raw `cat`/`grep`/`sed`.
- **Audit output is truncated.** `stdout` is capped at 4000 chars — rerun the
  auditor directly for full reports.

## Verification

- `hermes contracts status` reports `available: true` with a package path.
- `<out_dir>/<Name>.sol` exists and imports `@openzeppelin/contracts`.
- `contracts_audit` returns `available: true` with per-backend runs.
- The emitted file verifies via Recourse `/api/recourse/verify`.
- AST check: `python -c "import ast; ast.parse(open('__init__.py').read())"`.
- Manifest check: `python -c "import yaml,sys; yaml.safe_load(open('plugin.yaml'))"`.
