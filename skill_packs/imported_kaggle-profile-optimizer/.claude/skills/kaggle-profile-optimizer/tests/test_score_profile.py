"""Tests for score_profile.py.

Dependency-free (pytest only). The scripts directory is added to sys.path so
the module can be imported directly regardless of how pytest is invoked.
"""

import json
import os
import sys

# Make the sibling scripts directory importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_DIR = os.path.abspath(os.path.join(_HERE, "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import score_profile as sp  # noqa: E402


_EXAMPLE_PATH = os.path.abspath(
    os.path.join(_HERE, "..", "examples", "profile-input.example.json")
)

_EXPECTED_DIMENSIONS = {name for name, _ in sp.SCORERS}


def _load_example():
    with open(_EXAMPLE_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_example_returns_all_dimensions_and_valid_overall():
    """(a) Scoring the example yields all 12 dimensions and overall in [0, 5]."""
    profile = _load_example()
    card = sp.score_profile(profile)

    assert set(card.dimensions.keys()) == _EXPECTED_DIMENSIONS
    assert len(card.dimensions) == 12

    assert card.overall is not None
    assert 0.0 <= card.overall <= 5.0

    # Every scored dimension is an int within range; notes are never empty.
    for result in card.dimensions.values():
        if result.score is not None:
            assert isinstance(result.score, int)
            assert 0 <= result.score <= 5
        assert isinstance(result.note, str) and result.note.strip() != ""

    # The example is rich enough that every dimension is scorable.
    assert card.scored_count == 12


def test_clamp_keeps_scores_within_range():
    """(b) Extreme inputs stay within 0..5 after clamping."""
    assert sp.clamp_score(999) == 5
    assert sp.clamp_score(-999) == 0
    assert sp.clamp_score(2.6) == 3
    assert sp.clamp_score(0) == 0
    assert sp.clamp_score(5) == 5
    # Non-numeric input degrades to 0 rather than raising.
    assert sp.clamp_score("not-a-number") == 0

    # Extreme profile values must not push any dimension out of range.
    extreme = {
        "username": "x" * 500,
        "bio": "y" * 5000,
        "specialties": ["a"] * 50,
        "notebooks": [
            {
                "documented": True,
                "reproducible": True,
                "has_intro_conclusion": True,
            }
            for _ in range(1000)
        ],
        "datasets": [
            {"documented": True, "has_usage_example": True} for _ in range(1000)
        ],
        "competitions": [
            {"rank_percentile": -50, "medal": "gold"} for _ in range(1000)
        ],
        "recent_activity_days": -999,
        "professional_summary_present": True,
        "discussions_count": 10 ** 9,
        "external_links": {
            "github": "g",
            "linkedin": "l",
            "website": "w",
            "cv_or_summary": True,
        },
    }
    card = sp.score_profile(extreme)
    for result in card.dimensions.values():
        if result.score is not None:
            assert 0 <= result.score <= 5
    assert card.overall is not None
    assert 0.0 <= card.overall <= 5.0


def test_missing_data_yields_none_and_does_not_crash():
    """(c) A nearly-empty profile yields None for unscorable dimensions."""
    card = sp.score_profile({})

    assert set(card.dimensions.keys()) == _EXPECTED_DIMENSIONS
    assert card.scored_count == 0
    assert card.overall is None

    for result in card.dimensions.values():
        assert result.score is None
        assert "insufficient data" in result.note

    # Rendering an empty scorecard must also not crash.
    md = sp.render_markdown(card)
    assert "insufficient data" in md
    payload = json.loads(sp.render_json(card))
    assert payload["scored_count"] == 0
    assert payload["overall"] is None


def test_partial_profile_scores_some_dimensions():
    """A partial profile scores what it can and marks the rest insufficient."""
    card = sp.score_profile({"specialties": ["tabular"], "recent_activity_days": 5})
    assert card.dimensions["specialization"].score == 5
    assert card.dimensions["recent_activity"].score == 5
    assert card.dimensions["dataset_quality"].score is None
    assert card.scored_count >= 2


def test_self_test_reports_success():
    """(d) The built-in self-test function returns success."""
    assert sp.run_self_test() is True


def test_main_self_test_exit_code():
    """The CLI --self-test path returns exit code 0."""
    assert sp.main(["--self-test"]) == 0


def test_main_missing_args_is_non_zero():
    """No file and no --self-test is a usage error (non-zero exit)."""
    assert sp.main([]) != 0
