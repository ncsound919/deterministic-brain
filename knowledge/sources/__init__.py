from knowledge.sources.web import ingest_web_url
from knowledge.sources.gdrive import ingest_gdrive
from knowledge.sources.github_docs import ingest_github
from knowledge.sources.reddit import ingest_reddit
from knowledge.sources.discord import ingest_discord_channel

__all__ = [
    "ingest_web_url",
    "ingest_gdrive",
    "ingest_github",
    "ingest_reddit",
    "ingest_discord_channel",
]
