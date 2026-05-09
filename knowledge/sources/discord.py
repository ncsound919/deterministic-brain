"""Discord source ingester — read-only message history from accessible channels.
Requires DISCORD_BOT_TOKEN env var and a bot with 'Read Message History' permission
in the target server.
"""
from __future__ import annotations
import os
import asyncio
import time
from typing import List

from knowledge.fragment import KnowledgeFragment, chunk_text


def ingest_discord_channel(channel_id: int, limit: int = 100, tags: List[str] = None) -> List[KnowledgeFragment]:
    tags = tags or []
    token = os.getenv("DISCORD_BOT_TOKEN", "")

    if not token:
        return []

    try:
        return asyncio.run(_fetch_discord_messages(token, channel_id, limit, tags))
    except Exception:
        return []


async def _fetch_discord_messages(token: str, channel_id: int, limit: int,
                                   tags: List[str]) -> List[KnowledgeFragment]:
    try:
        import discord
    except ImportError:
        return _fetch_discord_rest(token, channel_id, limit, tags)

    intents = discord.Intents.default()
    intents.message_content = True

    messages = []
    last = None

    class _Bot(discord.Client):
        async def on_ready(self_):
            nonlocal messages, last
            try:
                channel = self_.get_channel(channel_id)
                if channel is None:
                    channel = await self_.fetch_channel(channel_id)
                async for msg in channel.history(limit=limit):
                    if len(msg.content) > 50:
                        messages.append(msg.content)
                    last = msg.id
            except Exception:
                pass
            await self_.close()

    bot = _Bot(intents=intents)
    try:
        await bot.start(token)
    except Exception:
        pass

    fragments = []
    for i, msg in enumerate(messages):
        fragment_id = f"discord-{last}-{i}" if last else f"discord-{channel_id}-{i}"
        fragments.append(
            KnowledgeFragment.create(
                source_type="discord",
                source_url=f"discord://channel/{channel_id}",
                source_title=f"Discord Channel #{channel_id} Message {i + 1}",
                chunk_text=msg[:800],
                tags=tags + ["discord"],
            )
        )
    return fragments


def _fetch_discord_rest(token: str, channel_id: int, limit: int,
                         tags: List[str]) -> List[KnowledgeFragment]:
    import urllib.request
    import json

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={min(limit, 100)}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bot {token}",
        "User-Agent": "DeterministicBrain-KnowledgeBank/1.0",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []

    fragments = []
    for msg in data:
        content = msg.get("content", "")
        if len(content) < 50:
            continue
        fragments.append(
            KnowledgeFragment.create(
                source_type="discord",
                source_url=f"discord://channel/{channel_id}",
                source_title=f"Discord #{channel_id}",
                chunk_text=content[:800],
                tags=tags + ["discord"],
            )
        )
    return fragments
