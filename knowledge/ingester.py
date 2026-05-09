from __future__ import annotations
import logging
from typing import List

from knowledge.fragment import KnowledgeFragment, chunk_text
from knowledge.sources.web import ingest_web_url
from knowledge.sources.gdrive import ingest_gdrive
from knowledge.sources.github_docs import ingest_github
from knowledge.sources.reddit import ingest_reddit

logger = logging.getLogger(__name__)


class KnowledgeIngester:

    def ingest_url(self, url: str, tags: List[str] = None) -> List[KnowledgeFragment]:
        tags = tags or []
        url_lower = url.lower()
        try:
            if "drive.google.com" in url_lower or "docs.google.com" in url_lower:
                return ingest_gdrive(url, tags)
            elif "github.com" in url_lower:
                return ingest_github(url, tags)
            elif "reddit.com" in url_lower:
                return ingest_reddit(url, tags)
            else:
                return ingest_web_url(url, tags)
        except Exception as e:
            logger.error(f"Ingest failed for {url}: {e}")
            return []

    def ingest_text(self, text: str, title: str, tags: List[str] = None) -> List[KnowledgeFragment]:
        tags = tags or []
        chunks = chunk_text(text, max_words=400)
        return [
            KnowledgeFragment.create(
                source_type="manual",
                source_url=f"manual://{title.replace(' ', '-')}",
                source_title=title,
                chunk_text=c,
                tags=tags,
            )
            for c in chunks
        ]

    def ingest_github_repo(self, owner: str, repo: str, tags: List[str] = None) -> List[KnowledgeFragment]:
        url = f"https://github.com/{owner}/{repo}"
        return ingest_github(url, tags or [])

    def ingest_reddit_post(self, url: str, tags: List[str] = None) -> List[KnowledgeFragment]:
        return ingest_reddit(url, tags or [])


_INGESTER: KnowledgeIngester | None = None


def get_ingester() -> KnowledgeIngester:
    global _INGESTER
    if _INGESTER is None:
        _INGESTER = KnowledgeIngester()
    return _INGESTER
