"""Tests for skills/hermes_ingest.py (stdlib + tmp dirs only, no network).

Run with:  pytest tests/test_hermes_ingest.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.hermes_ingest import (  # noqa: E402
    discover_hermes_plugins,
    ingest_all,
    ingest_plugin,
    ingest_wiki_trees,
)


def _make_plugin(root: Path, name: str = "demo-plugin") -> Path:
    plug = root / name
    plug.mkdir(parents=True, exist_ok=True)
    (plug / "plugin.yaml").write_text(
        f"name: {name}\nversion: 1.2.3\nprovides_tools:\n  - search\n  - fetch\n",
        encoding="utf-8",
    )
    (plug / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Demo plugin skill.\n---\n\n# Demo\n\nBody.\n",
        encoding="utf-8",
    )
    return plug


class TestDiscover:
    def test_missing_roots_never_throw(self, tmp_path):
        result = discover_hermes_plugins([tmp_path / "nope", "/definitely/not/here"])
        assert result == []

    def test_finds_fixture_plugin_dir(self, tmp_path):
        plug = _make_plugin(tmp_path / "plugins")
        # a decoy dir without plugin.yaml must be ignored
        (tmp_path / "plugins" / "not-a-plugin").mkdir(parents=True, exist_ok=True)
        ((tmp_path / "plugins" / "not-a-plugin") / "SKILL.md").write_text("# x", encoding="utf-8")

        items = discover_hermes_plugins([tmp_path / "plugins"])
        assert len(items) == 1
        item = items[0]
        assert item["plugin"] == "demo-plugin"
        assert item["version"] == "1.2.3"
        assert item["skill_path"] == str((plug / "SKILL.md").resolve())
        assert item["provides_tools"] == ["search", "fetch"]

    def test_default_roots_do_not_throw(self):
        # Environment-dependent (may find real plugins or nothing) — only
        # assert the fail-soft contract: a list is always returned.
        assert isinstance(discover_hermes_plugins(), list)


class TestIngest:
    def test_ingest_copies_and_second_run_skips(self, tmp_path):
        plug = _make_plugin(tmp_path / "plugins")
        dest = tmp_path / "packs" / "hermes"

        first = ingest_plugin(plug / "SKILL.md", dest)
        assert first["ingested"] is True
        assert (dest / "demo-plugin" / "SKILL.md").is_file()
        assert (dest / "demo-plugin" / "plugin.yaml").is_file()

        second = ingest_plugin(plug / "SKILL.md", dest)
        assert second["ingested"] is False
        assert "skipped" in second["reason"]

    def test_never_overwrites_newer_dest(self, tmp_path):
        plug = _make_plugin(tmp_path / "plugins")
        dest = tmp_path / "packs" / "hermes"
        ingest_plugin(plug / "SKILL.md", dest)

        # Make the destination strictly newer than the source.
        dest_skill = dest / "demo-plugin" / "SKILL.md"
        src_skill = plug / "SKILL.md"
        newer = src_skill.stat().st_mtime + 100
        os.utime(dest_skill, (newer, newer))
        dest_skill.write_text("NEWER HAND-EDITED CONTENT", encoding="utf-8")
        os.utime(dest_skill, (newer + 1, newer + 1))

        res = ingest_plugin(src_skill, dest)
        assert res["ingested"] is False
        assert "newer-dest" in res["reason"]
        assert dest_skill.read_text(encoding="utf-8") == "NEWER HAND-EDITED CONTENT"

    def test_ingest_all_summary(self, tmp_path):
        _make_plugin(tmp_path / "plugins", "alpha")
        _make_plugin(tmp_path / "plugins", "beta")
        dest = tmp_path / "packs" / "hermes"

        summary = ingest_all([tmp_path / "plugins"], dest)
        assert summary["found"] == 2
        assert summary["ingested"] == 2
        assert summary["skipped"] == 0
        assert summary["errors"] == []

        rerun = ingest_all([tmp_path / "plugins"], dest)
        assert rerun["found"] == 2
        assert rerun["ingested"] == 0
        assert rerun["skipped"] == 2


class TestWiki:
    def test_empty_root_returns_found_zero(self, tmp_path):
        summary = ingest_wiki_trees(tmp_path / "wiki-empty", tmp_path / "hermes_wiki")
        assert summary["found"] == 0
        assert summary["copied"] == 0

    def test_copies_repo_trees_idempotently(self, tmp_path):
        repo = tmp_path / "wiki" / "some-repo"
        (repo / "docs").mkdir(parents=True, exist_ok=True)
        (repo / "Home.md").write_text("# Home", encoding="utf-8")
        (repo / "docs" / "Guide.md").write_text("# Guide", encoding="utf-8")

        first = ingest_wiki_trees(tmp_path / "wiki", tmp_path / "hermes_wiki")
        assert first["found"] == 2
        assert first["copied"] == 2
        assert first["repos"] == ["some-repo"]
        assert (tmp_path / "hermes_wiki" / "some-repo" / "Home.md").is_file()
        assert (tmp_path / "hermes_wiki" / "_index.json").is_file()

        second = ingest_wiki_trees(tmp_path / "wiki", tmp_path / "hermes_wiki")
        assert second["found"] == 2
        assert second["copied"] == 0
        assert second["skipped"] == 2
