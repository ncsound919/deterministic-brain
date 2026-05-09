"""More free APIs — arXiv, Reddit, Product Hunt, Dev.to, RSS blog feeds.

All free. No API keys needed for most. Vault-aware for those that do.
"""

from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List



# ═══════════════════════════════════════════════════════════════════════
# arXiv — scientific papers (free, no key)
# ═══════════════════════════════════════════════════════════════════════

class ArxivClient:
    """arXiv API — search scientific papers. https://arxiv.org/help/api

    Free. No key. Returns Atom XML.
    """

    BASE = "http://export.arxiv.org/api/query"

    def _get(self, query: str, max_results: int = 10,
             sort_by: str = "submittedDate") -> Dict:
        params = (
            f"search_query={urllib.request.quote(query)}"
            f"&start=0&max_results={max_results}"
            f"&sortBy={sort_by}"
        )
        try:
            with urllib.request.urlopen(f"{self.BASE}?{params}", timeout=20) as r:
                root = ET.fromstring(r.read())
                ns = {
                    "atom": "http://www.w3.org/2005/Atom",
                    "arxiv": "http://arxiv.org/schemas/atom",
                }
                papers = []
                for entry in root.findall("atom:entry", ns):
                    title = entry.find("atom:title", ns)
                    summary = entry.find("atom:summary", ns)
                    link = entry.find("atom:id", ns)
                    authors = [
                        a.find("atom:name", ns).text
                        for a in entry.findall("atom:author", ns)
                    ]
                    papers.append({
                        "title": title.text.strip() if title is not None else "",
                        "summary": (summary.text.strip()[:300] if summary is not None and summary.text else ""),
                        "url": link.text.strip() if link is not None else "",
                        "authors": authors,
                    })
                return {"ok": True, "papers": papers}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def search(self, query: str, max_results: int = 10) -> Dict:
        return self._get(query, max_results)

    def latest_in(self, category: str = "cs.AI",
                  max_results: int = 10) -> Dict:
        """Latest papers in a category: cs.AI, cs.LG, cs.CL, stat.ML, etc."""
        return self._get(f"cat:{category}", max_results)


# ═══════════════════════════════════════════════════════════════════════
# Reddit — .json trick (free, no key for read-only)
# ═══════════════════════════════════════════════════════════════════════

class RedditClient:
    """Reddit — read public subreddits via .json (free, no key).
    https://www.reddit.com/r/{subreddit}/hot.json
    """

    BASE = "https://www.reddit.com"

    def _get(self, path: str, limit: int = 25) -> Dict:
        try:
            req = urllib.request.Request(
                f"{self.BASE}{path}?limit={limit}&raw_json=1",
                headers={
                    "User-Agent": "deterministic-brain/1.0 (by /u/ncsound919)",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
                posts = []
                for child in data.get("data", {}).get("children", []):
                    d = child.get("data", {})
                    posts.append({
                        "title": d.get("title", ""),
                        "author": d.get("author", ""),
                        "url": d.get("url", ""),
                        "score": d.get("score", 0),
                        "comments": d.get("num_comments", 0),
                        "subreddit": d.get("subreddit", ""),
                        "created": d.get("created_utc", 0),
                    })
                return {"ok": True, "posts": posts}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def hot(self, subreddit: str = "programming",
            limit: int = 25) -> Dict:
        return self._get(f"/r/{subreddit}/hot", limit)

    def top(self, subreddit: str = "programming",
            limit: int = 25, timeframe: str = "day") -> Dict:
        return self._get(f"/r/{subreddit}/top", limit)

    def new(self, subreddit: str = "programming",
            limit: int = 25) -> Dict:
        return self._get(f"/r/{subreddit}/new", limit)

    def search(self, query: str, subreddit: str = "all",
               limit: int = 25) -> Dict:
        try:
            req = urllib.request.Request(
                f"{self.BASE}/r/{subreddit}/search.json"
                f"?q={urllib.request.quote(query)}&limit={limit}&raw_json=1",
                headers={"User-Agent": "DeterministicBrain/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
                return {"ok": True, "data": data}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════
# Dev.to — developer articles (free, no key for read)
# ═══════════════════════════════════════════════════════════════════════

class DevToClient:
    """Dev.to API — developer articles. https://dev.to/api

    Free. No key for read. Posting needs an API key.
    """

    BASE = "https://dev.to/api"

    def _get(self, path: str, params: Dict = None) -> Dict:
        url = f"{self.BASE}{path}"
        if params:
            qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                         for k, v in params.items() if v)
            url += f"?{qs}"
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "deterministic-brain/1.0")
            with urllib.request.urlopen(req, timeout=15) as r:
                return {"ok": True, "articles": json.loads(r.read())}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def top_articles(self, tag: str = "", per_page: int = 20) -> Dict:
        params = {"per_page": per_page}
        if tag:
            params["tag"] = tag
        return self._get("/articles", params)

    def user_articles(self, username: str) -> Dict:
        return self._get(f"/articles?username={username}")

    def by_tag(self, tag: str, per_page: int = 20) -> Dict:
        return self._get("/articles", {"tag": tag, "per_page": per_page})


# ═══════════════════════════════════════════════════════════════════════
# Product Hunt — scraping (free, no key)
# ═══════════════════════════════════════════════════════════════════════

class ProductHuntClient:
    """Product Hunt — today's top products (free, no key).
    Uses the public GraphQL endpoint.
    """

    API = "https://www.producthunt.com/frontend/graphql"

    def trending(self) -> Dict:
        try:
            query = {
                "query": (
                    "query { posts(first: 10, order: RANKING) { "
                    "edges { node { id name tagline description votesCount "
                    "url website } } } }"
                ),
            }
            data = json.dumps(query).encode("utf-8")
            req = urllib.request.Request(
                self.API, data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "DeterministicBrain/1.0",
                    "Accept": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                result = json.loads(r.read())
                posts = []
                edges = result.get("data", {}).get("posts", {}).get("edges", [])
                if not edges:
                    edges = result.get("data", {}).get("posts", [])
                for item in edges:
                    n = item.get("node", item) if isinstance(item, dict) else {}
                    posts.append({
                        "name": n.get("name", ""),
                        "tagline": n.get("tagline", ""),
                        "description": (n.get("description", "") or "")[:200],
                        "votes": n.get("votesCount", 0),
                        "url": n.get("url", n.get("website", "")),
                    })
                return {"ok": True, "products": posts}
        except Exception as e:
            return {"ok": False, "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════
# Tech blog RSS feeds — curated list
# ═══════════════════════════════════════════════════════════════════════

TECH_FEEDS = {
    "hackernews": "https://hnrss.org/frontpage?count=10",
    "github_trending": "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml",
    "lobsters": "https://lobste.rs/rss",
    "arstechnica": "https://feeds.arstechnica.com/arstechnica/index",
    "techcrunch": "https://techcrunch.com/feed/",
    "wired": "https://www.wired.com/feed/rss",
    "theverge": "https://www.theverge.com/rss/index.xml",
    "mit_tech_review": "https://www.technologyreview.com/feed/",
    "dev_to": "https://dev.to/feed",
    "css_tricks": "https://css-tricks.com/feed/",
    "smashing_mag": "https://www.smashingmagazine.com/feed/",
    "realpython": "https://realpython.com/atom.xml",
    "rust_blog": "https://blog.rust-lang.org/feed.xml",
    "go_blog": "https://go.dev/blog/feed.atom",
}


class TechFeedClient:
    """Curated tech blog RSS feed aggregator."""

    def fetch(self, feeds: List[str] = None) -> Dict:
        feeds = feeds or list(TECH_FEEDS.keys())
        results = {}

        for name in feeds:
            url = TECH_FEEDS.get(name)
            if not url:
                continue
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent": "DeterministicBrain/1.0"},
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    root = ET.fromstring(r.read())
                    items = []
                    for item in root.iter("item"):
                        title = item.find("title")
                        link = item.find("link")
                        desc = item.find("description")
                        items.append({
                            "title": title.text if title is not None else "",
                            "url": link.text if link is not None else "",
                            "summary": (desc.text[:200] if desc is not None and desc.text else ""),
                        })
                    results[name] = items[:8]
            except Exception as e:
                results[name] = {"error": str(e)}

        return {"ok": True, "feeds": results, "count": sum(len(v) if isinstance(v, list) else 0 for v in results.values())}


# ═══════════════════════════════════════════════════════════════════════
# Aggregator
# ═══════════════════════════════════════════════════════════════════════

def get_tech_dashboard() -> Dict:
    """Aggregate tech news from all free sources."""
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result["hackernews"] = RedditClient().hot("programming", 5)
    except Exception as e:
        result["hackernews"] = {"error": str(e)}

    try:
        result["devto"] = DevToClient().top_articles(per_page=5)
    except Exception as e:
        result["devto"] = {"error": str(e)}

    try:
        result["producthunt"] = ProductHuntClient().trending()
    except Exception as e:
        result["producthunt"] = {"error": str(e)}

    try:
        tf = TechFeedClient()
        result["rss"] = tf.fetch(["hackernews", "github_trending", "dev_to"])
    except Exception as e:
        result["rss"] = {"error": str(e)}

    try:
        result["arxiv"] = ArxivClient().latest_in("cs.AI", 5)
    except Exception as e:
        result["arxiv"] = {"error": str(e)}

    return result
