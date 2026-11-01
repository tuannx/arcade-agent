"""Dogfood regression: Python import-only graphs must not assert cohesive evidence.

A SHA-pinned arcade-agent self-run reported a medium Concern Overload for
Tools (26 entities, two internal imports). Python's linker only emits imports
and inheritance, not internal calls; the missing calls can explain sparsity.
"""

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.algorithms.concern import detect_concern_overload
from arcade_agent.algorithms.coupling import compute_balanced_scores
from arcade_agent.algorithms.smells import SmellType
from arcade_agent.parsers.python import PythonParser
from arcade_agent.tools.detect_smells import detect_smells


def _real_python_graph(tmp_path):
    source = tmp_path / "tools.py"
    source.write_text(
        "".join(f"def step{i}():\n    return {i}\n\n" for i in range(26)),
        encoding="utf-8",
    )
    graph = PythonParser().parse([source], tmp_path)
    assert len(graph.entities) >= 26
    architecture = Architecture(components=[
        Component(name="Tools", responsibility="", entities=list(graph.entities))
    ], algorithm="pkg")
    return architecture, graph


def _derived_scores(architecture, graph, smells):
    metrics, signals, _ = compute_balanced_scores(architecture, graph, smells)
    return {metric.name: metric.value for metric in metrics}, signals


def test_python_parser_explicitly_declares_uncollected_calls(tmp_path):
    _, graph = _real_python_graph(tmp_path)
    assert graph.relation_coverage()["python"] == {
        "collected_relations": ["extends", "import"],
        "call_coverage": "not_collected",
    }
    assert all(edge.relation in {"import", "extends"} for edge in graph.edges)


def test_sparse_python_tools_is_a_low_severity_coverage_warning(tmp_path):
    architecture, graph = _real_python_graph(tmp_path)
    finding, = detect_concern_overload(architecture, graph)
    assert finding["component"] == "Tools"
    assert finding["coverage_status"] == "insufficient"
    assert finding["incomplete_call_languages"] == ["python"]
    assert finding["severity"] == "low"
    smell, = [
        item for item in detect_smells(architecture, graph)
        if item.smell_type == SmellType.CONCERN_OVERLOAD
    ]
    assert "insufficient coverage" in smell.description
    assert "multiple responsibilities have not been established" in smell.explanation
    assert smell.scoring_eligible is False


def test_unverified_coverage_warning_does_not_change_quality_score(tmp_path):
    architecture, graph = _real_python_graph(tmp_path)
    warnings = [
        item for item in detect_smells(architecture, graph)
        if item.smell_type == SmellType.CONCERN_OVERLOAD
    ]
    assert len(warnings) == 1
    assert _derived_scores(architecture, graph, warnings) == _derived_scores(
        architecture, graph, [],
    )
