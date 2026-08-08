from __future__ import annotations
"""Kaggle knowledge source — ingest a downloaded dataset snapshot into the
knowledge bank as searchable fragments (CSV/TSV/JSON/JSONL/TXT/MD)."""

import json
import logging
import os
import csv
from typing import List

from knowledge.fragment import KnowledgeFragment, chunk_text

logger = logging.getLogger(__name__)

_DATA_EXTS = {".csv", ".tsv", ".json", ".jsonl", ".txt", ".md", ".log", ".tsv"}


def ingest_kaggle_snapshot(snapshot_dir: str, ref: str,
                           tags: List[str] = None) -> List[KnowledgeFragment]:
    """Read every data file under a Kaggle snapshot dir and produce fragments.

    Fragments are chunked deterministically (no LLM). Files that cannot be
    parsed (binary, images, etc.) are skipped. The snapshot's manifest.json
    (if present) is excluded from content.
    """
    tags = tags or []
    base_tags = ["kaggle"] + tags
    fragments: List[KnowledgeFragment] = []

    if not os.path.isdir(snapshot_dir):
        return fragments

    for root, _dirs, files in os.walk(snapshot_dir):
        for name in sorted(files):
            if name == "manifest.json":
                continue
            path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext not in _DATA_EXTS:
                continue
            rel = os.path.relpath(path, snapshot_dir)
            title = f"{ref}/{rel}"
            url = f"kaggle://{ref}/{rel}"
            try:
                text = _file_to_text(path, ext)
            except Exception as e:
                logger.warning("Kaggle source: skipped %s: %s", rel, e)
                continue
            if not text or not text.strip():
                continue
            chunks = chunk_text(text, max_words=400)
            for c in chunks:
                fragments.append(KnowledgeFragment.create(
                    source_type="kaggle",
                    source_url=url,
                    source_title=title,
                    chunk_text=c,
                    tags=base_tags + [ref],
                ))

    return fragments


def _file_to_text(path: str, ext: str) -> str:
    if ext in (".csv", ".tsv"):
        return _csv_to_text(path, delimiter="," if ext == ".csv" else "\t")
    if ext in (".json", ".jsonl"):
        return _json_to_text(path)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _csv_to_text(path: str, delimiter: str = ",") -> str:
    lines = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f, delimiter=delimiter)
        for row in reader:
            if row:
                lines.append(" | ".join(cell.strip() for cell in row if cell.strip()))
    return "\n".join(lines)


def _json_to_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read().strip()
    records = []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Try JSONL: one object per line
        lines = [ln for ln in content.splitlines() if ln.strip()]
        for ln in lines:
            try:
                records.append(json.loads(ln))
            except json.JSONDecodeError:
                records.append(ln)
        return _json_records_to_text(records)

    if isinstance(data, list):
        return _json_records_to_text(data)
    if isinstance(data, dict):
        return _json_records_to_text([data])
    return str(data)


def _json_records_to_text(records: List) -> str:
    lines = []
    for rec in records:
        if isinstance(rec, dict):
            lines.append("; ".join(f"{k}: {v}" for k, v in rec.items()))
        else:
            lines.append(str(rec))
    return "\n".join(lines)
