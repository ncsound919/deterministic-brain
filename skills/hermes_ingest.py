"""Hermes-plugin skill ingestion (deterministic, stdlib only, no network).

Discovers Hermes plugin dirs (``plugin.yaml`` + ``SKILL.md``) and ingests
them into the brain's canonical runtime location so the existing
``SkillRegistry`` picks them up with zero core-loop changes:

- plugins  -> ``skill_packs/hermes/<plugin>/`` (same convention as
  ``scripts/import_skills.py`` which writes ``skill_packs/hermes/``;
  ``SkillRegistry`` discovers both ``skill_packs/<skill>/SKILL.md`` flat
  and ``skill_packs/<category>/<skill>/SKILL.md`` nested layouts).
- wiki trees produced by hermes-deepwiki
  (``knowledge_bank/wiki/<repo>/*.md``) -> ``knowledge_bank/hermes_wiki/``
  (+ ``_index.json``). ``knowledge_bank/`` otherwise holds ``fragments.db``
  + ``refs/`` (+ ``synthesis/``), i.e. there is no pre-existing wiki
  convention, so a dedicated ``hermes_wiki/`` tree is used.

All entry points are fail-soft: missing roots, unreadable files, and copy
errors are reported in the returned dicts, never raised (except programmer
errors such as a non-directory ``skill_path`` passed explicitly — even
those return ``ingested: False`` with a reason).

Usage:
    python -m skills.hermes_ingest --list
    python -m skills.hermes_ingest --ingest
    python -m skills.hermes_ingest --wiki
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

BRAIN_ROOT = Path(__file__).resolve().parent.parent

# Default search roots: agents/hermes-integrations (sibling of
# deterministic-brain under agents/) plus the per-user plugin dir.
DEFAULT_SEARCH_ROOTS: List[Path] = [
    Path(__file__).resolve().parent.parent.parent / "hermes-integrations",
    Path(os.path.expanduser("~/.hermes/plugins")),
]

DEFAULT_DEST_ROOT = BRAIN_ROOT / "skill_packs" / "hermes"
DEFAULT_WIKI_ROOT = BRAIN_ROOT / "knowledge_bank" / "wiki"
DEFAULT_WIKI_DEST = BRAIN_ROOT / "knowledge_bank" / "hermes_wiki"

_SAFE_NAME_RE = re.compile(r"[^a-z0-9-]+")


def sanitize_name(name: str) -> str:
    """Lowercase + slugify a plugin/repo name for use as a directory name."""
    slug = _SAFE_NAME_RE.sub("-", (name or "").strip().lower()).strip("-")
    return slug[:60] or "unknown"


def _parse_plugin_yaml(path: Path) -> Dict[str, Any]:
    """Minimal ``plugin.yaml`` parser (stdlib only, no PyYAML).

    Understands flat ``key: value`` pairs plus one level of ``key:``
    followed by ``- item`` list lines (enough for ``provides_tools:`` /
    ``tools:``). Anything else is ignored fail-soft.
    """
    data: Dict[str, Any] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return data
    current_list_key: Optional[str] = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_list_key:
            data.setdefault(current_list_key, []).append(stripped[2:].strip().strip("'\""))
            continue
        current_list_key = None
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip().lower()
            value = value.strip().strip("'\"")
            if value == "":
                current_list_key = key  # start of a list block
                data.setdefault(key, [])
            else:
                # inline "[a, b]" list support
                if value.startswith("[") and value.endswith("]"):
                    data[key] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                else:
                    data[key] = value
    return data


def _read_skill_title(skill_md: Path) -> str:
    """Best-effort title: first ``# heading`` of SKILL.md, else ''."""
    try:
        for line in skill_md.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith("#"):
                return s.lstrip("#").strip()[:120]
    except Exception:
        pass
    return ""


def discover_hermes_plugins(search_roots=None) -> List[Dict[str, Any]]:
    """Find plugin dirs containing ``plugin.yaml`` + ``SKILL.md``.

    Never throws on missing/unreadable roots — they are silently skipped.
    """
    roots = list(search_roots) if search_roots is not None else list(DEFAULT_SEARCH_ROOTS)
    found: List[Dict[str, Any]] = []
    for root in roots:
        try:
            root_path = Path(root)
        except Exception:
            continue
        try:
            if not root_path.is_dir():
                continue
            children = sorted(root_path.iterdir())
        except Exception:
            continue
        for child in children:
            try:
                if not child.is_dir():
                    continue
                plugin_yaml = child / "plugin.yaml"
                skill_md = child / "SKILL.md"
                if not (plugin_yaml.is_file() and skill_md.is_file()):
                    continue
                meta = _parse_plugin_yaml(plugin_yaml)
                name = str(meta.get("name") or child.name)
                version = str(meta.get("version") or "unknown")
                tools: List[str] = []
                for key in ("provides_tools", "provides-tools", "tools"):
                    val = meta.get(key)
                    if isinstance(val, list):
                        tools.extend(str(v) for v in val)
                    elif isinstance(val, str) and val:
                        tools.append(val)
                found.append(
                    {
                        "plugin": sanitize_name(name),
                        "raw_name": name,
                        "version": version,
                        "skill_path": str(skill_md.resolve()),
                        "plugin_dir": str(child.resolve()),
                        "provides_tools": tools,
                        "title": _read_skill_title(skill_md),
                    }
                )
            except Exception:
                continue
    return found


def _same_or_newer(src: Path, dest: Path) -> Optional[str]:
    """Compare src vs existing dest file.

    Returns None if dest is missing (copy needed), else a skip reason:
    ``up-to-date`` (same size + src not newer) or ``newer-dest`` (dest
    strictly newer — never overwritten silently).
    """
    try:
        if not dest.exists():
            return None
        s, d = src.stat(), dest.stat()
        if d.st_mtime > s.st_mtime:
            return "newer-dest"
        if d.st_mtime == s.st_mtime and d.st_size == s.st_size:
            return "up-to-date"
        if d.st_size == s.st_size and d.st_mtime >= s.st_mtime:
            return "up-to-date"
        if d.st_mtime >= s.st_mtime:
            return "newer-dest"
        return None  # src is newer -> copy allowed
    except Exception:
        return None


def ingest_plugin(skill_path, dest_root=None) -> Dict[str, Any]:
    """Copy one plugin's SKILL.md (+ plugin.yaml) into skill_packs/hermes/.

    Idempotent: a second run with unchanged sources reports
    ``ingested: False`` with reason ``skipped-...``. Never overwrites a
    newer destination file silently.
    """
    try:
        src_skill = Path(skill_path)
    except Exception as e:
        return {"ingested": False, "dest": "", "reason": f"bad-skill-path: {e}"}
    try:
        if not src_skill.is_file():
            return {"ingested": False, "dest": "", "reason": "skill-not-found"}
        src_dir = src_skill.parent
        plugin_yaml = src_dir / "plugin.yaml"
        meta = _parse_plugin_yaml(plugin_yaml) if plugin_yaml.is_file() else {}
        plugin = sanitize_name(str(meta.get("name") or src_dir.name))
        try:
            dest_base = Path(dest_root) if dest_root is not None else DEFAULT_DEST_ROOT
        except Exception as e:
            return {"ingested": False, "dest": "", "reason": f"bad-dest-root: {e}"}
        dest_dir = dest_base / plugin
        try:
            dest_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return {"ingested": False, "dest": str(dest_dir), "reason": f"mkdir-failed: {e}"}

        files: List[tuple] = [(src_skill, dest_dir / "SKILL.md")]
        if plugin_yaml.is_file():
            files.append((plugin_yaml, dest_dir / "plugin.yaml"))

        copied, skipped = [], []
        for src, dest in files:
            reason = _same_or_newer(src, dest)
            if reason is not None:
                skipped.append({"file": dest.name, "reason": f"skipped-{reason}"})
                continue
            try:
                shutil.copy2(src, dest)
                copied.append(dest.name)
            except Exception as e:
                return {
                    "ingested": bool(copied),
                    "dest": str(dest_dir),
                    "reason": f"copy-failed: {dest.name}: {e}",
                    "copied": copied,
                    "skipped": skipped,
                }
        if copied:
            return {
                "ingested": True,
                "dest": str(dest_dir),
                "reason": "ingested",
                "copied": copied,
                "skipped": skipped,
            }
        first = skipped[0]["reason"] if skipped else "skipped-up-to-date"
        return {"ingested": False, "dest": str(dest_dir), "reason": first, "skipped": skipped}
    except Exception as e:  # fail-soft catch-all
        return {"ingested": False, "dest": "", "reason": f"error: {e}"}


def ingest_all(search_roots=None, dest_root=None) -> Dict[str, Any]:
    """Discover + ingest every plugin. Returns summary dict."""
    try:
        discovered = discover_hermes_plugins(search_roots)
    except Exception as e:  # discover itself never throws, belt & braces
        return {"found": 0, "ingested": 0, "skipped": 0, "errors": [str(e)]}
    ingested = skipped = 0
    errors: List[str] = []
    details: List[Dict[str, Any]] = []
    for item in discovered:
        res = ingest_plugin(item["skill_path"], dest_root)
        res = {"plugin": item.get("plugin", "?"), **res}
        details.append(res)
        if res.get("ingested"):
            ingested += 1
        else:
            reason = str(res.get("reason", ""))
            if reason.startswith("copy-failed") or reason.startswith("mkdir-failed") \
                    or reason.startswith("error") or reason.startswith("bad-"):
                errors.append(f"{res['plugin']}: {reason}")
            else:
                skipped += 1
    return {
        "found": len(discovered),
        "ingested": ingested,
        "skipped": skipped,
        "errors": errors,
        "details": details,
    }


def ingest_wiki_trees(wiki_root=None, dest_root=None) -> Dict[str, Any]:
    """Copy ``knowledge_bank/wiki/<repo>/*.md`` trees to ``hermes_wiki/``.

    Idempotent per-file (mtime/size compare, never overwrite newer dest).
    Writes ``_index.json`` in the dest. If no trees exist, honestly
    returns ``{found: 0, ...}``.
    """
    try:
        wroot = Path(wiki_root) if wiki_root is not None else DEFAULT_WIKI_ROOT
    except Exception as e:
        return {"found": 0, "repos": [], "copied": 0, "skipped": 0, "errors": [f"bad-wiki-root: {e}"]}
    try:
        droot = Path(dest_root) if dest_root is not None else DEFAULT_WIKI_DEST
    except Exception as e:
        return {"found": 0, "repos": [], "copied": 0, "skipped": 0, "errors": [f"bad-dest-root: {e}"]}
    try:
        if not wroot.is_dir():
            return {"found": 0, "repos": [], "copied": 0, "skipped": 0, "errors": []}
        repos = sorted([p for p in wroot.iterdir() if p.is_dir()], key=lambda p: p.name)
    except Exception as e:
        return {"found": 0, "repos": [], "copied": 0, "skipped": 0, "errors": [str(e)]}
    md_files: List[Path] = []
    for repo in repos:
        try:
            md_files.extend(sorted(repo.rglob("*.md")))
        except Exception:
            continue
    if not md_files:
        return {"found": 0, "repos": [], "copied": 0, "skipped": 0, "errors": []}
    try:
        droot.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"found": 0, "repos": [], "copied": 0, "skipped": 0, "errors": [f"mkdir-failed: {e}"]}
    copied = skipped = 0
    errors: List[str] = []
    indexed_repos: List[str] = []
    for src in md_files:
        try:
            rel = src.relative_to(wroot)
        except Exception:
            continue
        dest = droot / rel
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"{rel}: mkdir-failed: {e}")
            continue
        reason = _same_or_newer(src, dest)
        if reason is not None:
            skipped += 1
            continue
        try:
            shutil.copy2(src, dest)
            copied += 1
        except Exception as e:
            errors.append(f"{rel}: copy-failed: {e}")
            continue
    try:
        indexed_repos = sorted({p.name for p in repos if any((p).rglob("*.md"))})
    except Exception:
        indexed_repos = sorted([p.name for p in repos])
    index = {
        "repos": indexed_repos,
        "files_copied": copied,
        "files_skipped": skipped,
        "source": str(wroot),
    }
    try:
        (droot / "_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    except Exception as e:
        errors.append(f"_index.json: write-failed: {e}")
    return {
        "found": len(md_files),
        "repos": indexed_repos,
        "copied": copied,
        "skipped": skipped,
        "errors": errors,
        "dest": str(droot),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Hermes-plugin skill ingestion (stdlib only, no network).")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List discovered Hermes plugins.")
    group.add_argument("--ingest", action="store_true", help="Discover + ingest all plugins.")
    group.add_argument("--wiki", action="store_true", help="Ingest hermes-deepwiki markdown trees.")
    parser.add_argument("--search-root", action="append", default=[], help="Extra plugin search root (repeatable).")
    parser.add_argument("--dest-root", default=None, help="Override ingest destination root.")
    parser.add_argument("--wiki-root", default=None, help="Override wiki source root.")
    parser.add_argument("--wiki-dest", default=None, help="Override wiki destination root.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    search_roots = list(args.search_root) if args.search_root else None

    if args.list:
        items = discover_hermes_plugins(search_roots)
        if args.json:
            print(json.dumps(items, indent=2))
        else:
            if not items:
                print("No Hermes plugins found.")
            for it in items:
                tools = ", ".join(it["provides_tools"]) if it["provides_tools"] else "-"
                print(f"{it['plugin']} v{it['version']} :: {it['skill_path']} :: tools: {tools}")
        return 0
    if args.ingest:
        summary = ingest_all(search_roots, args.dest_root)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"found={summary['found']} ingested={summary['ingested']} "
                  f"skipped={summary['skipped']} errors={len(summary['errors'])}")
            for d in summary.get("details", []):
                print(f"  {d['plugin']}: ingested={d['ingested']} reason={d['reason']} dest={d['dest']}")
            for e in summary["errors"]:
                print(f"  ERROR: {e}")
        return 0 if not summary["errors"] else 1
    if args.wiki:
        summary = ingest_wiki_trees(args.wiki_root, args.wiki_dest)
        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"found={summary['found']} copied={summary['copied']} "
                  f"skipped={summary['skipped']} errors={len(summary['errors'])}")
            if summary.get("repos"):
                print("repos: " + ", ".join(summary["repos"]))
            for e in summary["errors"]:
                print(f"  ERROR: {e}")
        return 0 if not summary["errors"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
