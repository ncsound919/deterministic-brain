"""News aggregator — RSS feeds + keyword extraction for cron-based intelligence.

Feeds the brain's reasoning engine with real-time headlines.
KAIROS cron: fetch every 30min, emit news_pulse event on bus.

Token savings: ~600 tokens saved per news summarization vs LLM.
"""

from __future__ import annotations
import json
import re
import time
from typing import Dict, List
from urllib.request import urlopen, Request


# Curated high-signal RSS sources
RSS_SOURCES = {
    "tech": [
        "https://feeds.feedburner.com/TechCrunch",
        "https://www.theverge.com/rss/index.xml",
    ],
    "crypto": [
        "https://cointelegraph.com/rss",
        "https://bitcoinmagazine.com/.rss/full/",
    ],
    "sports": [
        "https://www.espn.com/espn/rss/news",
    ],
    "finance": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC,^DJI,^IXIC",
    ],
    "ai": [
        "https://arxiv.org/rss/cs.AI",
        "https://news.ycombinator.com/rss",
    ],
}


class NewsAggregator:
    """Fetch headlines from RSS sources, extract keywords, feed the brain."""

    def fetch_all(self) -> Dict:
        headlines = []
        for category, urls in RSS_SOURCES.items():
            for url in urls:
                try:
                    items = self._parse_rss(url)
                    for item in items[:5]:
                        headlines.append({
                            "category": category,
                            "title": item.get("title", ""),
                            "link": item.get("link", ""),
                            "source": url.split("/")[2],
                            "keywords": self._extract_keywords(item.get("title", "")),
                        })
                except Exception:
                    continue
        return {
            "headlines": headlines,
            "count": len(headlines),
            "categories": list(set(h["category"] for h in headlines)),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def _parse_rss(self, url: str) -> List[Dict]:
        req = Request(url, headers={"User-Agent": "deterministic-brain/2.5"})
        with urlopen(req, timeout=15) as resp:
            content = resp.read().decode("utf-8", errors="replace")

        items = []
        # Extract <item> blocks from RSS XML
        for match in re.finditer(
            r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?</item>",
            content, re.DOTALL,
        ):
            items.append({"title": match.group(1).strip(), "link": match.group(2).strip()})
        return items

    def _extract_keywords(self, text: str) -> List[str]:
        stop = {"the", "a", "an", "is", "are", "was", "were", "in", "of",
                "to", "and", "or", "for", "with", "on", "at", "by", "this",
                "that", "it", "as", "be", "not", "from", "into", "its"}
        words = re.findall(r"[A-Z][a-z]{2,}|\b[a-z]{4,}\b", text)
        return list(set(w.lower() for w in words if w.lower() not in stop))[:8]


def fetch_news() -> Dict:
    """Convenience function for tool registry."""
    return NewsAggregator().fetch_all()
