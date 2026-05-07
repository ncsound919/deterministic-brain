"""Lane: live-docs-to-skill — fetch URL → TF-IDF index → emit skill.md stub."""
from __future__ import annotations
import os
import urllib.request
from typing import Dict


def run(inputs: Dict) -> Dict:
    url = inputs.get("url", "")
    if not url:
        return {"error": "No URL provided"}

    # 1. Fetch page text
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return {"error": f"Fetch failed: {exc}"}

    # 2. Strip tags naively (swap for browser-harness in production)
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()

    # 3. Chunk into 200-word segments
    words  = text.split()
    chunks = [" ".join(words[i:i+200]) for i in range(0, len(words), 200)]

    # 4. Add to TF-IDF index
    from retrieval.tfidf_search import TFIDFSearch
    existing = []
    docs_path = "retrieval/index/docs.txt"
    if os.path.exists(docs_path):
        with open(docs_path) as f:
            existing = [l.strip() for l in f if l.strip()]
    TFIDFSearch.build_index(existing + chunks)

    # 5. Emit a skill.md stub for human review
    stub = f"""---
skill: scraped-{url.split('//')[1].split('/')[0].replace('.', '-')}
version: 1.0
source_url: {url}
inputs:
  query: string
tools: [file_write]
audit: []
monte_carlo: false
---
## Step 1
# Auto-generated from {url}
# Review and complete this skill before use.
"""
    out_path = f"skill_packs/scraped/{url.split('//')[1].split('/')[0]}.skill.md"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(stub)

    return {"success": True, "chunks_indexed": len(chunks), "skill_stub": out_path}
