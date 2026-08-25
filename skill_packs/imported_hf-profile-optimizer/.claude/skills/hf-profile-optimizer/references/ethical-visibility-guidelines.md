# Ethical Visibility Guidelines

A short charter for responsible discoverability on Hugging Face. Each section is one principle with a do/don't. The rule underneath everything: make genuine work easier to find and understand, never fake or inflate it. When a Hugging Face specific matters, verify it against the current Hugging Face documentation.

---

## Accuracy of claims

Only make claims you can support with evidence.

- Do: back every capability, number, and comparison with a source, a run, or a reproducible setup.
- Do: mark any claim you cannot yet support with "needs evidence" rather than deleting the uncertainty.
- Don't: state capabilities or results you have not actually observed.

## Transparency about limitations

Users deserve to know where the work breaks.

- Do: document intended use, out-of-scope use, and known limitations on every card.
- Do: name biases, failure modes, and the conditions under which quality drops.
- Don't: hide weaknesses to look more polished.

## No invented metrics

Numbers must be real.

- Do: report metrics you measured, with the dataset, split, and setup.
- Don't: fabricate downloads, likes, citations, benchmark numbers, or affiliations.

## No engagement manipulation

Popularity signals must be earned.

- Do: grow visibility through useful work, clear docs, and honest sharing.
- Don't: buy or trade likes, followers, or downloads; create fake accounts; run vote rings; or build artificial backlinks.

## No benchmark cherry-picking

Comparisons must be fair.

- Do: report comparable settings and disclose the full evaluation setup.
- Do: include results that are unfavorable to your work when they are relevant.
- Don't: hide unfavorable results or compare against weaker baselines under mismatched conditions.

## Respect licenses

Licensing is not optional.

- Do: state and honor the license of every model, dataset, and code dependency, plus any third-party terms.
- Do: check compatibility between a base model, its training data, and your chosen license before publishing.
- Don't: relicense or redistribute artifacts in ways their terms forbid.

## Respect sensitive data

Data handling carries real responsibility.

- Do: flag personal or sensitive data, follow data-protection norms, and document consent and anonymization.
- Don't: expose private data or publish content that identifies people without a lawful basis.

## Intended use vs out-of-scope use

Both sides need to be explicit.

- Do: clarify on every card what the artifact is meant for and what it must not be used for.
- Don't: leave scope implicit and let users assume capabilities that were never validated.

## Tokens and privacy

Credentials stay secret.

- Do: read a token from the `HF_TOKEN` environment variable only, and only when needed; default to public-first workflows.
- Don't: expose, hardcode, commit, log, or store a Hugging Face token anywhere.

---

## Principle

Responsible visibility amplifies genuine work; it never replaces or fakes it. Clear cards, honest metrics, documented limits, and respected licenses make real contributions easier to find, trust, and reuse. If a tactic would make weak work look strong rather than making strong work legible, it does not belong here.
