"""Golden regression for distinct, SHA-pinned source and analyzer HTML provenance."""

import json
import sys

from arcade_agent.ci.run_self_analysis import main as run_self_analysis
from arcade_agent.exporters.html import export_html

SOURCE_SHA = "5a4ba4d33dfd88a90fd6ec749894fd0088baf1d9"
ANALYZER_SHA = "0bb63a0c9879b3c7db47752913d181cb1d599f4c"


def test_html_report_displays_separate_exact_commits(
    tmp_path, sample_architecture, sample_graph,
):
    """A local-looking version label must not hide verified source identity."""
    path = tmp_path / "report.html"
    export_html(
        "source-target", "local", sample_graph, sample_architecture, [], [], path,
        source_commit_sha=SOURCE_SHA,
        analyzer_commit_sha=ANALYZER_SHA,
    )

    html = path.read_text()
    assert "Source commit" in html
    assert SOURCE_SHA in html
    assert "Analyzer commit" in html
    assert ANALYZER_SHA in html
    assert "version local" not in html


def test_self_analysis_html_and_json_share_exact_provenance(tmp_path, monkeypatch):
    """The normal self-analysis entry point must forward resolved SHAs to HTML."""
    source = tmp_path / "target"
    source.mkdir()
    (source / "app.py").write_text(
        "def helper():\n    return 1\n\ndef run():\n    return helper()\n"
    )
    json_path = tmp_path / "analysis.json"
    html_path = tmp_path / "report.html"
    monkeypatch.setattr(
        "arcade_agent.ci.run_self_analysis.resolve_source_commit",
        lambda _source, _expected: SOURCE_SHA,
    )
    monkeypatch.setattr(
        "arcade_agent.ci.run_self_analysis.resolve_analyzer_commit",
        lambda _source, _expected: ANALYZER_SHA,
    )
    monkeypatch.setattr(
        sys, "argv", [
            "arcade-self-analysis", "--source", str(source), "--language", "python",
            "--output-json", str(json_path), "--output-html", str(html_path),
        ],
    )

    run_self_analysis()

    payload = json.loads(json_path.read_text())
    assert payload["commit_sha"] == SOURCE_SHA
    assert payload["analyzer_commit_sha"] == ANALYZER_SHA
    html = html_path.read_text()
    assert f"Source commit" in html
    assert SOURCE_SHA in html
    assert "Analyzer commit" in html
    assert ANALYZER_SHA in html
    assert "version local" not in html
