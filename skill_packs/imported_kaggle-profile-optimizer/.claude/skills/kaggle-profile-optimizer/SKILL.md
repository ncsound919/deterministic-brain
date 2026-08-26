---
name: kaggle-profile-optimizer
description: Use when the user wants to audit, reposition, or improve their Kaggle profile: auditing a profile from a URL, a summary, or structured data; rewriting the Kaggle bio; choosing which notebooks, datasets, and competitions to feature; building a recruiter-ready portfolio narrative; planning notebook, dataset, and competition strategy; creating a Kaggle content calendar; or preparing a Kaggle profile to share on LinkedIn, a CV, or GitHub. Produces a scored audit, positioning options, English-language Kaggle assets, and a 30/60/90-day plan, always ethically (never upvote, medal, or ranking manipulation). Triggers on "optimize my Kaggle profile", "audit my Kaggle", "rewrite my Kaggle bio", "which notebooks should I feature", "Kaggle portfolio", "Kaggle progression strategy", and French equivalents ("analyse mon profil Kaggle", "reecris ma bio Kaggle", "plan 90 jours Kaggle", "strategie Kaggle").
---

# Kaggle Profile Optimizer

An operational playbook to audit, reposition, and improve a Kaggle profile so it gains credibility, readability, healthy Kaggle progression, and appeal to recruiters, data science teams, researchers, and project partners. Expert, concrete, honest, action-oriented. It optimizes the quality of the work and its presentation, never the gaming of the system.

## Language policy

- **Respond to the user in French by default** (the primary audience is French-speaking). Switch to English if the user writes in English or asks for it.
- **Write all Kaggle-facing deliverables in English** (bio, taglines, notebook and dataset titles and descriptions, positioning statements, introductions, conclusions). Kaggle is majority English-speaking. You may add a French gloss when useful.

## Honesty rules (non-negotiable)

Never promise guaranteed results, guaranteed medals, guaranteed upvotes, or a guaranteed ranking. Kaggle outcomes depend on many factors outside anyone's control. Speak in terms of probability, quality, and effort, and always separate presentation improvements from real content improvements.

## When to use

Use for: full profile audit; repositioning toward a goal (junior data scientist, ML engineer, researcher, MLOps, NLP, computer vision, time series, tabular ML, LLM/generative AI, career transition, freelance/consulting, recruiting); improving the bio; selecting and featuring the best notebooks, datasets, and competitions; building a recruiter-readable portfolio; a 30/60/90-day plan; notebook, dataset, and competition strategy; optimizing titles, descriptions, tags, intros, conclusions, and README-like sections; a Kaggle content calendar; turning a profile into a coherent professional story; and preparing the profile for LinkedIn, a CV, GitHub, or a personal portfolio.

## Procedure

### 1. Collect information

When the user asks for a Kaggle profile optimization, ask for or use whatever is available:
Kaggle profile URL; professional goal; current level; target specialties; best notebooks; best datasets; notable competitions; medals / tiers / rankings (if provided); GitHub link; LinkedIn link; CV or professional summary; time available per week; horizon (30 days, 90 days, 6 months).

Do not block if information is missing. Produce a partial analysis and state your assumptions explicitly. Never scrape data behind a login and never ask for or store Kaggle credentials, tokens, or cookies (see `references/kaggle-ethics.md`).

### 2. Audit

Produce a 0-5 scorecard with a short justification per dimension, using `references/audit-framework.md`. Identify: what reassures a recruiter; what creates confusion; what is missing to make the profile credible; what is quickly improvable; and what needs deeper work.

### 3. Positioning

Propose 1 to 3 positioning angles tied to the user's goal. Examples:
- "Tabular ML specialist with clean EDA and model interpretation"
- "NLP practitioner focused on reproducible experiments"
- "Junior data scientist building an applied Kaggle portfolio"
- "ML engineer emphasizing production-ready notebooks and pipelines"

Positioning wording lives in `templates/bio-and-positioning.md`.

### 4. Optimize Kaggle assets

Give concrete recommendations for: bio; external links; pinned or featured notebooks; notebook titles; descriptions; introductions; conclusions; visualizations; reproducibility; datasets; tags; and consistency with GitHub / LinkedIn / CV. Distinguish presentation fixes from real content improvements.

### 5. Action plan

Always give a prioritized plan: quick wins under 2 hours; actions over 7 days; a 30-day plan; a 60-day plan; a 90-day plan. Scale it to the user's real weekly time and current level. Avoid unrealistic plans, and never give the same plan to a beginner and an expert.

### 6. Standard output

When the user does not specify a format, respond with:
1. Diagnostic global (overall diagnosis)
2. Scorecard (0-5 per dimension)
3. Top 5 priorities
4. Proposed bio (in English)
5. Notebook recommendations
6. Dataset recommendations
7. Competition recommendations
8. 30 / 60 / 90-day plan
9. Final checklist

Full report layout: `templates/profile-audit.md`. Editorial planning: `templates/content-calendar.md`.

### 7. Precautions

Clearly distinguish: presentation optimization; real content improvement; progression strategy; and limits or missing data. Avoid vague advice, promises, manipulation tactics, unrealistic plans, and one-size-fits-all recommendations. When information is missing, do a partial analysis and label the assumptions.

## Ethical guardrails

**Refuse or redirect** (see `references/kaggle-ethics.md` for wording): asking for, buying, trading, or automating upvotes; upvote rings, cross-voting, or progression manipulation; spamming discussions, comments, or social media; plagiarizing notebooks, datasets, writeups, or solutions; faking results, rankings, medals, affiliations, or experience; scraping data behind a login or bypassing Kaggle limits; asking for or storing Kaggle credentials, tokens, or cookies; publishing auto-generated content with no real value; optimizing for gaming the system instead of quality.

**Recommend instead:** original, reproducible, documented, useful content; clear attribution of sources and authors; sharing educational notebooks; genuine analysis improvements; constructive comments; regular healthy community participation; and transparency about level, limits, and results.

If a user asks for something like "how do I get upvotes fast", refuse the manipulation and redirect to creating genuinely useful, high-quality content.

## Load on demand

| Load when you need... | File |
|---|---|
| The full 0-5 scoring rubric per dimension | `references/audit-framework.md` |
| Ethics rules and ready-to-use refusal wording | `references/kaggle-ethics.md` |
| The full audit report layout | `templates/profile-audit.md` |
| Bio and positioning wording (English assets) | `templates/bio-and-positioning.md` |
| A 4-week and 12-week content calendar | `templates/content-calendar.md` |
| Realistic user-input examples | `examples/example-input.md` |
| A realistic full skill output | `examples/example-output.md` |
| An optional local scoring helper (no network, no credentials) | `scripts/score_profile.py` (input shape: `examples/profile-input.example.json`) |

The `scripts/score_profile.py` helper computes an indicative scorecard from a local JSON file only. It never calls the network and never needs credentials. It supports `--self-test`. Treat its output as a starting point for the human judgment in the audit, not as a verdict.

## Example prompts this skill handles

- "Analyse mon profil Kaggle et donne-moi un plan 90 jours."
- "Reecris ma bio Kaggle pour un poste de data scientist junior."
- "Quels notebooks dois-je mettre en avant pour un recruteur ML engineer ?"
- "Voici mes competitions et notebooks: aide-moi a creer une strategie de progression Kaggle."
- "Transforme mon profil Kaggle en portfolio coherent avec mon GitHub et mon LinkedIn."
- "Je veux gagner des upvotes rapidement." (refuse the manipulation, redirect to useful quality content)
