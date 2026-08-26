# Bio and Positioning Templates

> All assets in this file are ENGLISH (Kaggle-facing). Keep them honest and specific: name the domain, the tools, and a real result only when the user provides one. No vague "passionate about data" filler. Never claim guaranteed medals, upvotes, or ranking. Use `[result if available]` and omit the clause entirely when no result exists. Bios are inside fenced code blocks so they copy cleanly.

---

## Short Kaggle bio
> One or two lines. Lead with what you do and the domain, not with adjectives.

```
[role] working on [domain] with [tools]. Publishing notebooks on [topic/method]; [dataset or competition focus if any].
```

Example 1:
```
ML practitioner focused on tabular credit-risk modeling with Python, XGBoost, and scikit-learn. Publishing reproducible notebooks on feature engineering and validation.
```

Example 2:
```
NLP engineer working on multilingual text classification with Hugging Face Transformers and PyTorch. Sharing datasets and baselines for low-resource languages.
```

---

## Recruiter-oriented bio
> For hiring visibility. State role, stack, and one verifiable outcome. Keep it scannable.

```
[role] specializing in [domain]. Stack: [tools]. [One concrete project or result if available]. Open to [type of role / collaboration].
```

Example:
```
Data scientist specializing in demand forecasting for retail. Stack: Python, LightGBM, Prophet, SQL. Built and documented an end-to-end forecasting notebook covering data prep, backtesting, and error analysis. Open to full-time DS roles.
```

---

## Research-oriented bio
> For an academic or applied-research audience. Emphasize methods, reproducibility, and topics of interest.

```
Researching [problem area] using [methods/models]. Interested in [subfield]. Notebooks emphasize reproducibility and clear ablations; [publication or preprint if available].
```

Example:
```
Researching uncertainty estimation in medical imaging using Bayesian deep learning and conformal prediction. Interested in calibration under distribution shift. Notebooks emphasize reproducibility and clear ablations.
```

---

## ML-engineer-oriented bio
> For an engineering audience. Emphasize systems, pipelines, and production concerns over leaderboard scores.

```
ML engineer building [type of pipeline/system] with [tools/frameworks]. Focus on [reproducibility / serving / data pipelines / MLOps]. Notebooks show [what: end-to-end workflow, benchmarking, tooling].
```

Example:
```
ML engineer building training and inference pipelines with PyTorch, ONNX, and Docker. Focus on reproducibility and efficient inference. Notebooks show end-to-end workflows from data loading to exported, benchmarked models.
```

---

## Tagline
> One line, under ~90 characters. Concrete over clever. Domain plus one distinctive angle.

```
[domain] + [distinctive angle or method]
```

Examples:
```
Tabular ML for credit risk, with reproducible validation notebooks
```
```
Low-resource NLP: datasets and baselines you can actually rerun
```

---

## Specialization summary
> Two or three sentences that a reader remembers. What you do, for whom, and how your work differs.

```
I work on [specialization] for [audience/use case]. My notebooks and datasets focus on [distinctive method or standard: reproducibility, documentation, error analysis]. [What a reader can reuse from my work.]
```

Example:
```
I work on time-series forecasting for retail and energy demand. My notebooks focus on honest backtesting and error analysis rather than single leaderboard scores. Each one ships with clear data prep and a rerunnable pipeline you can adapt.
```

---

## Notebook introduction sentence
> The first sentence of a notebook. State the goal and the dataset in plain terms; set expectations, no hype.

```
This notebook [does what] on [dataset], covering [key steps]; the goal is [clear objective, e.g. a reproducible baseline for X].
```

Example:
```
This notebook builds a reproducible baseline for store-level sales forecasting on the M5 dataset, covering data prep, feature engineering, backtesting, and error analysis; the goal is a pipeline you can adapt to your own retail data.
```

---

## Dataset description
> Explain what the data is, where it came from, its shape, and a realistic use. Note licensing and known limitations honestly.

```
[What the dataset contains] collected from [source/method]. [Rows/columns/coverage if available]. Useful for [tasks]. License: [license]. Known limitations: [gaps, biases, missing fields].
```

Example:
```
Daily air-quality readings (PM2.5, PM10, NO2) collected from public municipal sensors across 12 cities. Roughly 2 years of hourly records with occasional gaps. Useful for time-series forecasting and anomaly detection. License: CC BY 4.0. Known limitations: sensor downtime creates missing intervals; coverage is uneven between cities.
```

---

## Short LinkedIn pitch that includes Kaggle
> One paragraph linking your Kaggle work to your professional profile. Point to specific work; keep the tone factual.

```
I share my [domain] work publicly on Kaggle: [notebooks / datasets / competition work] focused on [topic]. [One concrete example or result if available.] It is where I keep my applied work reproducible and open. Profile: [Kaggle URL].
```

Example:
```
I share my applied ML work publicly on Kaggle: reproducible notebooks and datasets focused on retail demand forecasting. My most recent notebook walks through an end-to-end forecasting pipeline with honest backtesting. It is where I keep my applied work reproducible and open. Profile: [Kaggle URL].
```
