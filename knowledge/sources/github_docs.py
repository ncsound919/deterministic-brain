from __future__ import annotations
from typing import List
from knowledge.fragment import KnowledgeFragment, chunk_text


def ingest_github(url: str, tags: List[str] = None) -> List[KnowledgeFragment]:
    tags = tags or []
    fragments = []

    parts = url.rstrip("/").split("/")
    owner = None
    repo = None
    for i, p in enumerate(parts):
        if p == "github.com" and i + 2 < len(parts):
            owner = parts[i + 1]
            repo = parts[i + 2]
            break

    if not owner or not repo:
        return _fetch_raw_url(url, tags)

    fragments.extend(_fetch_readme(owner, repo, url, tags))
    fragments.extend(_fetch_wiki(owner, repo, url, tags))
    fragments.extend(_fetch_issues_summary(owner, repo, url, tags))

    return fragments


def _fetch_readme(owner: str, repo: str, source_url: str, tags: List[str]) -> List[KnowledgeFragment]:
    readme_urls = [
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/readme.md",
        f"https://raw.githubusercontent.com/{owner}/{repo}/master/readme.md",
    ]
    import urllib.request
    for rurl in readme_urls:
        try:
            req = urllib.request.Request(rurl, headers={
                "User-Agent": "DeterministicBrain-KnowledgeBank/1.0",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
        except Exception:
            continue

        title = f"{owner}/{repo} README"
        chunks = chunk_text(text, max_words=400)
        return [
            KnowledgeFragment.create(
                source_type="github",
                source_url=source_url,
                source_title=title,
                chunk_text=c,
                tags=tags + [repo.lower(), owner.lower()],
            )
            for c in chunks
        ]
    return []


def _fetch_wiki(owner: str, repo: str, source_url: str, tags: List[str]) -> List[KnowledgeFragment]:
    wiki_urls = [
        f"https://raw.githubusercontent.com/{owner}/{repo}/main/Home.md",
        f"https://raw.githubusercontent.com/wiki/{owner}/{repo}/Home.md",
    ]
    import urllib.request
    for wurl in wiki_urls:
        try:
            req = urllib.request.Request(wurl, headers={
                "User-Agent": "DeterministicBrain-KnowledgeBank/1.0",
            })
            with urllib.request.urlopen(req, timeout=15) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
        except Exception:
            continue

        title = f"{owner}/{repo} Wiki"
        chunks = chunk_text(text, max_words=400)
        return [
            KnowledgeFragment.create(
                source_type="github",
                source_url=wurl,
                source_title=title,
                chunk_text=c,
                tags=tags + [repo.lower(), owner.lower()],
            )
            for c in chunks
        ]
    return []


def _fetch_issues_summary(owner: str, repo: str, source_url: str, tags: List[str]) -> List[KnowledgeFragment]:
    import urllib.request
    import json
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=all&per_page=10&sort=updated"
    try:
        req = urllib.request.Request(api_url, headers={
            "User-Agent": "DeterministicBrain-KnowledgeBank/1.0",
            "Accept": "application/vnd.github.v3+json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []

    fragments = []
    for issue in data[:10]:
        title = f"{owner}/{repo} Issue: {issue.get('title', '')}"
        body = issue.get("body", "") or ""
        if not body.strip():
            continue
        chunks = chunk_text(body, max_words=400)
        for c in chunks:
            fragments.append(
                KnowledgeFragment.create(
                    source_type="github",
                    source_url=issue.get("html_url", source_url),
                    source_title=title,
                    chunk_text=c,
                    tags=tags + [repo.lower(), owner.lower()],
                )
            )
    return fragments


def _fetch_raw_url(url: str, tags: List[str]) -> List[KnowledgeFragment]:
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "DeterministicBrain-KnowledgeBank/1.0",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    title = url.split("/")[-1] or "GitHub Raw"
    chunks = chunk_text(text, max_words=400)
    return [
        KnowledgeFragment.create(
            source_type="github",
            source_url=url,
            source_title=title,
            chunk_text=c,
            tags=tags,
        )
        for c in chunks
    ]
