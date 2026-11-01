"""Golden fixtures for Python 3 comprehension-local call bindings.

A comprehension loop target is local to its implicit scope.
It must not invent a same-module call edge or suppress a real outer call.
These are graph facts, not architecture verdicts or production FP rates.
"""

from arcade_agent.parsers.python import PythonParser


def _call_edges(tmp_path, source: str) -> set[tuple[str, str]]:
    path = tmp_path / "app.py"
    path.write_text(source, encoding="utf-8")
    graph = PythonParser().parse([path], tmp_path)
    return {
        (src, dst)
        for src, dst, relation in graph.to_edge_tuples()
        if relation == "calls"
    }


def test_comprehension_target_does_not_link_to_module_function(tmp_path):
    edges = _call_edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def shadowed(values):\n"
        "    return [helper() for helper in values]\n\n"
        "def unshadowed(values):\n"
        "    return [helper() for value in values]\n"
    ))
    assert edges == {("app.unshadowed", "app.helper")}


def test_comprehension_binding_does_not_leak_into_outer_scope(tmp_path):
    edges = _call_edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def outer(values):\n"
        "    values = [value for helper in values]\n"
        "    return helper()\n"
    ))
    assert edges == {("app.outer", "app.helper")}


def test_nested_generator_and_destructured_targets_are_scoped(tmp_path):
    edges = _call_edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def nested(groups):\n"
        "    return [[helper() for helper in group] for group in groups]\n\n"
        "def generator(values):\n"
        "    return (helper() for helper in values)\n\n"
        "def destructured(pairs):\n"
        "    return [helper() for helper, item in pairs]\n\n"
        "def unrelated(groups):\n"
        "    return [[helper() for value in group] for group in groups]\n"
    ))
    assert edges == {("app.unrelated", "app.helper")}
