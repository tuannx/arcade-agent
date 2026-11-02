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
