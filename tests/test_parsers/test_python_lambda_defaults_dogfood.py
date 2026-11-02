"""Golden labels for eager lambda defaults versus deferred lambda bodies.

A lambda's default expressions run when the lambda object is created.
Only explicit, unshadowed same-module calls are expected as graph edges.
These labels do not establish architecture violations.
"""

from arcade_agent.parsers.python import PythonParser


def _calls(tmp_path, source: str) -> set[tuple[str, str]]:
    file = tmp_path / "app.py"
    file.write_text(source, encoding="utf-8")
    graph = PythonParser().parse([file], tmp_path)
    return {
        (caller, callee)
        for caller, callee, relation in graph.to_edge_tuples()
        if relation == "calls"
    }


def test_lambda_default_is_evaluated_by_enclosing_function(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def parent():\n"
        "    callback = lambda value=helper(): value\n"
        "    return callback\n"
    ))
    assert edges == {("app.parent", "app.helper")}


def test_lambda_keyword_only_default_is_eager(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def parent():\n"
        "    callback = lambda *, value=helper(): value\n"
        "    return callback\n"
    ))
    assert edges == {("app.parent", "app.helper")}


def test_deferred_lambda_bodies_and_shadowed_defaults_remain_suppressed(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def deferred():\n"
        "    callback = lambda: helper()\n"
        "    return callback\n\n"
        "def shadowed(helper):\n"
        "    callback = lambda value=helper(): value\n"
        "    return callback\n\n"
        "def nested_deferred():\n"
        "    def child():\n"
        "        callback = lambda value=helper(): value\n"
        "        return callback\n"
        "    return child\n"
    ))
    assert edges == set()
