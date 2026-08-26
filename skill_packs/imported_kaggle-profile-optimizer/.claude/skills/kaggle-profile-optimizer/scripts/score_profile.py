#!/usr/bin/env python3
"""Indicative 0-5 scorecard for a Kaggle profile from a LOCAL JSON file.

This is a diagnostic aid, not a verdict. It reads a single local JSON file
describing a Kaggle profile and applies transparent heuristics to produce a
0-5 score across 12 dimensions, plus an overall average and a coverage line.

Design notes:
- Standard library only. No network calls. No credentials.
- Every dimension is scored by a small pure function so the logic is testable.
- Fields are optional. When the data needed for a dimension is absent, the
  dimension is set to None and a note "insufficient data: provide X" is added.
- Output is deterministic so tests stay stable.

It never claims guaranteed outcomes. Presentation is not the same as real
skill, and a recruiter or reviewer still needs to look at the actual work.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# Number of dimensions we attempt to score.
TOTAL_DIMENSIONS = 12


@dataclass
class DimensionResult:
    """Score and note for a single dimension.

    score is an int in 0..5 when the dimension could be scored, else None.
    note is a short human-readable explanation (never empty).
    """

    score: Optional[int]
    note: str


@dataclass
class Scorecard:
    """Full result of scoring a profile."""

    username: Optional[str]
    dimensions: Dict[str, DimensionResult] = field(default_factory=dict)
    overall: Optional[float] = None
    scored_count: int = 0
    total: int = TOTAL_DIMENSIONS


# ---------------------------------------------------------------------------
# Small helpers (pure)
# ---------------------------------------------------------------------------


def clamp_score(value: float) -> int:
    """Clamp a numeric score to the integer range 0..5.

    Values are rounded to the nearest integer first, then clamped. This keeps
    the scale discrete and predictable.
    """

    try:
        rounded = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    if rounded < 0:
        return 0
    if rounded > 5:
        return 5
    return rounded


def as_list(value: Any) -> List[Any]:
    """Return value as a list, treating None or non-lists as empty/singleton.

    Missing or malformed collections should never crash scoring; they simply
    behave as empty input.
    """

    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_dict(value: Any) -> Dict[str, Any]:
    """Return value as a dict, treating anything else as an empty dict."""

    if isinstance(value, dict):
        return value
    return {}


def get_bool(value: Any) -> bool:
    """Coerce a value to a strict bool (only True counts as truthy here)."""

    return value is True


def non_empty_str(value: Any) -> bool:
    """True when value is a string with at least one non-whitespace char."""

    return isinstance(value, str) and value.strip() != ""


def share(numerator: int, denominator: int) -> float:
    """Safe ratio in 0..1; returns 0.0 when denominator is 0."""

    if denominator <= 0:
        return 0.0
    return numerator / denominator


# ---------------------------------------------------------------------------
# Dimension scorers (pure). Each returns a DimensionResult.
# ---------------------------------------------------------------------------


def score_positioning_clarity(p: Dict[str, Any]) -> DimensionResult:
    """Bio present and specific, plus specialties listed."""

    bio = p.get("bio")
    specialties = as_list(p.get("specialties"))
    has_bio = "bio" in p
    has_specialties = "specialties" in p
    if not has_bio and not has_specialties:
        return DimensionResult(
            None, "insufficient data: provide bio and specialties"
        )

    score = 0.0
    if non_empty_str(bio):
        score += 2
        # Reward a bio that is reasonably specific (longer, descriptive).
        if len(bio.strip()) >= 80:
            score += 1
    if specialties:
        score += 2
    return DimensionResult(clamp_score(score), "bio specificity and specialties")


def score_technical_credibility(p: Dict[str, Any]) -> DimensionResult:
    """Volume of notebooks and competitions, plus any medals."""

    has_any = any(k in p for k in ("notebooks", "competitions"))
    if not has_any:
        return DimensionResult(
            None, "insufficient data: provide notebooks or competitions"
        )

    notebooks = as_list(p.get("notebooks"))
    competitions = as_list(p.get("competitions"))
    medals = sum(
        1 for c in competitions if non_empty_str(as_dict(c).get("medal"))
    )

    score = 0.0
    score += min(len(notebooks), 3)  # up to 3 points for notebook volume
    score += min(len(competitions), 1)  # 1 point for taking part at all
    if medals > 0:
        score += 1
    return DimensionResult(
        clamp_score(score), "notebook/competition volume and medals"
    )


def score_notebook_quality(p: Dict[str, Any]) -> DimensionResult:
    """Share of notebooks documented AND reproducible AND with intro/conclusion."""

    if "notebooks" not in p:
        return DimensionResult(None, "insufficient data: provide notebooks")
    notebooks = as_list(p.get("notebooks"))
    if not notebooks:
        return DimensionResult(0, "no notebooks to assess")

    good = 0
    for nb in notebooks:
        d = as_dict(nb)
        if (
            get_bool(d.get("documented"))
            and get_bool(d.get("reproducible"))
            and get_bool(d.get("has_intro_conclusion"))
        ):
            good += 1
    ratio = share(good, len(notebooks))
    return DimensionResult(
        clamp_score(ratio * 5), "share of well-formed notebooks"
    )


def score_dataset_quality(p: Dict[str, Any]) -> DimensionResult:
    """Share of datasets documented AND with a usage example."""

    if "datasets" not in p:
        return DimensionResult(None, "insufficient data: provide datasets")
    datasets = as_list(p.get("datasets"))
    if not datasets:
        return DimensionResult(0, "no datasets to assess")

    good = 0
    for ds in datasets:
        d = as_dict(ds)
        if get_bool(d.get("documented")) and get_bool(d.get("has_usage_example")):
            good += 1
    ratio = share(good, len(datasets))
    return DimensionResult(
        clamp_score(ratio * 5), "share of documented datasets with examples"
    )


def _best_percentile(competitions: List[Any]) -> Optional[float]:
    """Return the best (lowest) rank_percentile across competitions, or None.

    rank_percentile is interpreted as "top X percent", so lower is better.
    """

    best: Optional[float] = None
    for c in competitions:
        d = as_dict(c)
        pct = d.get("rank_percentile")
        if isinstance(pct, (int, float)):
            if best is None or pct < best:
                best = float(pct)
    return best


def score_competitions_progression(p: Dict[str, Any]) -> DimensionResult:
    """Number of competitions plus best rank percentile or medal."""

    if "competitions" not in p:
        return DimensionResult(None, "insufficient data: provide competitions")
    competitions = as_list(p.get("competitions"))
    if not competitions:
        return DimensionResult(0, "no competitions to assess")

    score = 0.0
    score += min(len(competitions), 2)  # up to 2 points for participation

    has_medal = any(
        non_empty_str(as_dict(c).get("medal")) for c in competitions
    )
    if has_medal:
        score += 2

    best = _best_percentile(competitions)
    if best is not None:
        if best <= 10:
            score += 1
        elif best <= 25:
            score += 0.5

    return DimensionResult(
        clamp_score(score), "participation, best rank and medals"
    )


def score_reproducibility(p: Dict[str, Any]) -> DimensionResult:
    """Share of notebooks marked reproducible."""

    if "notebooks" not in p:
        return DimensionResult(None, "insufficient data: provide notebooks")
    notebooks = as_list(p.get("notebooks"))
    if not notebooks:
        return DimensionResult(0, "no notebooks to assess")

    good = sum(1 for nb in notebooks if get_bool(as_dict(nb).get("reproducible")))
    ratio = share(good, len(notebooks))
    return DimensionResult(
        clamp_score(ratio * 5), "share of reproducible notebooks"
    )


def score_professional_narrative(p: Dict[str, Any]) -> DimensionResult:
    """Bio, professional summary flag, and at least one external link."""

    relevant_keys = ("bio", "professional_summary_present", "external_links")
    if not any(k in p for k in relevant_keys):
        return DimensionResult(
            None,
            "insufficient data: provide bio, professional_summary_present "
            "or external_links",
        )

    links = as_dict(p.get("external_links"))
    has_link = any(
        non_empty_str(links.get(k)) for k in ("github", "linkedin", "website")
    ) or get_bool(links.get("cv_or_summary"))

    score = 0.0
    if non_empty_str(p.get("bio")):
        score += 2
    if get_bool(p.get("professional_summary_present")):
        score += 2
    if has_link:
        score += 1
    return DimensionResult(clamp_score(score), "narrative and supporting links")


def score_recruiter_signals(p: Dict[str, Any]) -> DimensionResult:
    """GitHub and LinkedIn present, professional summary, and any medal."""

    relevant_keys = (
        "external_links",
        "professional_summary_present",
        "competitions",
    )
    if not any(k in p for k in relevant_keys):
        return DimensionResult(
            None,
            "insufficient data: provide external_links, "
            "professional_summary_present or competitions",
        )

    links = as_dict(p.get("external_links"))
    has_github = non_empty_str(links.get("github"))
    has_linkedin = non_empty_str(links.get("linkedin"))
    competitions = as_list(p.get("competitions"))
    has_medal = any(
        non_empty_str(as_dict(c).get("medal")) for c in competitions
    )

    score = 0.0
    if has_github:
        score += 1.5
    if has_linkedin:
        score += 1.5
    if get_bool(p.get("professional_summary_present")):
        score += 1
    if has_medal:
        score += 1
    return DimensionResult(clamp_score(score), "signals recruiters look for")


def score_external_consistency(p: Dict[str, Any]) -> DimensionResult:
    """Presence of GitHub and LinkedIn only. Real consistency needs review."""

    if "external_links" not in p:
        return DimensionResult(
            None, "insufficient data: provide external_links"
        )
    links = as_dict(p.get("external_links"))
    has_github = non_empty_str(links.get("github"))
    has_linkedin = non_empty_str(links.get("linkedin"))

    score = 0.0
    if has_github:
        score += 2.5
    if has_linkedin:
        score += 2.5
    note = "presence only; verify content matches manually"
    return DimensionResult(clamp_score(score), note)


def score_recent_activity(p: Dict[str, Any]) -> DimensionResult:
    """Recency of activity: <=30 days high, 31-90 medium, >90 low."""

    if "recent_activity_days" not in p:
        return DimensionResult(
            None, "insufficient data: provide recent_activity_days"
        )
    days = p.get("recent_activity_days")
    if not isinstance(days, (int, float)):
        return DimensionResult(
            None, "insufficient data: recent_activity_days must be a number"
        )
    if days < 0:
        days = 0
    if days <= 30:
        return DimensionResult(5, "active within the last 30 days")
    if days <= 90:
        return DimensionResult(3, "active within the last 31-90 days")
    return DimensionResult(1, "no activity in the last 90 days")


def score_specialization(p: Dict[str, Any]) -> DimensionResult:
    """1-2 focused specialties is best, 0 is low, 5+ is diluted."""

    if "specialties" not in p:
        return DimensionResult(None, "insufficient data: provide specialties")
    specialties = as_list(p.get("specialties"))
    count = len(specialties)
    if count == 0:
        return DimensionResult(1, "no declared specialty")
    if count <= 2:
        return DimensionResult(5, "focused specialization")
    if count <= 4:
        return DimensionResult(3, "somewhat broad focus")
    return DimensionResult(2, "focus diluted across many topics")


def score_community_contribution(p: Dict[str, Any]) -> DimensionResult:
    """Discussions count, when present."""

    if "discussions_count" not in p:
        return DimensionResult(
            None, "insufficient data: provide discussions_count"
        )
    count = p.get("discussions_count")
    if not isinstance(count, (int, float)):
        return DimensionResult(
            None, "insufficient data: discussions_count must be a number"
        )
    if count < 0:
        count = 0
    if count == 0:
        return DimensionResult(0, "no discussion activity")
    if count <= 5:
        return DimensionResult(2, "some discussion activity")
    if count <= 20:
        return DimensionResult(4, "regular discussion activity")
    return DimensionResult(5, "strong discussion activity")


# Ordered registry of dimensions. Order is fixed for deterministic output.
SCORERS: List[Tuple[str, Callable[[Dict[str, Any]], DimensionResult]]] = [
    ("positioning_clarity", score_positioning_clarity),
    ("technical_credibility", score_technical_credibility),
    ("notebook_quality", score_notebook_quality),
    ("dataset_quality", score_dataset_quality),
    ("competitions_progression", score_competitions_progression),
    ("reproducibility", score_reproducibility),
    ("professional_narrative", score_professional_narrative),
    ("recruiter_signals", score_recruiter_signals),
    ("external_consistency", score_external_consistency),
    ("recent_activity", score_recent_activity),
    ("specialization", score_specialization),
    ("community_contribution", score_community_contribution),
]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def score_profile(profile: Dict[str, Any]) -> Scorecard:
    """Score a profile dict across all dimensions and compute the overall.

    Dimensions that lack the required data are recorded with a None score and
    are excluded from the overall average.
    """

    p = as_dict(profile)
    card = Scorecard(username=p.get("username") if non_empty_str(p.get("username")) else None)

    scored_values: List[int] = []
    for name, scorer in SCORERS:
        try:
            result = scorer(p)
        except Exception:  # noqa: BLE001 - never let one scorer crash the run
            result = DimensionResult(None, "insufficient data: could not evaluate")
        card.dimensions[name] = result
        if result.score is not None:
            scored_values.append(result.score)

    card.scored_count = len(scored_values)
    if scored_values:
        card.overall = round(sum(scored_values) / len(scored_values), 1)
    else:
        card.overall = None
    return card


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


FOOTER_LINES = [
    "This scorecard is indicative only and is a diagnostic aid, not a verdict.",
    "Presentation is not the same as real skill; a reviewer must still read "
    "the actual work.",
    "No outcome (job, medal, ranking) is guaranteed by any score here.",
]


def render_markdown(card: Scorecard) -> str:
    """Render a scorecard as a deterministic Markdown report."""

    title_name = card.username if card.username else "profile"
    lines: List[str] = []
    lines.append("# Kaggle profile scorecard: " + title_name)
    lines.append("")
    lines.append("| Dimension | Score | Note |")
    lines.append("| --- | --- | --- |")
    for name, _ in SCORERS:
        result = card.dimensions.get(name)
        if result is None:
            score_cell = "n/a"
            note = "insufficient data"
        else:
            score_cell = (
                "insufficient data"
                if result.score is None
                else str(result.score) + "/5"
            )
            note = result.note
        lines.append("| " + name + " | " + score_cell + " | " + note + " |")
    lines.append("")
    overall_text = (
        "insufficient data" if card.overall is None else str(card.overall) + "/5"
    )
    lines.append("Overall: " + overall_text)
    lines.append(
        "Coverage: scored " + str(card.scored_count) + " of "
        + str(card.total) + " dimensions"
    )
    lines.append("")
    for footer in FOOTER_LINES:
        lines.append("> " + footer)
    return "\n".join(lines)


def card_to_dict(card: Scorecard) -> Dict[str, Any]:
    """Convert a scorecard to a plain dict for JSON output."""

    return {
        "username": card.username,
        "overall": card.overall,
        "scored_count": card.scored_count,
        "total": card.total,
        "dimensions": {
            name: {"score": res.score, "note": res.note}
            for name, res in card.dimensions.items()
        },
        "disclaimer": FOOTER_LINES,
    }


def render_json(card: Scorecard) -> str:
    """Render a scorecard as deterministic pretty JSON."""

    return json.dumps(card_to_dict(card), indent=2, sort_keys=True)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_profile(path: str) -> Dict[str, Any]:
    """Load a profile JSON file, raising ValueError on any user-facing error."""

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        raise ValueError("file not found: " + path)
    except IsADirectoryError:
        raise ValueError("path is a directory, not a file: " + path)
    except PermissionError:
        raise ValueError("permission denied reading: " + path)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid JSON in " + path + ": " + str(exc))
    except OSError as exc:
        raise ValueError("could not read " + path + ": " + str(exc))

    if not isinstance(data, dict):
        raise ValueError(
            "top-level JSON must be an object mapping fields to values"
        )
    return data


# ---------------------------------------------------------------------------
# Built-in sample and self-test
# ---------------------------------------------------------------------------


def sample_profile() -> Dict[str, Any]:
    """A representative profile used by the self-test (no external file needed)."""

    return {
        "username": "sample_user",
        "goal": "ml-engineer",
        "level": "contributor",
        "bio": (
            "Data scientist focused on tabular modeling and applied NLP, "
            "sharing reproducible notebooks and well-documented datasets."
        ),
        "specialties": ["tabular", "nlp"],
        "external_links": {
            "github": "https://github.com/sample_user",
            "linkedin": "https://linkedin.com/in/sample_user",
            "website": None,
            "cv_or_summary": True,
        },
        "notebooks": [
            {
                "title": "Tabular baseline",
                "upvotes": 12,
                "documented": True,
                "reproducible": True,
                "has_intro_conclusion": True,
            },
            {
                "title": "Quick EDA",
                "upvotes": 3,
                "documented": True,
                "reproducible": False,
                "has_intro_conclusion": False,
            },
        ],
        "datasets": [
            {
                "title": "Cleaned sales data",
                "documented": True,
                "has_usage_example": True,
            }
        ],
        "competitions": [
            {
                "name": "Tabular Playground",
                "rank_percentile": 12,
                "medal": "bronze",
                "writeup": True,
            },
            {
                "name": "NLP Challenge",
                "rank_percentile": 40,
                "medal": None,
                "writeup": False,
            },
        ],
        "recent_activity_days": 20,
        "professional_summary_present": True,
        "discussions_count": 7,
    }


def run_self_test() -> bool:
    """Run invariant checks against the built-in sample. Return True on pass."""

    card = score_profile(sample_profile())

    # Invariant 1: all 12 dimensions are present.
    if set(card.dimensions.keys()) != {name for name, _ in SCORERS}:
        return False
    if len(card.dimensions) != TOTAL_DIMENSIONS:
        return False

    # Invariant 2: every scored dimension is an int within 0..5.
    for result in card.dimensions.values():
        if result.score is not None:
            if not isinstance(result.score, int):
                return False
            if result.score < 0 or result.score > 5:
                return False
        if not non_empty_str(result.note):
            return False

    # Invariant 3: the sample is rich, so every dimension should be scorable.
    if card.scored_count != TOTAL_DIMENSIONS:
        return False

    # Invariant 4: overall exists and stays within range.
    if card.overall is None:
        return False
    if not (0.0 <= card.overall <= 5.0):
        return False

    # Invariant 5: an empty profile must not crash and must yield no scores.
    empty_card = score_profile({})
    if empty_card.scored_count != 0:
        return False
    if empty_card.overall is not None:
        return False
    for result in empty_card.dimensions.values():
        if result.score is not None:
            return False

    # Invariant 6: clamping holds for extreme inputs.
    if clamp_score(999) != 5 or clamp_score(-999) != 0:
        return False

    # Invariant 7: rendering never raises for either card.
    render_markdown(card)
    render_json(card)
    render_markdown(empty_card)

    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the CLI."""

    parser = argparse.ArgumentParser(
        prog="score_profile",
        description=(
            "Compute an indicative 0-5 scorecard for a Kaggle profile from a "
            "local JSON file. Diagnostic aid only; no outcome is guaranteed."
        ),
    )
    parser.add_argument(
        "json_path",
        nargs="?",
        default=None,
        help="path to a profile JSON file",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run built-in invariant checks and exit (no file needed)",
    )
    parser.add_argument(
        "--json-out",
        action="store_true",
        help="print machine-readable JSON instead of Markdown",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point. Return a process exit code (0 on success)."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.self_test:
        passed = run_self_test()
        print("PASS" if passed else "FAIL")
        return 0 if passed else 1

    if not args.json_path:
        parser.print_usage()
        print(
            "error: provide a json_path or use --self-test",
            file=sys.stderr,
        )
        return 2

    try:
        profile = load_profile(args.json_path)
    except ValueError as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 1

    card = score_profile(profile)
    if args.json_out:
        print(render_json(card))
    else:
        print(render_markdown(card))
    return 0


if __name__ == "__main__":
    sys.exit(main())
