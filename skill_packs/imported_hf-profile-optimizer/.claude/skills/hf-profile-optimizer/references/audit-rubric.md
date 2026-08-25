# Audit Rubric

This is a 0-5 scoring grid for auditing a Hugging Face personal or organization profile and its public repositories (models, datasets, Spaces).

How to use it:

- Score from observed evidence only. Read what is actually on the profile and repository pages, then score.
- When the evidence needed for a dimension is missing, do not guess. Mark that dimension "insufficient data" and state exactly what the user should provide (a URL, a screenshot, the raw README, the YAML frontmatter, the Collections list, and so on).
- Never invent metrics. Do not assume download counts, likes, citations, eval results, or affiliations that you cannot see.
- The number is a diagnostic aid, not a guarantee. A high score describes a well-structured, discoverable, trustworthy profile. It does not promise downloads, hiring outcomes, or citations.

Each dimension below has four labeled parts (What to check, Signs of a strong profile, Signs of a weak profile, Typical recommendations) and an anchored scale line describing what 0, 1, 3, and 5 look like.

## Positioning clarity

- What to check: The profile bio, header, pinned items, and organization card. Is it immediately clear who this person or org is, what they build, and for whom?
- Signs of a strong profile: A concise bio stating role, domain, and focus; a coherent theme across pinned repos; a link to a homepage or paper that matches the stated focus.
- Signs of a weak profile: Empty or generic bio, no stated focus, pinned items that contradict the bio, or a wall of unrelated repos with no framing.
- Typical recommendations: Draft a one-line positioning statement (role plus domain plus artifact type); pin 3-6 representative repos; align the bio, homepage link, and pinned items.
- Scale: 0 = no bio and no discernible focus. 1 = a name only, focus must be inferred. 3 = a readable bio with a mostly clear focus, minor mismatches. 5 = a sharp, specific positioning statement that the pinned repos visibly support.

## Audience fit

- What to check: Whether the language, artifacts, and framing match the intended readers (researchers, ML engineers, product teams, recruiters, or hobbyists).
- Signs of a strong profile: Terminology and detail level suited to the target reader; usage snippets for engineers, eval detail for researchers, plain framing for non-specialists where appropriate.
- Signs of a weak profile: One-size register that serves no audience well; jargon with no entry point, or oversimplification that omits what a technical reader needs.
- Typical recommendations: Name the primary audience explicitly; adjust the README opening to that reader; add a short "who is this for" line to key repos.
- Scale: 0 = no identifiable audience, content serves no one. 1 = audience unclear, register inconsistent. 3 = a plausible primary audience served adequately. 5 = a clearly targeted audience with framing, depth, and examples matched to it.

## Portfolio coherence

- What to check: Whether the set of public repos tells a consistent story or reads as scattered, unrelated uploads.
- Signs of a strong profile: Repos cluster around a theme or a small number of themes; naming and topics reinforce each other; abandoned experiments are archived, hidden, or clearly labeled.
- Signs of a weak profile: A long list of one-off forks, test uploads, and duplicates with no organizing logic.
- Typical recommendations: Group repos into Collections by theme; propose archiving or clearly labeling stale experiments (never delete without user confirmation); lead with the flagship repos.
- Scale: 0 = no coherence, only scattered uploads. 1 = one or two anchor repos lost in noise. 3 = a recognizable theme with some clutter. 5 = a tightly coherent portfolio where every visible repo supports the positioning.

## Repo naming

- What to check: Repository slugs and display names for clarity, convention, and searchability.
- Signs of a strong profile: Descriptive, consistent names that signal task, base model, language, or size where relevant; predictable conventions across the account.
- Signs of a weak profile: Names like "model", "test", "final2", or opaque hashes; inconsistent casing and separators.
- Typical recommendations: Propose clearer slugs following a consistent pattern (note that renaming affects URLs, so flag redirects and links before advising a change); reserve dates and version numbers for a versioning field, not the name.
- Scale: 0 = meaningless or placeholder names. 1 = names present but cryptic or inconsistent. 3 = mostly clear names with some legacy exceptions. 5 = clear, consistent, searchable names across the portfolio.

## Repo descriptions

- What to check: The short description shown in listings and search, separate from the full README.
- Signs of a strong profile: Every public repo has a concise, accurate description with the key task and distinguishing detail.
- Signs of a weak profile: Empty descriptions, or descriptions that just repeat the name.
- Typical recommendations: Draft a one-line description per repo (task plus what makes it distinct); keep it truthful and specific; avoid unverifiable superlatives.
- Scale: 0 = no descriptions. 1 = a few present, vague or duplicated. 3 = most repos described adequately. 5 = every repo has a crisp, accurate, informative one-liner.

## Model Card completeness

- What to check: The model README against the sections a reader needs to evaluate and use the model. Verify the current Hugging Face Model Card documentation for the sections expected today rather than assuming a fixed list.
- Signs of a strong profile: Clear intended use, how to load and run, training data summary, evaluation, limitations, and license, all present and mutually consistent.
- Signs of a weak profile: A stub README, missing intended use, no usage snippet, or claims with no backing.
- Typical recommendations: Fill gaps section by section; add a runnable usage snippet; only state eval numbers that the user can substantiate, otherwise mark them as not yet available.
- Scale: 0 = empty or auto-generated stub. 1 = a title and one paragraph. 3 = most core sections present, some thin. 5 = a complete, internally consistent, substantiated card.

## Dataset Card completeness

- What to check: The dataset README for description, structure, source, collection method, splits, licensing, and known limitations. Verify current Hugging Face Dataset Card documentation for the expected sections.
- Signs of a strong profile: Clear description of contents and schema, provenance, intended use, licensing, and documented limitations or biases.
- Signs of a weak profile: No provenance, unclear licensing, no field descriptions, or missing split information.
- Typical recommendations: Document schema and splits; state source and collection method truthfully; add a licensing and permitted-use section; note known gaps.
- Scale: 0 = empty or stub. 1 = a bare description only. 3 = structure and license present, provenance thin. 5 = a thorough, well-sourced, clearly licensed dataset card.

## Space README quality

- What to check: The Space README and its configuration frontmatter, plus whether the demo communicates what it does and how to use it.
- Signs of a strong profile: Clear purpose, instructions, a note on what the demo shows, links back to the underlying model or dataset, and correct config.
- Signs of a weak profile: A default template README, no instructions, no link to the source artifacts, or a broken demo.
- Typical recommendations: Rewrite the README to state purpose, inputs, and limits; link the underlying repos; verify the config frontmatter matches the app.
- Scale: 0 = default template, no useful content. 1 = a title and a screenshot. 3 = a working demo with basic instructions. 5 = a polished demo README with purpose, usage, limits, and source links.

## YAML metadata

- What to check: The frontmatter of each repo README (license, language, tags, task and pipeline fields, linked datasets and metrics, and similar). Confirm exact valid keys against current Hugging Face documentation before asserting any are required.
- Signs of a strong profile: Accurate, relevant metadata that improves filtering and discovery, consistent with the README body.
- Signs of a weak profile: Missing frontmatter, wrong or invented keys, tags that do not match the content, or metadata that contradicts the prose.
- Typical recommendations: Add the fields that apply and are verifiable; remove inaccurate tags; keep metadata and body consistent; validate keys against current docs rather than guessing.
- Scale: 0 = no frontmatter. 1 = a license only. 3 = several accurate fields, some gaps. 5 = complete, accurate, consistent metadata aligned with the content.

## License clarity

- What to check: Whether every public artifact states a license, whether it is appropriate for the content, and whether model, dataset, and base-model licenses are compatible.
- Signs of a strong profile: An explicit license on each repo, consistent between the license field and any LICENSE file, with base-model or source-data terms respected.
- Signs of a weak profile: No license, a license field that conflicts with the README, or terms that ignore an inherited license.
- Typical recommendations: Set an explicit license per repo; reconcile the field, the file, and the prose; flag any inherited-license obligations for the user to confirm (advise, do not decide legal questions for them).
- Scale: 0 = no license anywhere. 1 = license on some repos, inconsistent. 3 = licenses present and mostly consistent. 5 = explicit, consistent, compatible licensing across the portfolio.

## Usage examples

- What to check: Whether key model or dataset repos show a copy-pasteable way to load and run the artifact.
- Signs of a strong profile: A minimal, correct snippet (load plus a call) that a reader can run; input and output shown or described.
- Signs of a weak profile: No snippet, an incomplete snippet, or code that would not run as written.
- Typical recommendations: Add a minimal runnable example; show expected input and output; keep dependencies and calls current and correct.
- Scale: 0 = no usage guidance. 1 = a partial or non-runnable snippet. 3 = a working snippet for the main path. 5 = clear, correct, runnable examples covering the primary use.

## Evaluation transparency

- What to check: Whether any performance claims are backed by stated benchmarks, metrics, and conditions, and whether numbers are reproducible or at least sourced.
- Signs of a strong profile: Metrics tied to named datasets and settings, with enough detail to interpret them; honest scope on what was and was not tested.
- Signs of a weak profile: Bare claims of quality, cherry-picked numbers with no setup, or "state of the art" with no reference.
- Typical recommendations: State the benchmark, metric, and conditions for each number; never fabricate or round toward flattery; mark untested areas as untested rather than implying results.
- Scale: 0 = unbacked quality claims. 1 = numbers with no context. 3 = some metrics with partial context. 5 = clearly sourced, interpretable, honestly scoped evaluation.

## Limitations and bias documentation

- What to check: Whether the card acknowledges failure modes, out-of-scope uses, data biases, and risks.
- Signs of a strong profile: A concrete limitations section naming real weaknesses, known biases, and uses to avoid.
- Signs of a weak profile: No limitations section, or a boilerplate paragraph that says nothing specific.
- Typical recommendations: Add a specific limitations and bias section grounded in the actual data and task; state out-of-scope and high-risk uses; keep it honest rather than reassuring.
- Scale: 0 = no mention of limitations. 1 = a generic disclaimer only. 3 = some real limitations named. 5 = a candid, specific account of limitations, biases, and unsafe uses.

## Collections strategy

- What to check: Whether Collections are used to group and surface related work in a way that guides a visitor.
- Signs of a strong profile: A small number of well-titled Collections that map to themes and lead a visitor from entry point to depth.
- Signs of a weak profile: No Collections, or Collections that are unlabeled dumps with no narrative.
- Typical recommendations: Create theme-based Collections with clear titles and short descriptions; order them to tell a story; feature the flagship Collection.
- Scale: 0 = no Collections. 1 = one unlabeled or incoherent Collection. 3 = usable Collections with room to improve. 5 = a deliberate Collections structure that guides discovery.

## Maintenance and recency

- What to check: Signs of upkeep visible on the pages: recent commits, current usage instructions, working links, and absence of obvious rot.
- Signs of a strong profile: Recently touched flagship repos, instructions that match current libraries, and no dead links.
- Signs of a weak profile: Long-stale flagship repos, outdated install or usage steps, and broken links or images.
- Typical recommendations: Refresh the flagship repos first; fix dead links and outdated snippets; archive or label truly inactive work rather than leaving it to look neglected.
- Scale: 0 = everything appears abandoned. 1 = mostly stale with rot. 3 = flagships maintained, long tail stale. 5 = the visible portfolio looks actively and consistently maintained.

## Community/discussion readiness

- What to check: Whether the repos invite and can handle engagement: discussions or community tab enabled where appropriate, contact or issue guidance, and responsiveness signals.
- Signs of a strong profile: Clear guidance on how to report problems or ask questions, discussions enabled where it helps, and evidence of engagement being handled.
- Signs of a weak profile: No path for feedback, disabled or ignored discussions, and no contact route.
- Typical recommendations: Add a short "questions and issues" note; enable discussions where useful; set expectations on support and response.
- Scale: 0 = no path for engagement. 1 = a channel exists but is unused or unmanaged. 3 = a basic feedback path in place. 5 = a clear, managed, welcoming path for community engagement.

## Scoring notes

- Average only the dimensions you actually scored. Exclude any dimension marked "insufficient data" from the average, and never substitute a guessed value for missing evidence.
- Report coverage alongside the score: state how many of the 16 dimensions were scored (for example, "coverage: 12 of 16") so the reader knows how much the average rests on.
- Present the result as a diagnostic snapshot of structure, discoverability, and trust, based on observed evidence at a point in time.
- Never present the score as a guarantee of downloads, hiring, or citations. It reflects how the profile is built and documented, not outcomes it cannot control.
