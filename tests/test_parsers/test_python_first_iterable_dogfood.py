"""Regression fixtures for the first iterable of a Python comprehension.

Python evaluates the outermost iterable in the *enclosing* scope, before
binding the comprehension targets. Later clauses and the result expression
use comprehension-local targets. These are graph facts, not verified smells.
"""

from arcade_agent.parsers.python import PythonParser


def _calls(tmp_path, source: str) -> set[tuple[str, str]]:
    path = tmp_path / "app.py"
    path.write_text(source, encoding="utf-8")
    graph = PythonParser().parse([path], tmp_path)
    return {
        (src, dst)
        for src, dst, relation in graph.to_edge_tuples()
        if relation == "calls"
    }


def test_first_iterable_uses_enclosing_scope_across_comprehension_kinds(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return [1, 2]\n\n"
        "def as_list():\n    return [helper for helper in helper()]\n\n"
        "def as_set():\n    return {helper for helper in helper()}\n\n"
        "def as_dict():\n    return {helper: helper for helper in helper()}\n\n"
        "def as_generator():\n    return (helper for helper in helper())\n"
    ))
    assert edges == {
        ("app.as_list", "app.helper"),
        ("app.as_set", "app.helper"),
        ("app.as_dict", "app.helper"),
        ("app.as_generator", "app.helper"),
    }


def test_first_iterable_is_global_but_element_and_later_clauses_are_local(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return [lambda: 1]\n\n"
        "def element(values):\n    return [helper() for helper in helper()]\n\n"
        "def later(values):\n"
        "    return [item for helper in helper() for item in helper()]\n\n"
        "def guard(values):\n"
        "    return [helper for helper in helper() if helper()]\n"
    ))
    assert edges == {
        ("app.element", "app.helper"),
        ("app.later", "app.helper"),
        ("app.guard", "app.helper"),
    }


def test_nested_first_iterable_inherits_outer_comprehension_binding(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return [1]\n\n"
        "def nested(groups):\n"
        "    return [[item for item in helper()] for helper in groups]\n\n"
        "def unshadowed(groups):\n"
        "    return [[item for item in helper()] for group in groups]\n\n"
        "def second_clause(groups):\n"
        "    return [item for helper in groups for item in helper()]\n"
    ))
    assert edges == {("app.unshadowed", "app.helper")}



def test_first_iterable_cache_is_stable_and_local_targets_do_not_leak(tmp_path):
    """First-iterable true calls survive direct, cold and warm cache parses."""
    from arcade_agent.tools.parse import parse

    path = tmp_path / "app.py"
    path.write_text(
        "def helper():\n    return [1, 2]\n\n"
        "def first(values):\n"
        "    return [helper for helper in helper()]\n\n"
        "def shadowed_later(values):\n"
        "    return [item for helper in values for item in helper()]\n\n"
        "def shadowed_nested(values):\n"
        "    return [[item for item in helper()] for helper in values]\n\n"
        "def unshadowed_nested(values):\n"
        "    return [[item for item in helper()] for group in values]\n\n"
        "def does_not_leak(values):\n"
        "    _ = [item for helper in values for item in [1]]\n"
        "    return helper()\n",
        encoding="utf-8",
    )
    expected = {
        ("app.first", "app.helper"),
        ("app.unshadowed_nested", "app.helper"),
        ("app.does_not_leak", "app.helper"),
    }
    graphs = [
        PythonParser().parse([path], tmp_path),
        parse(str(tmp_path), language="python", use_cache=True),
        parse(str(tmp_path), language="python", use_cache=True),
    ]
    for graph in graphs:
        edges = {
            (src, dst)
            for src, dst, relation in graph.to_edge_tuples()
            if relation == "calls"
        }
        assert edges == expected
