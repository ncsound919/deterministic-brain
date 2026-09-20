---
name: hermes-oasst2
description: Sample and eval with OpenAssistant oasst2 data.
version: 0.1.0
author: Draymond-Orchestrator fleet
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [eval, reward-model, preferences, oasst2, alignment]
    category: evaluation
    related_skills: [plan, requesting-code-review]
    config: {}
---

# OASST2 Skill

Reward-model style eval on human-preference data from the HuggingFace
dataset `OpenAssistant/oasst2`. Sample real ranked rows, then score a
model's ranking of dataset messages against the dataset's own human rank
signal. This skill never fabricates rankings — without network +
HuggingFace access the tools report `available: false`.

Upstream note: the code repo https://github.com/LAION-AI/Open-Assistant is
COMPLETED/archived. Only the HF dataset `OpenAssistant/oasst2` matters.

## When to Use

- Sampling real human-preference pairs for reward-model style eval.
- Scoring a model's best-first ranking of assistant replies vs human ranks.
- Feeding chosen/rejected pairs to the Hermes curator + learning_graph.
- Checking whether dataset access works (`status`) before a larger eval run.
- Auditing preference coverage per language/split before training.

Do not use for inventing preference labels, scoring free-form text without
dataset ranks, or evaluating code repos — there is no code here, data only.

## Prerequisites

- Python with `datasets` + `huggingface_hub`: `pip install datasets huggingface_hub`.
- Network access to HuggingFace (dataset `OpenAssistant/oasst2`).
- Hermes plugin installed (see `README.md`): symlink this directory to
  `~/.hermes/plugins/hermes-oasst2` or run `install.ps1`.
- Without the library/network, the `oasst2_*` tools still resolve but return
  `available: false` — install + connect for real rows.

## How to Run

Via tools (preferred in-session):

- `oasst2_sample` with optional `n` / `lang` / `split` / `seed` / `offset`.
- `oasst2_eval` with `message_ids` + `model_ordering` (best-first permutation).

Via CLI (operator terminal):

```bash
hermes oasst2 status
hermes oasst2 sample --n 5 --lang en --split train --seed 7
hermes oasst2 eval <id1,id2,id3> --order <id2,id1,id3> --split train
```

Via slash command: `/oasst2 status`, `/oasst2 sample`, `/oasst2 eval`
(tool-guided).

## Quick Reference

| Surface | Command | Maps to |
|---------|---------|---------|
| Tool | `oasst2_sample(n?, lang?, split?, seed?, offset?)` | Real `OpenAssistant/oasst2` rows + ranks |
| Tool | `oasst2_eval(message_ids, model_ordering, split?)` | Pairwise agreement vs human ranks |
| CLI | `hermes oasst2 sample --n 5 --lang en` | Same as `oasst2_sample` from terminal |
| CLI | `hermes oasst2 eval <ids> --order <ids>` | Same as `oasst2_eval` from terminal |
| Handoff | `handoff.curator_input` / `handoff.learning_graph` | Chosen/rejected pairs for curator |

## Procedure

1. **Check availability.** Run `oasst2_sample` with `n: 1` (or `hermes oasst2
   status`). If `available: false`, fix `datasets`/network first — do not
   proceed on invented data.
2. **Sample.** Call `oasst2_sample` (e.g. `n: 5`, `lang: "en"`,
   `split: "train"`, fixed `seed` for reproducibility). Confirm the returned
   `dataset` is `OpenAssistant/oasst2` with real `message_id`s.
3. **Rank with the model.** Order the sampled `message_id`s best-first using
   the model under test — keep it a strict permutation, no drops or extras.
4. **Eval.** Call `oasst2_eval` with `message_ids` + `model_ordering`. Read
   `pairwise_accuracy`, `agreements/total_pairs`, and per-pair `details`.
5. **Handle ties honestly.** Pairs with equal human rank carry no signal and
   are skipped in the score — that is by design, not a bug.
6. **Hand off.** Forward `handoff.curator_input.preference_pairs` to the
   Hermes curator and `handoff.learning_graph` as the reward-model style
   signal (chosen/rejected per dataset rank).
7. **Repeat per slice.** Re-sample with new `seed`/`offset` or another
   `lang`/`split` for coverage; never reuse one tiny sample as a benchmark.

## Pitfalls

- **No network means no data.** `available: false` is the honest answer —
  install `datasets` and reach HuggingFace instead of guessing ranks.
- **Eval needs a permutation.** `model_ordering` must contain exactly the
  `message_ids`, best-first — anything else returns `success: false`.
- **Missing rank signal fails loudly.** If sampled rows carry no numeric
  rank field, eval refuses rather than inventing a score.
- **Ties are skipped.** Equal-rank pairs do not count toward accuracy.
- **Samples are truncated.** `text` is capped (~1200 chars, flagged via
  `truncated`) — fetch the full row from the dataset for long contexts.
- **Shell utilities are wrapped.** Use `` `read_file` `` / `` `search_files` `` /
  `` `patch` `` / `` `terminal` `` for file work, not raw `cat`/`grep`/`sed`.
- **Upstream is archived.** Do not clone LAION-AI/Open-Assistant for code —
  the dataset is the only live artifact.

## Verification

- `hermes oasst2 status` reports `dataset: OpenAssistant/oasst2`.
- `oasst2_sample` returns rows with real `message_id` + `rank` values.
- `oasst2_eval` on a 2-id permutation returns `pairwise_accuracy` 0.0 or 1.0.
- `handoff.curator_input.preference_pairs` is consumable by the curator.
- AST check: `python -c "import ast; ast.parse(open('__init__.py').read())"`.
- Manifest check: `python -c "import yaml,sys; yaml.safe_load(open('plugin.yaml'))"`.
