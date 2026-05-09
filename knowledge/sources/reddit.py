"""Reddit source ingester — supports public thread ingestion via pushshift or direct fetch.
Requires no auth for public posts when using the pushshift fallback.
With PRAW installed and REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT
env vars set, uses the official Reddit API for richer metadata.
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
import os
from typing import List

from knowledge.fragment import KnowledgeFragment, chunk_text


def ingest_reddit(url: str, tags: List[str] = None) -> List[KnowledgeFragment]:
    tags = tags or []

    praw_frags = _try_praw(url, tags)
    if praw_frags:
        return praw_frags

    return _fallback_reddit_json(url, tags)


def _try_praw(url: str, tags: List[str]) -> List[KnowledgeFragment] | None:
    try:
        import praw
    except ImportError:
        return None

    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent = os.getenv("REDDIT_USER_AGENT", "DeterministicBrain-KnowledgeBank/1.0")

    if not client_id or not client_secret:
        return None

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        submission = reddit.submission(url=url)
        title = submission.title[:200]
        subreddit = str(submission.subreddit)

        chunks = []
        if submission.selftext:
            chunks.extend(chunk_text(f"{title}\n{submission.selftext}", max_words=400))

        for comment in submission.comments.list()[:20]:
            if hasattr(comment, "body") and len(comment.body) > 100:
                chunks.append(comment.body[:800])

        if not chunks:
            chunks = [title]

        return [
            KnowledgeFragment.create(
                source_type="reddit",
                source_url=url,
                source_title=title,
                chunk_text=c,
                tags=tags + [subreddit.lower(), "reddit"],
            )
            for c in chunks
        ]
    except Exception:
        return None


def _fallback_reddit_json(url: str, tags: List[str]) -> List[KnowledgeFragment]:
    json_url = url.rstrip("/") + ".json"
    req = urllib.request.Request(json_url, headers={
        "User-Agent": "DeterministicBrain-KnowledgeBank/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return []

    try:
        post_data = data[0]["data"]["children"][0]["data"]
        title = post_data.get("title", "Reddit Post")[:200]
        selftext = post_data.get("selftext", "")
        subreddit = post_data.get("subreddit", "unknown")

        fragments = []
        if selftext:
            text = f"{title}\n{selftext}"
            for c in chunk_text(text, max_words=400):
                fragments.append(
                    KnowledgeFragment.create(
                        source_type="reddit",
                        source_url=url,
                        source_title=title,
                        chunk_text=c,
                        tags=tags + [subreddit.lower(), "reddit"],
                    )
                )

        for child in data[1]["data"]["children"][:20]:
            comment_data = child.get("data", {})
            body = comment_data.get("body", "")
            if len(body) > 100:
                fragments.append(
                    KnowledgeFragment.create(
                        source_type="reddit",
                        source_url=url,
                        source_title=f"Comment on: {title}",
                        chunk_text=body[:800],
                        tags=tags + [subreddit.lower(), "reddit"],
                    )
                )

        if not fragments:
            fragments.append(
                KnowledgeFragment.create(
                    source_type="reddit",
                    source_url=url,
                    source_title=title,
                    chunk_text=title,
                    tags=tags + [subreddit.lower(), "reddit"],
                )
            )

        return fragments
    except (IndexError, KeyError, TypeError):
        return []
