# Audit Framework

This framework scores a Kaggle profile from 0 to 5 across 12 dimensions. Scores reflect the evidence actually provided by the user (a profile URL, a screenshot, a text summary, or structured data). When the evidence needed for a dimension is missing, mark that dimension "insufficient data", state exactly what to provide to score it, and do not invent a number. A guessed score is worse than an honest gap: it misleads the user about where to spend their effort.

The audit is a diagnostic aid. It tells the user where their profile is strong and where it is thin. It never predicts medals, upvotes, tier changes, or recruiter outcomes, and it must never be presented as such.

## Scoring scale

- 0 = absent: the dimension is not present at all.
- 1 = very weak: present in name only, no substance.
- 2 = weak: some content, but clearly underdeveloped or low quality.
- 3 = acceptable: solid baseline, meets a reasonable standard without standing out.
- 4 = strong: clearly above average, well executed, few gaps.
- 5 = excellent: best-in-class, a genuine differentiator.

## Positioning clarity

What it measures: whether a visitor understands, within a few seconds, who this person is, what they do, and who they are for.

- A 5 looks like: a bio and profile that state a clear specialty, target audience, and value in one or two lines, consistent across bio, pinned work, and activity.
- A 1-2 looks like: an empty or generic bio ("Data enthusiast"), no stated focus, and featured items that pull in unrelated directions.

Signals to check:
- Does the bio name a domain, a role, or a problem the person solves?
- Do the pinned/featured items reinforce that message or contradict it?
- Could a stranger paraphrase the positioning after 10 seconds?

How to improve: write a one-line positioning statement (specialty + audience + proof) and make every featured item support it.

## Technical credibility

What it measures: visible evidence of real technical skill, not just claims.

- A 5 looks like: notebooks and datasets that demonstrate depth (sound methodology, clean code, correct evaluation), with concrete, verifiable results.
- A 1-2 looks like: assertions of expertise with little or no work to back them, or work that shows basic errors (leakage, no validation, copied boilerplate).

Signals to check:
- Is there code that a reviewer could read and respect?
- Are results measured and reproducible, or just stated?
- Does the difficulty of the work match the claimed level?

How to improve: publish one or two pieces that show correct methodology end to end, and describe the reasoning, not just the output.

## Notebook quality

What it measures: the craft of the published notebooks (structure, clarity, code, narrative, visuals).

- A 5 looks like: notebooks with a clear question, readable and documented code, meaningful visuals, honest interpretation, and a conclusion a reader can act on.
- A 1-2 looks like: unstructured cells, no explanation, broken or unrun outputs, charts with no takeaway.

Signals to check:
- Is there a stated goal and a conclusion?
- Is the code commented and does it run top to bottom?
- Do the visuals carry an insight or just decorate?

How to improve: pick the two best notebooks, add a clear intro and conclusion, comment the code, and ensure every chart answers a question.

## Dataset quality

What it measures: the value and care of any published datasets.

- A 5 looks like: a well-documented dataset with a clear description, licensing, column-level metadata, provenance, and a genuine use case, ideally with a starter notebook.
- A 1-2 looks like: an undocumented dump with no description, unclear source, no license, or duplicate of an existing dataset with no added value.

Signals to check:
- Is there a real description, column documentation, and a license?
- Is the provenance clear and the collection method legitimate?
- Does the dataset serve a use case others would want?

How to improve: add a thorough description, document columns and license, state provenance, and ship a small starter notebook.

## Competitions and progression

What it measures: participation in competitions and evidence of learning over time.

- A 5 looks like: a track record of meaningful participation with visible progression in approach and results, and write-ups that explain what was learned.
- A 1-2 looks like: no participation, or a single abandoned entry with no reflection.

Signals to check:
- Is there real participation, not just a joined-and-left record?
- Does approach or performance improve across entries?
- Are there write-ups explaining decisions and lessons?

How to improve: enter one competition aligned with the stated specialty, and publish a short write-up on the approach and the lessons, regardless of rank.

## Reproducibility

What it measures: whether others can rerun the work and get the same result.

- A 5 looks like: pinned versions, seeds set, clear data sources, environment noted, and notebooks that run top to bottom without manual patching.
- A 1-2 looks like: hidden dependencies, no seeds, missing data paths, outputs that cannot be regenerated.

Signals to check:
- Do notebooks run end to end from a clean state?
- Are random seeds and key versions fixed?
- Are data sources and paths explicit?

How to improve: set seeds, pin critical versions, reference data sources explicitly, and verify a clean top-to-bottom run.

## Professional narrative

What it measures: whether the profile tells a coherent story a professional audience can follow.

- A 5 looks like: bio, featured work, and activity that together explain a trajectory (where the person came from, what they focus on, where they are going).
- A 1-2 looks like: disconnected artifacts with no throughline, or a narrative that overstates experience.

Signals to check:
- Is there a throughline connecting the featured items?
- Does the story match the evidence (no inflation)?
- Would a hiring manager understand the person's focus and direction?

How to improve: choose a single narrative thread and order the featured work so it reads as a progression toward the stated focus.

## Recruiter signals

What it measures: the presence of the concrete cues recruiters and hiring managers look for.

- A 5 looks like: clear specialty, evidence of applied skill, links to GitHub/LinkedIn/portfolio, contactability, and work that maps to real job requirements.
- A 1-2 looks like: no external links, no clear skill area, nothing that connects the profile to a role.

Signals to check:
- Are there working links to GitHub, LinkedIn, or a portfolio?
- Is the specialty legible in job-market terms?
- Is there at least one piece a recruiter could show a hiring manager?

How to improve: add external links, state the specialty in role terms, and feature one piece that clearly demonstrates job-relevant skill.

## Consistency with GitHub / LinkedIn / CV

What it measures: whether the Kaggle profile aligns with the person's other professional surfaces.

- A 5 looks like: name, headline, specialty, and headline projects that match across Kaggle, GitHub, LinkedIn, and CV, with no contradictions in claims or dates.
- A 1-2 looks like: conflicting titles, mismatched specialties, or claims on one surface not supported by the others.

Signals to check:
- Do the headline and specialty match across surfaces?
- Do project names and claims line up?
- Are there date or level contradictions?

How to improve: pick one canonical positioning and align the headline, specialty, and flagship projects everywhere. Only score this when the other surfaces are provided.

## Recent activity

What it measures: whether the profile shows current, ongoing engagement.

- A 5 looks like: regular, recent activity (notebooks, datasets, competition entries, or substantive discussion) over the past months.
- A 1-2 looks like: a profile that has been dormant for a long time, with the latest work far in the past.

Signals to check:
- When was the most recent published work?
- Is activity steady or a single old burst?
- Is the cadence sustainable rather than crammed?

How to improve: set a realistic, sustainable cadence (for example one quality notebook per month) rather than a short burst followed by silence.

## Specialization

What it measures: whether the profile signals depth in a focused area rather than shallow breadth.

- A 5 looks like: a recognizable niche (a domain, technique, or data type) reinforced across bio and featured work, with depth others would cite.
- A 1-2 looks like: scattered work across many unrelated topics with no depth in any.

Signals to check:
- Is there an identifiable niche?
- Does the featured work go deep rather than wide?
- Would a peer associate this person with a specific area?

How to improve: choose one niche that fits the person's real interest and background, and concentrate the next few pieces of work there.

## Healthy community contribution

What it measures: genuine, constructive participation in the Kaggle community.

- A 5 looks like: thoughtful comments, useful shared resources, helpful answers, and collaboration that adds real value for others.
- A 1-2 looks like: no engagement, or low-value activity (generic comments, self-promotion, anything that looks like gaming participation).

Signals to check:
- Are comments and contributions substantive and helpful?
- Does the engagement help others, not just the person's own metrics?
- Is participation free of manipulation patterns?

How to improve: leave a few genuinely useful comments or answers each month and share a resource others can reuse. Quality of contribution, never volume for its own sake.

## Computing the overall score

Average only the dimensions that had enough evidence to be scored. Do not count "insufficient data" dimensions as zero: that would penalize the user for a gap in what they shared, not a gap in their profile.

Always report coverage: state how many of the 12 dimensions were scorable (for example "9 of 12 scored; 3 marked insufficient data") so the reader knows how complete the picture is. Low coverage means the average is provisional, so say so.

Present the overall number as a diagnostic aid only. It summarizes where the profile stands today and where the effort should go next. It is never a prediction or a guarantee of medals, upvotes, tier changes, ranking, or recruiter outcomes, and it must never be framed that way.

These 12 dimensions, in this order, are the same ones the optional `scripts/score_profile.py` helper computes, so a manual audit and the script report the same structure.
