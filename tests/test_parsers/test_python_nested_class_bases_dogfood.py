"""Golden call-edge labels for eager nested class base expressions.

Python evaluates class base and metaclass expressions in the enclosing scope
at class-definition time. Methods remain deferred, and parameters shadow
same-module functions. These labels concern call-graph coverage, not
architecture-policy violations.
"""

from arcade_agent.parsers.python import PythonParser


def _calls(tmp_path, source: str) -> set[tuple[str, str]]:
    path = tmp_path / "app.py"
    path.write_text(source, encoding="utf-8")
    graph = PythonParser().parse([path], tmp_path)
    return {
        (caller, callee)
        for caller, callee, relation in graph.to_edge_tuples()
        if relation == "calls"
    }


def test_nested_class_base_call_is_eager_in_enclosing_function(tmp_path):
    source = (
        "def helper():\n    return object\n\n"
        "def parent():\n"
        "    class Child(helper()):\n"
        "        pass\n"
        "    return Child\n"
    )
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}


def test_nested_class_metaclass_argument_is_eager(tmp_path):
    source = (
        "def helper():\n    return type\n\n"
        "def parent():\n"
        "    class Child(metaclass=helper()):\n"
        "        pass\n"
        "    return Child\n"
    )
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}


def test_nested_class_decorator_call_stays_visible(tmp_path):
    source = (
        "def helper():\n    return 1\n\n"
        "def parent():\n"
        "    @unknown_decorator(helper())\n"
        "    class Child:\n"
        "        pass\n"
        "    return Child\n"
    )
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}


def test_nested_class_method_is_deferred_and_base_shadowing_is_respected(tmp_path):
    source = (
        "def helper():\n    return object\n\n"
        "def deferred():\n"
        "    class Child:\n"
        "        def method(self):\n"
        "            return helper()\n"
        "    return Child\n\n"
        "def shadowed(helper):\n"
        "    class Child(helper()):\n"
        "        pass\n"
        "    return Child\n"
    )
    assert _calls(tmp_path, source) == set()
