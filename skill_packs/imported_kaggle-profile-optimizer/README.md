# kaggle-profile-optimizer

A Claude Code Agent Skill (SKILL.md format) that helps you audit, reposition, and improve your Kaggle profile so it gains credibility, readability, healthy Kaggle progression, and appeal to recruiters, data science teams, researchers, and project partners. Expert, concrete, honest, action-oriented, and ethical by design.

## What it does

- Runs a full profile audit with a 0-5 scorecard across 12 dimensions (positioning, technical credibility, notebook and dataset quality, competitions, reproducibility, professional narrative, recruiter signals, cross-platform consistency, recent activity, specialization, and healthy community contribution).
- Repositions the profile toward a goal (junior data scientist, ML engineer, researcher, MLOps, NLP, computer vision, time series, tabular ML, LLM/generative AI, career transition, freelance/consulting, recruiting).
- Rewrites the bio and produces ready-to-use English Kaggle assets (bio, taglines, titles, descriptions, positioning statements).
- Recommends which notebooks, datasets, and competitions to feature, and how to optimize titles, descriptions, tags, intros, and conclusions.
- Builds a 30/60/90-day action plan and a 4-week and 12-week content calendar scaled to your real weekly time and level.
- Prepares a coherent professional story to share on LinkedIn, a CV, GitHub, or a personal portfolio.

## Honesty and ethics

- It never promises guaranteed medals, upvotes, rankings, or results. Kaggle outcomes depend on many factors, so it speaks in terms of quality, probability, and effort.
- It refuses and redirects any request to manipulate the system: buying, trading, or automating upvotes, upvote rings and cross-voting, spamming, plagiarizing notebooks or solutions, faking results or rankings, scraping behind a login, or storing Kaggle credentials.
- It recommends the opposite: original, reproducible, documented, useful content, clear attribution, educational notebooks, genuine analysis improvements, and transparent reporting of level and limits.

## Language policy

The skill responds to the user in French by default and writes all Kaggle-facing deliverables (bio, titles, descriptions, positioning) in English, since Kaggle is majority English-speaking. It switches to English if you write in English.

## Installation

### Claude Code, project level
Open this repository as a project in Claude Code. The skill at `.claude/skills/kaggle-profile-optimizer/` is auto-discovered. To add it to another project, copy that folder into the project's `.claude/skills/` directory:

```bash
cp -r .claude/skills/kaggle-profile-optimizer /path/to/your-project/.claude/skills/
```

### Claude Code, global level
Copy the skill into your user skills directory so every session can use it:

```bash
cp -r .claude/skills/kaggle-profile-optimizer ~/.claude/skills/
```

### Use it
Just describe your task in natural language, for example:
- "Analyse mon profil Kaggle et donne-moi un plan 90 jours."
- "Rewrite my Kaggle bio for a junior data scientist role."
- "Which notebooks should I feature for an ML engineer recruiter?"
- "Turn my Kaggle profile into a portfolio consistent with my GitHub and LinkedIn."

## Optional local scoring helper

`scripts/score_profile.py` computes an indicative 0-5 scorecard from a local JSON file. It makes no network calls and needs no credentials.

```bash
cd .claude/skills/kaggle-profile-optimizer
python3 scripts/score_profile.py examples/profile-input.example.json
python3 scripts/score_profile.py --self-test
```

The score is a diagnostic aid, not a verdict, and no outcome is guaranteed.

## Repository structure

```
.claude/skills/kaggle-profile-optimizer/
├── SKILL.md
├── references/
│   ├── audit-framework.md          # 0-5 rubric across 12 dimensions
│   └── kaggle-ethics.md            # conduct rules + ready-to-use refusals (FR + EN)
├── templates/
│   ├── profile-audit.md            # full audit report layout
│   ├── bio-and-positioning.md      # English bio and positioning assets
│   └── content-calendar.md         # 4-week and 12-week calendars
├── examples/
│   ├── example-input.md            # 5 realistic profiles
│   ├── example-output.md           # a full realistic output
│   └── profile-input.example.json  # input for the scoring script
├── scripts/
│   └── score_profile.py            # local scorecard, no network, --self-test
└── tests/
    └── test_score_profile.py       # pytest tests
```

## License

MIT. See `LICENSE`.

---

Part of the **[mr-bridge.com](https://mr-bridge.com)** toolkit for scraping, data, and content automation:
[Scrapers](https://mr-bridge.com/scrapers) · [MCP servers](https://mr-bridge.com/mcp-servers) · [AI workflows](https://mr-bridge.com/ai-workflows) · [Studies](https://mr-bridge.com/studies) · [Articles](https://mr-bridge.com/articles) · [Solutions](https://mr-bridge.com/solutions)

---

*Part of the [MrBridge Agent Skills catalog](https://github.com/MrBridgeHQ/skills). Browse them all at [mr-bridge.com/skills](https://mr-bridge.com/skills).*
