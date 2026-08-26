# hf-profile-optimizer

A Claude Code Agent Skill (SKILL.md format) that audits and optimizes Hugging Face personal or organization profiles, and their Models, Datasets, and Spaces, with accurate, ethical, evidence-based recommendations. It helps you clarify positioning, improve Model/Dataset/Space cards and metadata, curate Collections, and become readable to recruiters, researchers, clients, and open-source users, without deceptive tactics.

## What it does

- Runs a prioritized profile audit with a 0-5 scorecard and quick wins, strategic improvements, and 7-day / 30-day plans.
- Rewrites profile positioning (one-liner, short and long bios, audience-specific and FR/EN variants) without unsupported claims.
- Upgrades Model Cards, Dataset Cards, and Space READMEs (intended use, out-of-scope use, usage snippet, provenance, evaluation, limitations, bias/safety, license, citation) and their YAML metadata.
- Plans a small number of high-signal public Collections, and improves organization cards.
- Provides a launch-readiness checklist before a model, dataset, or Space is announced.

## Ethics and safety

- Never invents metrics, downloads, likes, citations, affiliations, or evaluation results. Missing numbers are marked "needs evidence" or "More Information Needed".
- Never suggests buying fake likes, followers, downloads, or backlinks, or any engagement manipulation or benchmark cherry-picking.
- Never exposes, prints, or stores a Hugging Face token. If a token helps, only the optional `HF_TOKEN` environment variable is used; public mode works without authentication.
- Non-destructive: it proposes changes as patches, drafts, or checklists before publishing, and preserves existing good content.
- It responds in the user's language (French included) and keeps Hub-facing cards in English with bilingual variants when useful.

## Installation

### Claude Code, project level
Open this repository as a project in Claude Code. The skill at `.claude/skills/hf-profile-optimizer/` is auto-discovered. To add it to another project, copy that folder into the project's `.claude/skills/` directory:

```bash
cp -r .claude/skills/hf-profile-optimizer /path/to/your-project/.claude/skills/
```

### Claude Code, global level
Copy the skill into your user skills directory so every session can use it:

```bash
cp -r .claude/skills/hf-profile-optimizer ~/.claude/skills/
```

### Use it
Describe your task in natural language, for example:
- "Optimise mon profil Hugging Face pour un recruteur IA."
- "Audit huggingface.co/<username> and propose a 7-day improvement plan."
- "Improve this model card so it is clearer and more discoverable."

## Optional public metadata collector

`.claude/skills/hf-profile-optimizer/scripts/hf_public_profile_audit.py` collects public repository metadata for a username or organization. It uses the official `huggingface_hub` API (public data, no token required), reads `HF_TOKEN` from the environment only if present, and never prints it.

```bash
cd .claude/skills/hf-profile-optimizer
python3 scripts/hf_public_profile_audit.py --help
python3 scripts/hf_public_profile_audit.py --self-test
python3 scripts/hf_public_profile_audit.py <username> --format md
```

If `huggingface_hub` or network access is missing, the skill continues manually and explains the limitation.

## Repository structure

```
.claude/skills/hf-profile-optimizer/
├── SKILL.md
├── references/
│   ├── audit-rubric.md                 # 0-5 grid across 16 dimensions
│   ├── hf-profile-playbook.md          # practical guide + FR/EN phrasings
│   ├── card-metadata-checklist.md      # checklists + generic YAML (verify current HF docs)
│   └── ethical-visibility-guidelines.md# responsible-visibility charter
├── templates/
│   ├── profile-audit-report.md
│   ├── profile-positioning-brief.md
│   ├── model-card-upgrade.md
│   ├── dataset-card-upgrade.md
│   ├── space-readme-upgrade.md
│   ├── organization-card.md
│   └── collection-plan.md
└── scripts/
    └── hf_public_profile_audit.py      # public-first, HF_TOKEN optional, --self-test
```

## License

MIT. See `LICENSE`.

---

Part of the **[mr-bridge.com](https://mr-bridge.com)** toolkit for scraping, data, and content automation:
[Scrapers](https://mr-bridge.com/scrapers) · [MCP servers](https://mr-bridge.com/mcp-servers) · [AI workflows](https://mr-bridge.com/ai-workflows) · [Studies](https://mr-bridge.com/studies) · [Articles](https://mr-bridge.com/articles) · [Solutions](https://mr-bridge.com/solutions)

---

*Part of the [MrBridge Agent Skills catalog](https://github.com/MrBridgeHQ/skills). Browse them all at [mr-bridge.com/skills](https://mr-bridge.com/skills).*
