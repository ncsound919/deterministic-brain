#!/usr/bin/env python3
"""Collect PUBLIC Hugging Face repository metadata for a profile audit.

This helper gathers only publicly available metadata (models, datasets, and
Spaces) for a given Hugging Face username or organization slug. It is meant to
feed a profile-optimization audit. It is deliberately lightweight and not
aggressive: it caps the number of repositories fetched per category.

Design constraints:
- Public data only. No token is required and the tool works fully in public
  mode. If the environment variable HF_TOKEN is set, it is passed to the API
  so that private repos you own can be listed, but the token is NEVER printed,
  logged, echoed, or written to any output.
- Uses only the Python standard library plus, optionally, the huggingface_hub
  package (imported inside a try/except). No other third-party dependency.
- No HTML scraping, no private-access tricks, no bypassing of any protection.

Offline validation:
    python3 hf_public_profile_audit.py --self-test

The self-test builds a fixed in-memory sample result and exercises the pure
formatting functions (JSON and Markdown) without any network access and
without importing huggingface_hub. It is the supported way to validate the
script in an offline environment.

Usage examples:
    python3 hf_public_profile_audit.py someuser
    python3 hf_public_profile_audit.py some-org --format json --limit 25
    python3 hf_public_profile_audit.py --self-test
"""

import argparse
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional

EXIT_OK = 0
EXIT_ERROR = 1

# Categories of repositories we collect, mapped to their HfApi list method name.
REPO_CATEGORIES = ("models", "datasets", "spaces")


def _to_iso(value: Any) -> Optional[str]:
    """Return an ISO-8601 string for a datetime-like value, else pass through.

    Missing values become None. Strings are returned as-is. Objects that expose
    an isoformat method (datetime, date) are converted. Anything else is
    stringified defensively so the result stays JSON-serializable.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        try:
            return isoformat()
        except Exception:
            return str(value)
    return str(value)


def _summarize_card_data(card_data: Any) -> Optional[Dict[str, Any]]:
    """Produce a compact summary of card/metadata without dumping large content.

    Returns a small dict describing which top-level metadata keys are present,
    plus a few short scalar values when they are cheap to include. Large or
    nested values are reduced to their key names only, so we never dump big
    payloads (for example full model-index eval tables or long descriptions).
    """
    if card_data is None:
        return None

    # huggingface_hub may expose card data as an object with to_dict, or as a
    # plain mapping. Normalize to a plain dict when possible.
    data: Any = card_data
    to_dict = getattr(card_data, "to_dict", None)
    if callable(to_dict):
        try:
            data = to_dict()
        except Exception:
            data = None

    if not isinstance(data, dict):
        # Unknown shape: report only that some metadata exists.
        return {"present": True, "keys": None}

    keys = sorted(str(k) for k in data.keys())
    summary: Dict[str, Any] = {"present": True, "keys": keys}

    # Include a few short, safe scalar values when available.
    for short_key in ("license", "language", "pipeline_tag", "library_name"):
        if short_key in data:
            val = data[short_key]
            if isinstance(val, (str, int, float, bool)):
                summary[short_key] = val
            elif isinstance(val, list):
                # Keep short lists of scalars only, capped in length.
                scalars = [v for v in val if isinstance(v, (str, int, float, bool))]
                summary[short_key] = scalars[:10]
    return summary


def _extract_repo(item: Any, repo_type: str) -> Dict[str, Any]:
    """Extract only the present public fields from a repo info object.

    Any field that is absent becomes None (never fabricated).
    """
    repo_id = getattr(item, "id", None)
    if repo_id is None:
        repo_id = getattr(item, "modelId", None)
    if repo_id is None:
        repo_id = getattr(item, "repo_id", None)

    name: Optional[str] = None
    if isinstance(repo_id, str) and "/" in repo_id:
        name = repo_id.split("/")[-1]
    elif isinstance(repo_id, str):
        name = repo_id

    tags = getattr(item, "tags", None)
    if tags is not None:
        try:
            tags = list(tags)
        except Exception:
            tags = None

    last_modified = _to_iso(getattr(item, "lastModified", None))
    if last_modified is None:
        last_modified = _to_iso(getattr(item, "last_modified", None))

    card_data = getattr(item, "cardData", None)
    if card_data is None:
        card_data = getattr(item, "card_data", None)

    return {
        "id": repo_id if isinstance(repo_id, str) else (str(repo_id) if repo_id is not None else None),
        "name": name,
        "repo_type": repo_type,
        "likes": getattr(item, "likes", None),
        "downloads": getattr(item, "downloads", None),
        "tags": tags,
        "lastModified": last_modified,
        "cardData": _summarize_card_data(card_data),
    }


def collect_profile(author: str, limit: int, token: Optional[str]) -> Dict[str, Any]:
    """Collect public repository metadata for an author using huggingface_hub.

    This function performs network access and requires huggingface_hub. Each
    category call is isolated so that a failure in one does not prevent the
    others. Errors are recorded as human-readable notes instead of raising.

    The token (if any) is passed to the API but is never included in the
    returned structure, printed, or logged.
    """
    # Imported here (not at module top) so that --self-test never needs it.
    from huggingface_hub import HfApi  # type: ignore

    api = HfApi()
    result: Dict[str, Any] = {
        "author": author,
        "collected_at": None,
        "counts": {"models": 0, "datasets": 0, "spaces": 0},
        "models": [],
        "datasets": [],
        "spaces": [],
        "notes": [],
    }

    listers: Dict[str, Callable[..., Any]] = {
        "models": api.list_models,
        "datasets": api.list_datasets,
        "spaces": api.list_spaces,
    }

    # Singular repo_type label used when extracting each item.
    type_label = {"models": "model", "datasets": "dataset", "spaces": "space"}

    for category in REPO_CATEGORIES:
        lister = listers[category]
        try:
            items = lister(author=author, limit=limit, token=token)
            collected: List[Dict[str, Any]] = []
            for item in items:
                collected.append(_extract_repo(item, type_label[category]))
            result[category] = collected
            result["counts"][category] = len(collected)
            if len(collected) >= limit:
                result["notes"].append(
                    "Category '%s' hit the --limit cap of %d; more repos may exist."
                    % (category, limit)
                )
        except Exception as exc:  # noqa: BLE001 - we intentionally degrade gracefully
            # Keep the note free of any sensitive detail; do not include token.
            result["notes"].append(
                "Failed to list %s for '%s': %s: %s"
                % (category, author, type(exc).__name__, _safe_error_text(exc))
            )
            result[category] = []
            result["counts"][category] = 0

    return result


def _safe_error_text(exc: Exception) -> str:
    """Return a short, safe string for an exception message.

    Truncated to avoid dumping large payloads into notes. Never includes any
    environment secret because we never put the token into exception context.
    """
    text = str(exc).strip()
    if not text:
        return "(no message)"
    text = text.replace("\n", " ").replace("\r", " ")
    if len(text) > 300:
        text = text[:297] + "..."
    return text


def format_json(result: Dict[str, Any]) -> str:
    """Serialize the result dict to indented JSON (pure function)."""
    return json.dumps(result, indent=2, default=str)


def _fmt_field(value: Any) -> str:
    """Render a single field value for Markdown, marking missing as n/a."""
    if value is None:
        return "n/a"
    if isinstance(value, list):
        if not value:
            return "n/a"
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        keys = value.get("keys")
        if keys:
            return "card keys: " + ", ".join(str(k) for k in keys)
        if value.get("present"):
            return "present"
        return "n/a"
    return str(value)


def _format_repo_bullet(repo: Dict[str, Any]) -> str:
    """Render one repository as a Markdown bullet (pure function)."""
    name = _fmt_field(repo.get("id") or repo.get("name"))
    likes = _fmt_field(repo.get("likes"))
    downloads = _fmt_field(repo.get("downloads"))
    last_modified = _fmt_field(repo.get("lastModified"))
    tags = _fmt_field(repo.get("tags"))
    card = _fmt_field(repo.get("cardData"))
    return (
        "- %s\n"
        "  - likes: %s | downloads: %s | lastModified: %s\n"
        "  - tags: %s\n"
        "  - metadata: %s"
        % (name, likes, downloads, last_modified, tags, card)
    )


def format_markdown(result: Dict[str, Any]) -> str:
    """Render the result dict as a readable Markdown summary (pure function)."""
    author = result.get("author")
    author_label = author if author else "unknown"
    counts = result.get("counts", {}) or {}
    n_models = counts.get("models", 0)
    n_datasets = counts.get("datasets", 0)
    n_spaces = counts.get("spaces", 0)

    lines: List[str] = []
    lines.append("# Hugging Face public profile audit: %s" % author_label)
    collected_at = result.get("collected_at")
    if collected_at:
        lines.append("")
        lines.append("Collected at: %s" % collected_at)
    lines.append("")
    lines.append(
        "Counts: models=%s, datasets=%s, spaces=%s"
        % (n_models, n_datasets, n_spaces)
    )

    section_titles = {
        "models": "## Models",
        "datasets": "## Datasets",
        "spaces": "## Spaces",
    }
    for category in REPO_CATEGORIES:
        lines.append("")
        lines.append(section_titles[category])
        repos = result.get(category) or []
        if not repos:
            lines.append("")
            lines.append("_None found or not collected._")
            continue
        lines.append("")
        for repo in repos:
            lines.append(_format_repo_bullet(repo))

    lines.append("")
    lines.append("## Notes")
    notes = result.get("notes") or []
    if not notes:
        lines.append("")
        lines.append("_No notes._")
    else:
        lines.append("")
        for note in notes:
            lines.append("- %s" % note)

    lines.append("")
    return "\n".join(lines)


def render(result: Dict[str, Any], fmt: str) -> str:
    """Dispatch to the requested output formatter (pure function)."""
    if fmt == "json":
        return format_json(result)
    return format_markdown(result)


def _build_sample_result() -> Dict[str, Any]:
    """Return a fixed, deterministic sample result for --self-test.

    No network access, no huggingface_hub, no clock reads: this must stay
    fully deterministic so the self-test assertions are stable.
    """
    return {
        "author": "sample-user",
        "collected_at": None,
        "counts": {"models": 2, "datasets": 1, "spaces": 1},
        "models": [
            {
                "id": "sample-user/demo-model",
                "name": "demo-model",
                "repo_type": "model",
                "likes": 12,
                "downloads": 3456,
                "tags": ["text-classification", "pytorch"],
                "lastModified": "2026-01-15T10:00:00",
                "cardData": {
                    "present": True,
                    "keys": ["license", "language", "pipeline_tag"],
                    "license": "apache-2.0",
                    "pipeline_tag": "text-classification",
                },
            },
            {
                "id": "sample-user/second-model",
                "name": "second-model",
                "repo_type": "model",
                "likes": None,
                "downloads": None,
                "tags": None,
                "lastModified": None,
                "cardData": None,
            },
        ],
        "datasets": [
            {
                "id": "sample-user/demo-dataset",
                "name": "demo-dataset",
                "repo_type": "dataset",
                "likes": 3,
                "downloads": 120,
                "tags": ["tabular"],
                "lastModified": "2026-02-01T08:30:00",
                "cardData": {"present": True, "keys": ["license"], "license": "mit"},
            }
        ],
        "spaces": [
            {
                "id": "sample-user/demo-space",
                "name": "demo-space",
                "repo_type": "space",
                "likes": 7,
                "downloads": None,
                "tags": ["gradio"],
                "lastModified": "2026-03-10T12:00:00",
                "cardData": None,
            }
        ],
        "notes": ["Sample note: this is offline self-test data."],
    }


def run_self_test() -> int:
    """Exercise the pure formatters on a fixed sample and assert structure.

    Returns EXIT_OK on success, EXIT_ERROR on any failed assertion. Prints a
    single PASS or FAIL line. No network, no huggingface_hub import.
    """
    failures: List[str] = []
    sample = _build_sample_result()

    # JSON formatter checks.
    try:
        json_out = format_json(sample)
        parsed = json.loads(json_out)
        if parsed.get("author") != "sample-user":
            failures.append("json: author mismatch")
        if parsed.get("counts", {}).get("models") != 2:
            failures.append("json: models count mismatch")
        if parsed.get("counts", {}).get("datasets") != 1:
            failures.append("json: datasets count mismatch")
        if parsed.get("counts", {}).get("spaces") != 1:
            failures.append("json: spaces count mismatch")
    except Exception as exc:  # noqa: BLE001
        failures.append("json: raised %s: %s" % (type(exc).__name__, exc))

    # Markdown formatter checks.
    try:
        md_out = format_markdown(sample)
        required_fragments = [
            "# Hugging Face public profile audit: sample-user",
            "Counts: models=2, datasets=1, spaces=1",
            "## Models",
            "## Datasets",
            "## Spaces",
            "## Notes",
            "sample-user/demo-model",
        ]
        for fragment in required_fragments:
            if fragment not in md_out:
                failures.append("md: missing fragment %r" % fragment)
        # Missing fields must render as n/a somewhere (second-model has none).
        if "n/a" not in md_out:
            failures.append("md: expected 'n/a' for missing fields")
    except Exception as exc:  # noqa: BLE001
        failures.append("md: raised %s: %s" % (type(exc).__name__, exc))

    # Empty-category rendering check.
    try:
        empty = {
            "author": "empty-user",
            "collected_at": None,
            "counts": {"models": 0, "datasets": 0, "spaces": 0},
            "models": [],
            "datasets": [],
            "spaces": [],
            "notes": [],
        }
        md_empty = format_markdown(empty)
        if "_None found or not collected._" not in md_empty:
            failures.append("md: empty category placeholder missing")
        if "_No notes._" not in md_empty:
            failures.append("md: empty notes placeholder missing")
    except Exception as exc:  # noqa: BLE001
        failures.append("md: empty case raised %s: %s" % (type(exc).__name__, exc))

    if failures:
        print("SELF-TEST: FAIL")
        for f in failures:
            print("  - %s" % f)
        return EXIT_ERROR
    print("SELF-TEST: PASS")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="hf_public_profile_audit.py",
        description=(
            "Collect PUBLIC Hugging Face repository metadata (models, datasets, "
            "spaces) for a username or organization slug, to feed a profile "
            "audit. Public data only; no token required. If HF_TOKEN is set in "
            "the environment it is used but never printed or stored."
        ),
        epilog=(
            "Offline validation: python3 hf_public_profile_audit.py --self-test"
        ),
    )
    parser.add_argument(
        "author",
        nargs="?",
        default=None,
        help="Hugging Face username or organization slug (optional if --self-test is given).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "md"),
        default="md",
        help="Output format (default: md).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max repositories fetched per category, to stay lightweight (default: 50).",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in offline formatting checks on sample data and exit (no network).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Program entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test()

    if not args.author:
        # No author and no self-test: show usage and exit non-zero.
        parser.print_usage(sys.stderr)
        print(
            "error: an 'author' argument is required unless --self-test is used.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    if args.limit <= 0:
        print("error: --limit must be a positive integer.", file=sys.stderr)
        return EXIT_ERROR

    # Attempt to import the optional dependency. Give a clear install hint if
    # it is missing and exit gracefully (non-zero), without a traceback.
    try:
        import huggingface_hub  # noqa: F401  (import checked, used in collect_profile)
    except ImportError:
        print(
            "The optional dependency 'huggingface_hub' is not installed.",
            file=sys.stderr,
        )
        print(
            "Install it to enable public metadata collection:",
            file=sys.stderr,
        )
        print("    pip install huggingface_hub", file=sys.stderr)
        return EXIT_ERROR

    # Read the token from the environment ONLY. It may be None (public mode).
    # It is never printed, logged, or written into any output structure.
    token = os.environ.get("HF_TOKEN")

    try:
        result = collect_profile(args.author, args.limit, token)
    except Exception as exc:  # noqa: BLE001 - never crash with a raw traceback
        print(
            "error: unexpected failure while collecting data for '%s': %s: %s"
            % (args.author, type(exc).__name__, _safe_error_text(exc)),
            file=sys.stderr,
        )
        return EXIT_ERROR

    # A totally empty result with all categories failing is worth flagging, but
    # is not itself a hard error (the author may simply have no public repos).
    try:
        output = render(result, args.format)
    except Exception as exc:  # noqa: BLE001
        print(
            "error: failed to format output: %s: %s"
            % (type(exc).__name__, _safe_error_text(exc)),
            file=sys.stderr,
        )
        return EXIT_ERROR

    print(output)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
