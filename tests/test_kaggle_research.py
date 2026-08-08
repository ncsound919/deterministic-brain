"""Tests for the Kaggle research feed — knowledge source + feed feature."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from knowledge.sources.kaggle import ingest_kaggle_snapshot
from features.kaggle_research import KaggleResearchFeed


@pytest.fixture
def snapshot_dir(tmp_path):
    d = tmp_path / "owner" / "nba-stats"
    d.mkdir(parents=True)
    (d / "players.csv").write_text("name,team,points\nLeBron,LAL,27\nCurry,GSW,30\n", encoding="utf-8")
    (d / "notes.json").write_text(json.dumps([{"player": "LeBron", "role": "SF"}]), encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"content_hash": "x"}), encoding="utf-8")
    return d


class TestKaggleKnowledgeSource:
    def test_ingest_creates_fragments(self, snapshot_dir):
        frags = ingest_kaggle_snapshot(str(snapshot_dir), "owner/nba-stats", tags=["research"])
        assert len(frags) >= 2  # csv + json file
        assert all(f.source_type == "kaggle" for f in frags)
        assert all("owner/nba-stats" in f.source_title for f in frags)
        assert all("kaggle" in f.tags for f in frags)
        # manifest.json excluded
        assert not any("manifest.json" in f.source_title for f in frags)

    def test_ingest_missing_dir(self, tmp_path):
        assert ingest_kaggle_snapshot(str(tmp_path / "nope"), "owner/ds") == []

    def test_ingest_skips_binary(self, tmp_path):
        d = tmp_path / "binary_only"
        d.mkdir()
        (d / "data.bin").write_bytes(b"\x00\x01\x02")
        frags = ingest_kaggle_snapshot(str(d), "owner/ds")
        assert frags == []


class TestKaggleResearchFeed:
    def test_feed_dataset_flows(self, tmp_path):
        feed = KaggleResearchFeed(data_dir=str(tmp_path))
        snap = {"status": "ok", "dir": str(tmp_path / "snap"), "content_hash": "abc"}
        with patch.object(feed, "_ingest_to_bank", return_value={"status": "ok", "fragments_added": 3}) as ingest, \
             patch.object(feed, "_rebuild_tfidf", return_value={"status": "ok", "documents": 2}) as tfidf, \
             patch("features.kaggle_manager.get_kaggle") as gk:
            gk.return_value.download_dataset.return_value = snap
            result = feed.feed_dataset("owner/nba-stats", tags=["research"])
        assert result["status"] == "ok"
        assert result["knowledge_bank"]["fragments_added"] == 3
        assert result["tfidf"]["status"] == "ok"
        ingest.assert_called_once()
        tfidf.assert_called_once()

    def test_feed_dataset_download_failure(self, tmp_path):
        feed = KaggleResearchFeed(data_dir=str(tmp_path))
        with patch("features.kaggle_manager.get_kaggle") as gk:
            gk.return_value.download_dataset.return_value = {"status": "error", "error": "boom"}
            result = feed.feed_dataset("owner/ds")
        assert result["status"] == "error"

    def test_ingest_to_bank_unavailable(self, tmp_path):
        feed = KaggleResearchFeed(data_dir=str(tmp_path))
        (tmp_path / "a.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        with patch("knowledge.bank.get_knowledge_bank", side_effect=ImportError):
            res = feed._ingest_to_bank(str(tmp_path), "owner/ds", ["t"])
        assert res["fragments_created"] >= 1
        assert res["fragments_added"] == 0

    def test_list_feeds(self, tmp_path):
        feed = KaggleResearchFeed(data_dir=str(tmp_path))
        with patch("features.kaggle_manager.get_kaggle") as gk:
            gk.return_value.list_snapshots.return_value = [{"ref": "owner/ds"}]
            assert feed.list_feeds() == [{"ref": "owner/ds"}]
