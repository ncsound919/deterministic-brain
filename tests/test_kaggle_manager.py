"""Tests for the Kaggle manager — search, snapshots, determinism."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from features.kaggle_manager import KaggleDataset, KaggleManager


@pytest.fixture
def kg(tmp_path):
    return KaggleManager(username="tester", api_key="key123", data_dir=str(tmp_path / "kaggle"))


class TestConfig:
    def test_configured(self, kg):
        assert kg.configured is True

    def test_not_configured(self):
        kg = KaggleManager(username="", api_key="")
        assert kg.configured is False
        assert kg.whoami()["configured"] is False

    def test_whoami_probes_competitions(self, kg):
        with patch.object(kg, "_api", return_value=[{"id": 1, "competitionName": "x"}]):
            who = kg.whoami()
            assert who["configured"] is True
            assert who["authenticated"] is True
            assert who["competitions"] == 1

    def test_whoami_reports_error(self, kg):
        with patch.object(kg, "_api", return_value={"error": "HTTP 401"}):
            who = kg.whoami()
            assert who["configured"] is True
            assert "error" in who
            assert who.get("authenticated") is None

    def test_status_ok_flag(self, kg):
        with patch.object(kg, "_api", return_value=[]):
            st = kg.status()
            assert st["ok"] is True
            assert st["authenticated"] is True


class TestSearch:
    def test_search_datasets_parses_plain_array(self, kg):
        payload = [
            {
                "ref": "owner/nba-stats",
                "title": "NBA Stats",
                "subtitle": "player box scores",
                "totalBytes": 1000,
                "downloadCount": 10,
                "licenseName": "CC0-1.0",
                "tags": [{"nameNullable": "sports"}],
                "lastUpdated": "2026-01-01",
            }
        ]
        with patch.object(kg, "_api", return_value=payload) as api:
            results = kg.search_datasets("nba", 5)
            assert len(results) == 1
            r = results[0]
            assert isinstance(r, KaggleDataset)
            assert r.ref == "owner/nba-stats"
            assert r.title == "NBA Stats"
            assert r.tags == ["sports"]
            assert r.total_bytes == 1000
            assert r.total_downloads == 10
            api.assert_called_once()
            assert api.call_args[1]["params"]["search"] == "nba"
            assert api.call_args[1]["params"]["pageSize"] == 5

    def test_search_error_returns_empty(self, kg):
        with patch.object(kg, "_api", return_value={"error": "HTTP 403"}):
            assert kg.search_datasets("nba") == []

    def test_list_competitions(self, kg):
        with patch.object(kg, "_api", return_value=[{"id": 1, "competitionName": "playground", "reward": 0}]):
            comps = kg.list_competitions()
            assert comps[0]["name"] == "playground"

    def test_dataset_files(self, kg):
        payload = {"datasetFiles": [{"name": "data.csv", "totalBytes": 5, "fileType": "csv"}]}
        with patch.object(kg, "_api", return_value=payload):
            files = kg.dataset_files("owner/nba-stats")
            assert files[0]["name"] == "data.csv"
            assert files[0]["total_bytes"] == 5

    def test_dataset_files_bad_ref(self, kg):
        assert kg.dataset_files("no-slash") == []


class TestSnapshotDeterminism:
    def test_download_creates_manifest_and_hash(self, kg):
        zip_bytes = b"PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        with patch.object(kg, "_api", return_value={}), \
             patch("urllib.request.urlopen", return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=lambda: zip_bytes)))):
            result = kg.download_dataset("owner/nba-stats")

        assert result["status"] == "ok"
        assert result["reused"] is False
        assert result["content_hash"]
        manifest_path = result["manifest"]
        assert os.path.exists(manifest_path)
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        assert manifest["ref"] == "owner/nba-stats"
        assert manifest["content_hash"] == result["content_hash"]

    def test_download_reuses_existing_snapshot(self, kg):
        zip_bytes = b"PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        with patch("urllib.request.urlopen", return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=lambda: zip_bytes)))):
            first = kg.download_dataset("owner/nba-stats")

        # Second call without force should reuse — no new urlopen required
        with patch("urllib.request.urlopen") as uo:
            second = kg.download_dataset("owner/nba-stats")
            uo.assert_not_called()

        assert second["reused"] is True
        assert second["content_hash"] == first["content_hash"]

    def test_force_redownloads(self, kg):
        zip_bytes = b"PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        with patch("urllib.request.urlopen", return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=lambda: zip_bytes)))):
            kg.download_dataset("owner/nba-stats")
            forced = kg.download_dataset("owner/nba-stats", force=True)
        assert forced["reused"] is False

    def test_download_requires_creds(self, tmp_path):
        """Public datasets download without credentials (auth errors come from the server)."""
        kg = KaggleManager(username="", api_key="", data_dir=str(tmp_path / "kaggle"))
        fake = MagicMock(read=lambda: b"PK\x05\x06" + b"\x00" * 18)
        with patch("urllib.request.urlopen", return_value=MagicMock(__enter__=MagicMock(return_value=fake))) as uo:
            result = kg.download_dataset("owner/nba-stats")
        assert result.get("status") == "ok"
        uo.assert_called_once()

    def test_list_snapshots(self, kg):
        zip_bytes = b"PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        with patch("urllib.request.urlopen", return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock(read=lambda: zip_bytes)))):
            kg.download_dataset("owner/nba-stats")
        snaps = kg.list_snapshots()
        assert len(snaps) == 1
        assert snaps[0]["ref"] == "owner/nba-stats"


class TestFileEntry:
    def test_content_hash_stable(self):
        files = [
            {"path": "a.csv", "sha256": "x" * 64},
            {"path": "b.csv", "sha256": "y" * 64},
        ]
        h1 = KaggleManager._content_hash(files)
        h2 = KaggleManager._content_hash(list(reversed(files)))
        assert h1 == h2  # order-independent
