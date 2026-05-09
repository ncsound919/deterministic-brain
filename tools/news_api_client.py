"""News API clients — NewsAPI.org, GNews, World News API.

Uses the credential vault for API keys. Falls back gracefully to RSS when
no API key is configured.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List

from tools.vault_aware_api import get_key


class NewsAPIClient:
    """NewsAPI.org — headlines, search, sources. https://newsapi.org

    Free tier: 100 req/day, headlines + everything endpoint.
    """

    BASE = "https://newsapi.org/v2"

    def __init__(self, api_key: str = ""):
        self.key = get_key(
            vault_category="newsapi", vault_key="api_key",
            env_var="NEWSAPI_KEY", explicit=api_key,
        )

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        params = params or {}
        params["apiKey"] = self.key
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                      for k, v in params.items() if v)
        url = f"{self.BASE}/{endpoint}?{qs}"
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return json.loads(r.read())
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def top_headlines(self, country: str = "us", category: str = "",
                      q: str = "", page_size: int = 10) -> Dict:
        params = {"country": country, "pageSize": page_size}
        if category:
            params["category"] = category
        if q:
            params["q"] = q
        return self._get("top-headlines", params)

    def everything(self, q: str, from_date: str = "",
                   to_date: str = "", language: str = "en",
                   sort_by: str = "publishedAt", page_size: int = 10) -> Dict:
        params = {"q": q, "language": language, "sortBy": sort_by,
                  "pageSize": page_size}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return self._get("everything", params)

    def sources(self, category: str = "", language: str = "en",
                country: str = "") -> Dict:
        params = {}
        if category:
            params["category"] = category
        if language:
            params["language"] = language
        if country:
            params["country"] = country
        return self._get("top-headlines/sources", params)


class GNewsClient:
    """GNews API — Google News search. https://gnews.io

    Free tier: 100 req/day, up to 10 articles per request.
    """

    BASE = "https://gnews.io/api/v4"

    def __init__(self, api_key: str = ""):
        self.key = get_key(
            vault_category="gnews", vault_key="api_key",
            env_var="GNEWS_API_KEY", explicit=api_key,
        )

    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        params = params or {}
        params["apikey"] = self.key
        qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                      for k, v in params.items() if v)
        url = f"{self.BASE}/{endpoint}?{qs}"
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return json.loads(r.read())
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def top_headlines(self, category: str = "general",
                      country: str = "us", lang: str = "en",
                      max_results: int = 10) -> Dict:
        return self._get("top-headlines", {
            "category": category, "country": country,
            "lang": lang, "max": max_results,
        })

    def search(self, q: str, lang: str = "en", country: str = "us",
               max_results: int = 10, from_date: str = "",
               to_date: str = "") -> Dict:
        params = {"q": q, "lang": lang, "country": country,
                  "max": max_results}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return self._get("search", params)


class WorldNewsClient:
    """World News API — multilingual news. https://worldnewsapi.com

    Free tier: 50 req/day, 100/day on paid.
    """

    BASE = "https://api.worldnewsapi.com"

    def __init__(self, api_key: str = ""):
        self.key = get_key(
            vault_category="worldnews", vault_key="api_key",
            env_var="WORLDNEWS_API_KEY", explicit=api_key,
        )

    def _get(self, path: str, params: Dict = None) -> Dict:
        url = f"{self.BASE}{path}"
        if params:
            qs = "&".join(f"{k}={urllib.request.quote(str(v))}"
                          for k, v in params.items() if v)
            url += f"?{qs}"
        req = urllib.request.Request(url)
        if self.key:
            req.add_header("x-api-key", self.key)
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def search_news(self, text: str = "", source_countries: str = "us",
                    language: str = "en", number: int = 10) -> Dict:
        return self._get("/search-news", {
            "text": text, "source-countries": source_countries,
            "language": language, "number": number,
        })


def get_news(providers: List[str] = None) -> Dict:
    """Unified news fetch — tries NewsAPI → GNews → WorldNews → RSS fallback.

    Returns a dict with headlines from all working providers.
    """
    providers = providers or ["newsapi", "gnews", "worldnews", "rss"]
    result = {"providers": {}, "timestamp": datetime.now(timezone.utc).isoformat()}

    for provider in providers:
        try:
            if provider == "newsapi":
                n = NewsAPIClient()
                if n.key:
                    result["providers"]["newsapi"] = n.top_headlines("us", page_size=8)
            elif provider == "gnews":
                g = GNewsClient()
                if g.key:
                    result["providers"]["gnews"] = g.top_headlines(max_results=8)
            elif provider == "worldnews":
                w = WorldNewsClient()
                if w.key:
                    result["providers"]["worldnews"] = w.search_news(language="en", number=8)
            elif provider == "rss":
                result["providers"]["rss"] = _fetch_rss_fallback()
        except Exception as e:
            result["providers"][provider] = {"error": str(e)}

    return result


def _fetch_rss_fallback() -> List[Dict]:
    """Fallback to RSS feeds when no API key is configured."""
    feeds = [
        "https://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
        "https://feeds.npr.org/1001/rss.xml",
    ]
    articles = []
    for url in feeds:
        try:
            import xml.etree.ElementTree as ET
            with urllib.request.urlopen(url, timeout=10) as r:
                root = ET.fromstring(r.read())
                for item in root.iter("item"):
                    title = item.find("title")
                    desc = item.find("description")
                    link = item.find("link")
                    articles.append({
                        "title": title.text if title is not None else "",
                        "description": (desc.text[:200] if desc is not None and desc.text else ""),
                        "url": link.text if link is not None else "",
                        "source": url.split("/")[2],
                    })
                if articles:
                    break
        except Exception:
            continue
    return articles[:15]
