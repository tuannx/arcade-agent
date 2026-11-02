"""Golden call-edge fixtures for nested function definition-time defaults.

Python evaluates a nested def's default arguments while executing its
enclosing function, but not its nested body or lambda body. These labels
concern static call edges, not architectural violations.
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


def test_nested_function_default_runs_in_enclosing_scope(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def parent():\n"
        "    def child(value=helper()):\n"
        "        return value\n"
        "    return child\n"
    ))
    assert edges == {("app.parent", "app.helper")}


def test_nested_typed_default_runs_in_enclosing_scope(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def typed_parent():\n"
        "    def child(value: int = helper()):\n"
        "        return value\n"
        "    return child\n"
    ))
    assert edges == {("app.typed_parent", "app.helper")}


def test_deferred_nested_bodies_and_shadowed_defaults_are_not_calls(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def deferred():\n"
        "    def child():\n        return helper()\n"
        "    callback = lambda: helper()\n"
        "    return child, callback\n\n"
        "def parameter_shadow(helper):\n"
        "    def child(value=helper()):\n"
        "        return value\n"
        "    return child\n"
    ))
    assert edges == set()
