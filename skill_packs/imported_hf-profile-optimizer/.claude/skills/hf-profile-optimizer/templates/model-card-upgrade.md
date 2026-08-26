# Model Card Upgrade (README template)

> This is a Hub asset: the card content is English. Fill only what is supported by real evidence. Use "More Information Needed" where a value is genuinely unknown, and "[needs evidence]" where a claim would need a source. Never fabricate downloads, benchmark numbers, or affiliations.

## YAML frontmatter

> Note: verify the current Hugging Face model-card documentation for the exact accepted fields and their spelling before publishing; field names and allowed values change over time. Placeholders below are a starting point, not an authoritative schema.

```yaml
---
license: [license identifier, e.g. apache-2.0]
language:
  - [language code, e.g. en]
library_name: [library, e.g. transformers]
tags:
  - [tag]
  - [tag]
pipeline_tag: [pipeline tag, e.g. text-classification]
datasets:
  - [dataset id]
metrics:
  - [metric name]
model-index:
  - name: [model name]
    results: [] # More Information Needed - fill only with real, cited results
---
```

## Model summary
> One paragraph: what the model does, its architecture family, and who it is for.

[Model summary]

## Intended use
> The tasks and contexts this model is designed for.

[Intended use]

## Out-of-scope use
> Uses this model is not suitable for or must not be used for.

[Out-of-scope use]

## How to use
> Minimal, runnable snippet for loading and inference. Keep it copy-paste ready.

```python
# [loading and inference snippet placeholder]
```

## Inputs/outputs
> Describe the expected input format and the output format the model returns.

[Inputs and outputs]

## Training data
> The data the model was trained on, with sources and licenses where known.

[Training data]

## Training procedure
> Key training details: objective, hyperparameters, hardware, and duration where known.

[Training procedure]

## Evaluation
> Report metrics only with real, cited results; otherwise leave the marker in place.

[metric: needs evidence]

## Limitations
> Known failure modes, scope limits, and conditions under which quality degrades.

[Limitations]

## Bias, risks and ethical considerations
> Documented biases, foreseeable harms, and mitigations or usage cautions.

[Bias, risks and ethical considerations]

## Citation
> How to cite this model. Use "More Information Needed" if no citation exists yet.

```bibtex
[citation placeholder]
```

## License
> Restate the license and any usage terms a user must accept.

[License]

## Contact
> Where to reach the maintainer for questions, issues, or reporting misuse.

[Contact]
