from __future__ import annotations
"""
WEB_BROWSER_TOOL — In-process web browser tool.

Exposes a simplified browser interface that the brain can call as a tool:
- fetch(url)        : GET a page and return its text content
- search(query)     : Web search via Tavily
- screenshot(url)   : Capture a page screenshot (requires Playwright)
- extract_links(url): Return all hrefs from a page

This is distinct from the agent_brain lane's full browser automation;
this is a lightweight read-only tool available to all lanes.
"""
import os
from typing import Any

try:
    import httpx
    _HTTPX_OK = True
except ImportError:
    _HTTPX_OK = False


def fetch(url: str, timeout: int = 10) -> dict:
    if not _HTTPX_OK:
        return {'error': 'httpx not installed. pip install httpx'}
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={'User-Agent': 'deterministic-brain/1.0'})
        return {'url': url, 'status': resp.status_code, 'text': resp.text[:10000]}
    except Exception as exc:
        return {'url': url, 'error': str(exc)}


def search(query: str, max_results: int = 5) -> dict:
    key = os.getenv('TAVILY_API_KEY', '')
    if not key:
        return {'error': 'TAVILY_API_KEY not set'}
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=key)
        results = client.search(query, max_results=max_results)
        return {'query': query, 'results': results.get('results', [])}
    except Exception as exc:
        return {'query': query, 'error': str(exc)}


def extract_links(url: str) -> dict:
    page = fetch(url)
    if 'error' in page:
        return page
    import re
    links = re.findall(r'href=["\']([^"\']+)["\']', page['text'])
    return {'url': url, 'links': list(set(links))[:50]}


def screenshot(url: str) -> dict:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=15000)
            data = page.screenshot(type='png')
            browser.close()
        return {'url': url, 'bytes': len(data), 'format': 'png'}
    except Exception as exc:
        return {'url': url, 'error': str(exc)}
