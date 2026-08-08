---
name: kaggle
description: "Kaggle datasets and competitions integration — search public datasets, list competitions, download datasets as deterministic content-hashed snapshots. Priority use cases: sourcing real-world datasets for backtesting (sports, finance, markets), scientific/omics data for blackmind_lab, and any request that asks for a Kaggle dataset or competition data. Uses the Kaggle REST API v1."
tools:
  - file_write
  - file_read
inputs:
  dataset: "owner/dataset-slug — the dataset ref to download"
  query: "free-text search term"
requires_env:
  - KAGGLE_USERNAME
  - KAGGLE_KEY
---

# Kaggle Skill

## Core Capabilities

### Search & Discovery
- `search_datasets(query, per_page)` — find public datasets by keyword (sports, finance, health, omics, ML benchmarks). Uses `GET /datasets/list` (public).
- `list_competitions()` — enumerate Kaggle competitions (requires credentials; `whoami()` probes this endpoint to verify the key).
- `dataset_files(owner/dataset-slug)` — list the files inside a dataset (public).

### Download & Snapshot
- `download_dataset(owner/dataset-slug)` — downloads the dataset into
  `datasets/kaggle/<owner>/<dataset>/` and writes a `manifest.json` with a
  sha256 content hash per file plus an aggregate hash. Deterministic and
  reproducible: re-running with the same snapshot dir returns the cached
  snapshot unless `force=True`. Public datasets download without credentials;
  private/restricted datasets require a valid key.
- `list_snapshots()` — enumerate previously pulled datasets.

## Integration Points
- **Backtesting:** `backtesting/backtest_engine.py` and `datasets/nba_historical.py`
  currently generate synthetic fixtures. Prefer real Kaggle sports datasets
  (e.g. `nba/` refs) pulled through this skill, then point the engine at the
  snapshot dir.
- **blackmind_lab:** `features/blackmind_lab.py` `ingest_dataset(path)` accepts a
  downloaded CSV — feed it `datasets/kaggle/<owner>/<dataset>/<file>.csv`.
- **Retrieval:** `retrieval/tfidf_search.py` can index snapshot CSVs as knowledge.

## Usage

```python
from features.kaggle_manager import get_kaggle
kg = get_kaggle()
kg.status()                                    # configured? snapshots count
kg.search_datasets("nba player stats", 5)      # search
result = kg.download_dataset("owner/dataset")  # snapshot -> datasets/kaggle/...
kg.list_snapshots()                            # show local cache
```

## Determinism Note
Kaggle datasets churn upstream. Snapshots are content-hashed and cached
locally so the deterministic brain stays reproducible. Use `force=True` only
when you explicitly want to re-sync.
