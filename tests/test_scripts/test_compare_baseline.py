"""Tests for scripts/compare_baseline.py."""

import sys
from pathlib import Path

import pytest

# Make scripts importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from compare_baseline import _delta, _quality_label, _rci_icon, _severity_icon, build_comment

# ── helper function tests ──────────────────────────────────────────────────────


def test_delta_increase():
    assert "↑" in _delta(0.6, 0.5)
    assert "+0.1000" in _delta(0.6, 0.5)


def test_delta_decrease():
    assert "↓" in _delta(0.4, 0.5)
    assert "-0.1000" in _delta(0.4, 0.5)


def test_delta_no_change():
    assert "no change" in _delta(0.5, 0.5)
    assert "no change" in _delta(0.5001, 0.5)  # within epsilon


def test_rci_icon():
    assert _rci_icon(0.9) == "🟢"
    assert _rci_icon(0.8) == "🟢"
    assert _rci_icon(0.7) == "🟡"
    assert _rci_icon(0.6) == "🟡"
    assert _rci_icon(0.5) == "🔴"
    assert _rci_icon(0.0) == "🔴"


def test_quality_label():
    assert _quality_label(0.8) == "Good"
    assert _quality_label(0.9) == "Good"
    assert _quality_label(0.6) == "Fair"
    assert _quality_label(0.7) == "Fair"
    assert _quality_label(0.5) == "Poor"
    assert _quality_label(0.0) == "Poor"


def test_severity_icon():
    assert _severity_icon("high") == "🔴"
    assert _severity_icon("medium") == "🟡"
    assert _severity_icon("low") == "🟢"
    assert _severity_icon("unknown") == "⚪"


# ── build_comment without baseline ────────────────────────────────────────────


@pytest.fixture
def sample_current() -> dict:
    return {
        "timestamp": "2026-01-01T00:00:00Z",
        "commit_sha": "abc1234",
        "num_components": 8,
        "num_entities": 115,
        "num_edges": 119,
        "components": [
            {"name": "Algorithms", "num_entities": 42},
            {"name": "Parsers", "num_entities": 26},
            {"name": "Tools", "num_entities": 19},
        ],
        "metrics": {
            "RCI": 0.5294,
            "TurboMQ": 0.2484,
            "BasicMQ": 0.2484,
        },
        "smells": [
            {
                "smell_type": "ConcernOverload",
                "severity": "high",
                "affected_components": ["Algorithms"],
                "description": "Too many responsibilities",
            }
        ],
    }


def test_build_comment_without_baseline(sample_current):
    comment = build_comment(sample_current, baseline=None)

    assert "## 🤖 Architecture Analysis Summary" in comment
    assert "Current Architecture" in comment
    assert "**8**" in comment   # num_components
    assert "**115**" in comment  # num_entities
    assert "**119**" in comment  # num_edges
    assert "0.5294" in comment   # RCI
    assert "ConcernOverload" in comment
    assert "No baseline available" in comment


def test_build_comment_shows_all_components(sample_current):
    comment = build_comment(sample_current, baseline=None)

    assert "Algorithms" in comment
    assert "Parsers" in comment
    assert "Tools" in comment


def test_build_comment_run_url(sample_current):
    url = "https://github.com/example/repo/actions/runs/123"
    comment = build_comment(sample_current, baseline=None, run_url=url)
    assert url in comment


# ── build_comment with baseline ───────────────────────────────────────────────


@pytest.fixture
def sample_baseline() -> dict:
    return {
        "commit_sha": "def5678abc",
        "num_components": 7,
        "num_entities": 110,
        "num_edges": 112,
        "metrics": {
            "RCI": 0.51,
            "TurboMQ": 0.23,
            "BasicMQ": 0.23,
        },
        "smells": [],
    }


def test_build_comment_with_baseline_shows_evolution(sample_current, sample_baseline):
    comment = build_comment(sample_current, baseline=sample_baseline)

    assert "Evolution vs Baseline" in comment
    assert "def5678" in comment  # baseline commit sha (first 7 chars)
    # Current vs baseline deltas
    assert "↑" in comment  # metrics improved


def test_build_comment_with_baseline_shows_smell_changes(sample_current, sample_baseline):
    comment = build_comment(sample_current, baseline=sample_baseline)

    # sample_current has a smell that sample_baseline doesn't → "New smell"
    assert "New smell" in comment
    assert "ConcernOverload" in comment


def test_build_comment_with_baseline_resolved_smells(sample_baseline):
    """When current has no smells but baseline did, show resolved."""
    current = {
        "num_components": 7,
        "num_entities": 110,
        "num_edges": 112,
        "components": [],
        "metrics": {"RCI": 0.8, "TurboMQ": 0.5},
        "smells": [],
    }
    baseline = {
        "commit_sha": "aaa111",
        "num_components": 7,
        "num_entities": 110,
        "num_edges": 112,
        "metrics": {"RCI": 0.75, "TurboMQ": 0.45},
        "smells": [
            {"smell_type": "CyclicDependency", "severity": "high", "affected_components": []}
        ],
    }
    comment = build_comment(current, baseline=baseline)
    assert "Resolved" in comment
    assert "CyclicDependency" in comment


def test_build_comment_stable_rci_trend(sample_baseline):
    """When RCI change is within ±0.01, trend is Stable."""
    current = {
        "num_components": 7,
        "num_entities": 110,
        "num_edges": 112,
        "components": [],
        "metrics": {"RCI": 0.515, "TurboMQ": 0.23},
        "smells": [],
    }
    baseline = dict(sample_baseline)
    baseline["metrics"] = {"RCI": 0.51, "TurboMQ": 0.23}
    comment = build_comment(current, baseline=baseline)
    assert "Stable" in comment


def test_build_comment_no_smells(sample_current):
    current = dict(sample_current)
    current["smells"] = []
    comment = build_comment(current, baseline=None)
    assert "No architectural smells detected" in comment
