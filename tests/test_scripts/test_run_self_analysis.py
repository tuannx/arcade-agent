"""Integration tests for scripts/run_self_analysis.py.

These tests run the self-analysis pipeline on the actual codebase to verify
that all stages (ingest → parse → recover → detect_smells → compute_metrics
→ visualize) complete without errors and produce the expected outputs.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT = REPO_ROOT / "scripts" / "run_self_analysis.py"


def _run_script(tmp_path, *, check: bool = True, text: bool = False):
    """Helper to invoke run_self_analysis.py with standard output paths."""
    json_out = tmp_path / "results.json"
    html_out = tmp_path / "report.html"
    args = [
        sys.executable,
        str(SCRIPT),
        "--output-json",
        str(json_out),
        "--output-html",
        str(html_out),
    ]
    result = subprocess.run(args, capture_output=True, text=text, check=check)
    return result, json_out, html_out


def test_run_self_analysis_produces_json(tmp_path):
    """The script should produce a valid JSON results file."""
    result, json_out, _ = _run_script(tmp_path, check=False, text=True)
    assert result.returncode == 0, f"Script failed:\n{result.stdout}\n{result.stderr}"
    assert json_out.exists(), "JSON output file not created"


def test_run_self_analysis_json_schema(tmp_path):
    """The JSON results file should contain all required fields."""
    _, json_out, _ = _run_script(tmp_path)

    data = json.loads(json_out.read_text())
    required_keys = {
        "timestamp",
        "commit_sha",
        "ref",
        "algorithm",
        "num_components",
        "num_entities",
        "num_edges",
        "components",
        "metrics",
        "smells",
    }
    assert required_keys.issubset(data.keys()), f"Missing keys: {required_keys - data.keys()}"


def test_run_self_analysis_positive_counts(tmp_path):
    """The codebase should yield at least some entities and components."""
    _, json_out, _ = _run_script(tmp_path)

    data = json.loads(json_out.read_text())
    assert data["num_entities"] > 0, "Expected at least one entity"
    assert data["num_components"] > 0, "Expected at least one component"
    assert len(data["components"]) == data["num_components"]


def test_run_self_analysis_metrics_present(tmp_path):
    """The results should include the standard quality metrics."""
    _, json_out, _ = _run_script(tmp_path)

    data = json.loads(json_out.read_text())
    assert "RCI" in data["metrics"]
    assert "TurboMQ" in data["metrics"]
    for val in data["metrics"].values():
        assert isinstance(val, (int, float))


def test_run_self_analysis_produces_html(tmp_path):
    """The script should produce a non-empty HTML report."""
    _, json_out, html_out = _run_script(tmp_path)

    assert html_out.exists(), "HTML output file not created"
    assert html_out.stat().st_size > 0, "HTML file is empty"
    content = html_out.read_text()
    assert "<html" in content.lower()
