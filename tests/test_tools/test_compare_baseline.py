"""Tests for baseline comparison reporting."""

import importlib.util
from pathlib import Path

from arcade_agent.exporters.html import export_evolution_html

_COMPARE_BASELINE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "compare_baseline.py"
_COMPARE_BASELINE_SPEC = importlib.util.spec_from_file_location(
    "compare_baseline",
    _COMPARE_BASELINE_PATH,
)
assert _COMPARE_BASELINE_SPEC and _COMPARE_BASELINE_SPEC.loader
_COMPARE_BASELINE_MODULE = importlib.util.module_from_spec(_COMPARE_BASELINE_SPEC)
_COMPARE_BASELINE_SPEC.loader.exec_module(_COMPARE_BASELINE_MODULE)
build_report_payload = _COMPARE_BASELINE_MODULE.build_report_payload


def _snapshot(commit_sha: str, component_name: str, classes: int, methods: int) -> dict:
    return {
        "commit_sha": commit_sha,
        "algorithm": "pkg",
        "num_components": 1,
        "num_entities": 1,
        "num_edges": 0,
        "source_num_entities": 1 + methods,
        "class_count": classes,
        "function_count": 0,
        "method_count": methods,
        "component_dependencies": [],
        "components": [
            {
                "name": component_name,
                "responsibility": component_name,
                "num_entities": 1,
                "class_count": classes,
                "function_count": 0,
                "method_count": methods,
                "entity_kind_counts": {"class": classes, "method": methods},
                "entities": [f"pkg.{component_name}"],
            }
        ],
        "metrics": {"RCI": 0.7, "TurboMQ": 0.4},
        "smells": [],
    }


def test_build_report_payload_tracks_component_and_method_deltas():
    baseline = _snapshot("abc1234", "Core", 1, 2)
    current = _snapshot("def5678", "Core", 1, 4)

    report = build_report_payload(current, baseline, run_url="https://example.test/run")

    assert report["overview_cards"][0]["value"] == 1
    assert any(row["name"] == "Methods" and row["delta"] == "+2" for row in report["metric_rows"])
    assert report["component_rows"][0]["status"] == "matched"
    assert "+2" in report["component_rows"][0]["methods"]


def test_export_evolution_html_writes_report(tmp_path: Path):
    baseline = _snapshot("abc1234", "Core", 1, 1)
    current = _snapshot("def5678", "Core", 1, 2)
    report = build_report_payload(current, baseline)

    output = tmp_path / "comparison.html"
    export_evolution_html(report, output)

    content = output.read_text()
    assert "Architecture Evolution Report" in content
    assert "Core" in content
    assert "Methods" in content
