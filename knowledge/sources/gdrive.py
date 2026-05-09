from __future__ import annotations
import re
import urllib.request
import os
from typing import List

from knowledge.fragment import KnowledgeFragment, chunk_text


def ingest_gdrive(url: str, tags: List[str] = None) -> List[KnowledgeFragment]:
    tags = tags or []

    gdoc_match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', url)
    file_match = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    open_match = re.search(r'id=([a-zA-Z0-9_-]+)', url)

    if gdoc_match:
        return _ingest_gdoc(gdoc_match.group(1), url, tags)
    elif file_match:
        return _ingest_gdrive_file(file_match.group(1), url, tags)
    elif open_match:
        return _ingest_gdrive_file(open_match.group(1), url, tags)
    else:
        return _ingest_gdrive_file(url, url, tags)


def _ingest_gdoc(doc_id: str, original_url: str, tags: List[str]) -> List[KnowledgeFragment]:
    export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
    req = urllib.request.Request(export_url, headers={
        "User-Agent": "DeterministicBrain-KnowledgeBank/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    if not text.strip():
        return []

    lines = text.splitlines()
    title = "Google Doc"
    if lines:
        heading = lines[0].strip()
        if heading and len(heading) < 200:
            title = heading

    chunks = chunk_text(text, max_words=400)
    return [
        KnowledgeFragment.create(
            source_type="gdrive",
            source_url=original_url,
            source_title=title,
            chunk_text=c,
            tags=tags,
        )
        for c in chunks
    ]


def _ingest_gdrive_file(file_id: str, original_url: str, tags: List[str]) -> List[KnowledgeFragment]:
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    req = urllib.request.Request(download_url, headers={
        "User-Agent": "DeterministicBrain-KnowledgeBank/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
    except Exception:
        return []

    title = original_url.split("/")[-1] or "Google Drive File"

    if "pdf" in content_type.lower():
        return _extract_pdf(data, original_url, title, tags)

    try:
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        return []

    chunks = chunk_text(text, max_words=400)
    return [
        KnowledgeFragment.create(
            source_type="gdrive",
            source_url=original_url,
            source_title=title,
            chunk_text=c,
            tags=tags,
        )
        for c in chunks
    ]


def _extract_pdf(pdf_bytes: bytes, url: str, title: str, tags: List[str]) -> List[KnowledgeFragment]:
    try:
        from pdfminer.high_level import extract_text
        import io
        text = extract_text(io.BytesIO(pdf_bytes))
    except ImportError:
        try:
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                tf.write(pdf_bytes)
                tf_path = tf.name
            result = subprocess.run(
                ["pdftotext", tf_path, "-"],
                capture_output=True, text=True, timeout=30
            )
            os.unlink(tf_path)
            text = result.stdout
        except Exception:
            return []

    if not text.strip():
        return []

    chunks = chunk_text(text, max_words=400)
    return [
        KnowledgeFragment.create(
            source_type="gdrive",
            source_url=url,
            source_title=title,
            chunk_text=c,
            tags=tags,
        )
        for c in chunks
    ]
