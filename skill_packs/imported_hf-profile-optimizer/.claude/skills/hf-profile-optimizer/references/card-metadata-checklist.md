# Card Metadata Checklist

This file gives a practical metadata checklist and a generic YAML frontmatter example for each of the main Hugging Face card types: Model Card README, Dataset Card README, Space README, and Organization card.

Important, read before using any example below:

- Every YAML block here is a generic, illustrative example with placeholder values. It is NOT an exhaustive or authoritative field list.
- Field names, allowed values, and which fields matter change over time. Do not treat any field here as required or guaranteed.
- Before applying metadata, check the current Hugging Face documentation for the exact and up-to-date fields: the Model Cards reference, the Dataset Cards reference, and the Spaces configuration reference.
- Never invent required fields, and never present an example key as if it were certainly valid. Verify first, then apply.
- Fill placeholders only with values you can substantiate. Do not add metrics, datasets, or results you cannot back up.

## Model Card README

Checklist of metadata and sections to consider (verify current requirements in the Hugging Face Model Cards documentation):

- [ ] License field, matching any LICENSE file and the README prose
- [ ] Language field where the model is language-specific
- [ ] Library or framework field where applicable
- [ ] Tags that accurately describe task, domain, and characteristics
- [ ] A task or pipeline field where one applies
- [ ] Linked base model where the model is derived
- [ ] Linked training datasets where they are public and disclosable
- [ ] Metrics referenced in a structured field only if you can substantiate them
- [ ] An evaluation results placeholder, left empty until real numbers exist
- [ ] README body: intended use, how to load and run, training data summary, evaluation, limitations and bias, and license

Generic illustrative example only. This is NOT an exhaustive or authoritative field list. Verify every key against the current Hugging Face Model Cards documentation before use.

```yaml
---
license: apache-2.0
language:
  - en
library_name: transformers
pipeline_tag: text-classification
tags:
  - text-classification
  - example-domain
  - placeholder-tag
datasets:
  - your-username/example-dataset
metrics:
  - accuracy
  - f1
# model-index is a placeholder. Leave results empty until you have real,
# reproducible numbers. Do not invent metric values.
model-index:
  - name: example-model-name
    results: []
---
```

## Dataset Card README

Checklist of metadata and sections to consider (verify current requirements in the Hugging Face Dataset Cards documentation):

- [ ] License field, consistent with any source-data terms
- [ ] Language field where the data is language-specific
- [ ] Task categories field describing intended tasks
- [ ] Tags describing domain, format, and characteristics
- [ ] Size category field where you can state it accurately
- [ ] A configs placeholder for named configurations and splits, if used
- [ ] README body: description, schema and fields, provenance and collection method, splits, licensing and permitted use, and known limitations or biases

Generic illustrative example only. This is NOT an exhaustive or authoritative field list. Verify every key against the current Hugging Face Dataset Cards documentation before use.

```yaml
---
license: cc-by-4.0
language:
  - en
task_categories:
  - text-classification
tags:
  - example-domain
  - placeholder-tag
size_categories:
  - 10K<n<100K
# configs is a placeholder. Define real configurations, data files, and
# splits only as they actually exist in your dataset.
configs:
  - config_name: default
    data_files:
      - split: train
        path: data/train-placeholder.parquet
      - split: test
        path: data/test-placeholder.parquet
---
```

## Space README

Checklist of metadata and sections to consider (verify current requirements in the Hugging Face Spaces configuration reference):

- [ ] Title and emoji for the Space listing
- [ ] Color fields for the card gradient
- [ ] SDK field and, where relevant, the SDK version
- [ ] App entry file field
- [ ] Pinned flag if you want to feature the Space
- [ ] License field where applicable
- [ ] README body: what the demo does, how to use it, inputs and limits, and links back to the underlying model or dataset

Generic illustrative example only. This is NOT an exhaustive or authoritative field list. Verify every key against the current Hugging Face Spaces configuration reference before use.

```yaml
---
title: Example Space Title
emoji: 🤗
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: 4.0.0
app_file: app.py
pinned: false
license: apache-2.0
---
```

## Organization card

Checklist of items to consider for an organization profile card (verify current behavior in the Hugging Face organization and card documentation):

- [ ] A clear org name and short mission or focus statement
- [ ] A concise description of what the org builds and for whom
- [ ] Links to a homepage, key repos, or Collections
- [ ] A pointer to how to get in touch or report issues
- [ ] Body content that frames the featured models, datasets, and Spaces

The organization card is primarily a Markdown README that renders on the org page. It generally relies less on structured frontmatter than model, dataset, and Space cards. Do not assume a fixed set of frontmatter keys here; verify current behavior in the Hugging Face documentation before adding any.

Generic illustrative example only. This is NOT an exhaustive or authoritative field list, and org-card frontmatter support may differ from repo cards. Verify against the current Hugging Face documentation before use.

```yaml
---
# Illustrative placeholders only. Confirm which keys, if any, an
# organization card supports in the current Hugging Face documentation
# before relying on frontmatter here.
title: Example Organization
emoji: 🏷️
colorFrom: indigo
colorTo: purple
---
```

Body content for the organization card (Markdown after the frontmatter) typically carries the real value: a one-line positioning statement, a short description of the org's focus, and links to flagship repos and Collections. Keep every claim truthful and verifiable, and never store or expose a Hugging Face token in a card. If authenticated tooling is needed, rely only on the optional HF_TOKEN environment variable and never write it into any file.
