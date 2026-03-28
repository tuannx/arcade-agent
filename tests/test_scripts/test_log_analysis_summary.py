"""Tests for scripts/log_analysis_summary.py."""

import json
import sys
from pathlib import Path

import pytest

# Make scripts importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from log_analysis_summary import _quality_label, _rci_icon, _severity_icon, _write_step_summary

# ── helper function tests ──────────────────────────────────────────────────────


def test_rci_icon_good():
    assert _rci_icon(0.8) == "🟢"
    assert _rci_icon(1.0) == "🟢"


def test_rci_icon_fair():
    assert _rci_icon(0.6) == "🟡"
    assert _rci_icon(0.79) == "🟡"


def test_rci_icon_poor():
    assert _rci_icon(0.0) == "🔴"
    assert _rci_icon(0.59) == "🔴"


def test_quality_label_good():
    assert _quality_label(0.8) == "Good"
    assert _quality_label(0.9) == "Good"


def test_quality_label_fair():
    assert _quality_label(0.6) == "Fair"
    assert _quality_label(0.7) == "Fair"


def test_quality_label_poor():
    assert _quality_label(0.5) == "Poor"
    assert _quality_label(0.0) == "Poor"


def test_severity_icon():
    assert _severity_icon("high") == "🔴"
    assert _severity_icon("medium") == "🟡"
    assert _severity_icon("low") == "🟢"
    assert _severity_icon("other") == "⚪"


# ── step summary writing ───────────────────────────────────────────────────────


@pytest.fixture
def sample_results() -> dict:
    return {
        "num_components": 8,
        "num_entities": 115,
        "num_edges": 119,
        "components": [
            {"name": "Algorithms", "num_entities": 42},
            {"name": "Parsers", "num_entities": 26},
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
            }
        ],
    }


def test_write_step_summary_creates_file(tmp_path, sample_results):
    out = tmp_path / "summary.md"
    rci = sample_results["metrics"]["RCI"]
    turbo_mq = sample_results["metrics"]["TurboMQ"]
    _write_step_summary(
        out,
        sample_results,
        rci,
        turbo_mq,
        sample_results["smells"],
        sample_results["components"],
        sample_results["metrics"],
    )
    assert out.exists()
    content = out.read_text()
    assert "Architecture Analysis Results" in content
    assert "Components" in content
    assert "ConcernOverload" in content


def test_write_step_summary_no_smells(tmp_path, sample_results):
    out = tmp_path / "summary.md"
    rci = 0.9
    turbo_mq = 0.5
    _write_step_summary(
        out,
        sample_results,
        rci,
        turbo_mq,
        smells=[],
        components=sample_results["components"],
        metrics={"RCI": 0.9, "TurboMQ": 0.5},
    )
    content = out.read_text()
    assert "No architectural smells detected" in content


def test_write_step_summary_appends(tmp_path, sample_results):
    """Multiple writes should append, not overwrite."""
    out = tmp_path / "summary.md"
    out.write_text("EXISTING CONTENT\n")
    rci = sample_results["metrics"]["RCI"]
    turbo_mq = sample_results["metrics"]["TurboMQ"]
    _write_step_summary(
        out,
        sample_results,
        rci,
        turbo_mq,
        sample_results["smells"],
        sample_results["components"],
        sample_results["metrics"],
    )
    content = out.read_text()
    assert "EXISTING CONTENT" in content
    assert "Architecture Analysis Results" in content


# ── end-to-end: main() with a real JSON file ──────────────────────────────────


def test_main_runs_without_error(tmp_path, sample_results, capsys):
    """main() should print the box-drawing table without raising."""
    results_file = tmp_path / "results.json"
    results_file.write_text(json.dumps(sample_results))

    original_argv = sys.argv
    try:
        sys.argv = ["log_analysis_summary.py", str(results_file)]
        from log_analysis_summary import main
        main()
    finally:
        sys.argv = original_argv

    captured = capsys.readouterr()
    assert "ARCADE AGENT" in captured.out
    assert "QUALITY METRICS" in captured.out
    assert "COMPONENTS" in captured.out
    assert "ARCHITECTURAL SMELLS" in captured.out
