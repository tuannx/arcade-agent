"""Hand-reviewed call-edge oracle from real Arcade parser production source.

This is an intentionally small, labelled *sample* of direct same-module
function calls and deliberately absent relationships. It is not an exhaustive
production precision/recall benchmark and does not verify architecture rules.
"""

from pathlib import Path

from arcade_agent.parsers.python import PythonParser


def test_real_parser_source_direct_call_oracle():
    repo_root = Path(__file__).resolve().parents[2]
    file = repo_root / "src/arcade_agent/parsers/python.py"
    graph = PythonParser().parse([file], repo_root)
    prefix = "src.arcade_agent.parsers.python."
    observed = {
        (caller.removeprefix(prefix), callee.removeprefix(prefix))
        for caller, callee, relation in graph.to_edge_tuples()
        if relation == "calls" and caller.startswith(prefix) and callee.startswith(prefix)
    }

    # These are direct call sites actually present in the pinned source file,
    # manually checked against its function bodies (14 positive pairs).
    positive = {
        ("_extract_classes", "_unwrap_decorated"),
        ("_extract_classes", "_get_text"),
        ("_extract_functions", "_unwrap_decorated"),
        ("_extract_functions", "_get_text"),
        ("_extract_methods", "_unwrap_decorated"),
        ("_extract_methods", "_get_text"),
        ("_extract_imports", "_imported_name"),
        ("_extract_imports", "_get_text"),
        ("_extract_unqualified_calls", "_binding_names"),
        ("_extract_unqualified_calls", "_parameter_binding_names"),
        ("_extract_unqualified_calls", "_comprehension_targets"),
        ("_extract_unqualified_calls", "_match_capture_names"),
        ("_extract_module_variables", "_get_text"),
        ("_extract_referenced_names", "_get_text"),
    }
    # The selected caller bodies do not call these same-module functions.
    # This is a curated negative control, not random or exhaustive sampling.
    negative = {
        ("_extract_classes", "_extract_methods"),
        ("_extract_imports", "_resolve_relative_imports"),
        ("_extract_functions", "_extract_classes"),
        ("_extract_methods", "_extract_imports"),
        ("_extract_unqualified_calls", "_extract_referenced_names"),
        ("_extract_module_variables", "_match_capture_names"),
    }
    assert not positive - observed, f"Missing hand-reviewed calls: {positive - observed}"
    assert not negative & observed, f"Spurious hand-reviewed calls: {negative & observed}"
