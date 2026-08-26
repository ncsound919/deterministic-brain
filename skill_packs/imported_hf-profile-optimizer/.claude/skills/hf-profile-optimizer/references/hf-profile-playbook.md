# Hugging Face Profile Playbook

A practical, skimmable guide to optimizing a Hugging Face presence: personal profiles, organizations, and the repositories that carry your work (Models, Datasets, Spaces, Collections).

The goal is honest discoverability. Make your real work easy to find, understand, and trust. Do not fake signals, and do not overclaim. Hugging Face features and UI change over time, so verify specifics against the current Hugging Face documentation when a detail is load-bearing.

---

## Personal profiles

Your profile is the first thing people read. Make it accurate and specific.

- **Bio and headline**: one or two sentences that say who you are and what you actually build. Name your domain (for example NLP, computer vision, speech, tabular, RAG) and your role. Prefer concrete verbs over adjectives.
- **Name, avatar, consistency**: use a real display name and a recognizable avatar. Keep the same name, handle, and avatar across Hugging Face, GitHub, and your site so people know it is the same person.
- **Interests and topics**: list the areas you genuinely work in. This helps the right people and the right recommendations find you. Do not pad with unrelated buzzwords.
- **Pinned and visible repos**: surface a small number of your strongest public repos. A visitor should understand your best work within a few seconds. Quality over quantity.
- **External links**: link to your GitHub, personal site, papers, or blog. Every link should resolve and point to something current.
- **What a strong personal profile signals**: active maintenance, a clear specialty, reproducible work, and honesty about scope. It reads as "this person ships real, documented things," not "this person collects empty repos."

---

## Organization profiles

An org profile represents a team or project. It should make the mission and the entry points obvious.

- **Org card**: a short, clear description of what the org does and who it serves. State the focus in the first line.
- **Maintained artifacts**: feature the models, datasets, and Spaces the org actively maintains. Mark clearly anything experimental or archived.
- **Mission**: one short paragraph on purpose and scope. Avoid slogans; say what the org produces and for whom.
- **How to contribute**: point to guidelines, issues, discussions, or a repo where contributions are welcome. Make the first step easy to find.
- **Contact**: give a real way to reach the team (a linked page, a discussion space, or an email the org actually reads).

---

## Models

A Model Card is documentation, not marketing. A good card lets someone decide, use, and cite responsibly.

- **Naming**: a clear, predictable name. Include the base architecture, task, and variant where it helps (for example `base-model-task-lang`). Avoid cryptic names.
- **Clear summary**: one short paragraph at the top: what the model is, the task it does, and what it was trained on at a high level.
- **Intended use**: state the use cases the model is meant for, and note out-of-scope uses explicitly.
- **How-to-use snippet**: a minimal, copy-pasteable code example (typically `transformers` or the relevant library) that loads the model and runs one inference. Keep it runnable.
- **Provenance**: name the base model, the training data sources at a high level, and any parent models. Link them where possible.
- **Evaluation transparency**: report metrics with the dataset, split, and setup used. Describe the evaluation so a reader can judge comparability. Do not present numbers without their setup.
- **Limitations**: known failure modes, biases, and conditions where the model degrades. Be candid; this builds trust.
- **License**: state the license clearly and make sure it is compatible with the base model and training data terms.
- **Tags and metadata**: fill the card metadata (task, language, library, license, base model, datasets) so the model is filterable and discoverable. Use accurate tags only; no keyword stuffing.

---

## Datasets

A Dataset Card should let a stranger understand, trust, and reuse the data.

- **Naming**: descriptive and specific. Convey domain, language, and task where relevant.
- **Summary**: one paragraph on what the dataset contains and what it is for.
- **Structure, fields, splits**: describe each field and its type, the splits (train/validation/test), and rough sizes. A small example row helps a lot.
- **Collection process**: explain how the data was gathered or generated, over what period, and any filtering or annotation steps. Reproducibility matters.
- **Licensing**: state the dataset license and any source terms it inherits. Check that redistribution is permitted.
- **Sensitive-data notes**: flag any personal, private, or otherwise sensitive content. Note anonymization, consent, and known risks. If none, say so explicitly.
- **Intended use**: the tasks the dataset is meant to support, plus out-of-scope uses to avoid.

---

## Spaces

A Space is a live demo. Its README should make the demo self-explanatory even before it loads.

- **What the demo does**: one line on the purpose and what a visitor can try.
- **Try it**: clear instructions to get a first result quickly.
- **Inputs and outputs**: what the user provides and what they get back, with formats.
- **Dependencies**: the models, datasets, or APIs the Space relies on. Link them.
- **Runtime expectations**: note approximate response time, hardware tier if relevant, and whether cold starts or queues apply.
- **Limitations**: what the demo does not do, size or rate limits, and known rough edges.
- **Local run**: instructions to clone and run it locally (dependencies, environment variables, launch command). If a token is needed, use `HF_TOKEN` as an environment variable; never hardcode it.

---

## Collections

Collections group related work into a curated story.

- **Curate a few high-signal collections**: a small number of focused collections beats many thin ones. Each should have a clear theme.
- **Ordering**: order items so the collection reads logically, most representative or most recent first, depending on the theme.
- **The "complete project" pattern**: when the pieces exist, group a project end to end: paper (or write-up) + dataset + model + Space. This lets someone read, reproduce, and try in one place, and it is a strong trust signal.
- Keep collections tidy: remove stale or off-topic items so the signal stays high.

---

## External links and consistency

Discoverability improves when your footprint tells one coherent story.

- Keep your profile, repos, demos, papers, docs, blog posts, and GitHub consistent in naming, claims, and versions.
- Cross-link cleanly: model to Space, Space to model and dataset, repo to paper, profile to site. Every link should resolve.
- Avoid contradictions: the same metric, license, or capability should read the same everywhere. If you update a claim in one place, update it everywhere.
- Prefer canonical links (the official repo or paper page) over duplicates.

---

## Common mistakes

- Vague bios that say nothing specific about what you build.
- Empty or auto-generated cards left at their default template.
- Missing or unstated license.
- No usage snippet, so users cannot try the model quickly.
- No limitations section, which erodes trust.
- Unversioned or abandoned repos with no maintenance signal.
- Cluttered collections that dilute the signal.
- Unsupported claims (metrics or capabilities you cannot back).
- Keyword stuffing in tags or text, which hurts credibility and rarely helps discovery.

---

## FR/EN phrasing examples

These are illustrative templates with placeholders. Keep them honest and specific, no hype, no invented results. Replace every placeholder with real, verifiable content.

**Bio line**
- EN: "I build [task] models for [domain]; I maintain [N] public repos and share reproducible training code."
- FR: "Je construis des modeles de [tache] pour [domaine] ; je maintiens [N] depots publics et je partage du code d'entrainement reproductible."

**Model summary line**
- EN: "[Model] is a [architecture] fine-tuned from [base model] for [task] on [dataset]."
- FR: "[Modele] est un [architecture] affine a partir de [modele de base] pour [tache] sur [jeu de donnees]."

**Intended-use line**
- EN: "Intended for [use case] in [language/domain]; out of scope for [excluded use], where it is untested."
- FR: "Prevu pour [cas d'usage] en [langue/domaine] ; hors perimetre pour [usage exclu], ou il n'est pas teste."

**Evaluation line (state the setup, never a bare number)**
- EN: "On [dataset] ([split]), it reaches [metric] under [setup]; see the evaluation section for details."
- FR: "Sur [jeu de donnees] ([split]), il atteint [metrique] avec [configuration] ; voir la section evaluation pour les details."
