"""Golden labels: Python `del` targets bind in a function's local scope.

CPython compiles `del helper` as DELETE_FAST, not deletion of a module
function; subsequent `helper()` therefore does NOT call the module helper.
Attribute and subscript deletion are different: they do not bind the base name.
These are call-edge labels, not architecture-policy violations.
"""

import pytest

from arcade_agent.parsers.python import PythonParser


def _calls(tmp_path, source: str) -> set[tuple[str, str]]:
    path = tmp_path / "app.py"
    path.write_text(source, encoding="utf-8")
    graph = PythonParser().parse([path], tmp_path)
    assert graph.metadata["relation_coverage"]["python"]["call_coverage"] == "partial"
    return {
        (caller, callee)
        for caller, callee, relation in graph.to_edge_tuples()
        if relation == "calls"
    }


def test_del_local_name_does_not_call_module_function(tmp_path):
    source = (
        "def helper():\n    return 1\n\n"
        "def parent():\n"
        "    del helper\n"
        "    return helper()\n"
    )
    assert _calls(tmp_path, source) == set()
    namespace = {}
    exec(source, namespace)
    with pytest.raises(UnboundLocalError):
        namespace["parent"]()


def test_destructured_del_names_are_local_too(tmp_path):
    source = (
        "def helper():\n    return 1\n\n"
        "def parent():\n"
        "    del (helper, other)\n"
        "    return helper()\n"
    )
    assert _calls(tmp_path, source) == set()


def test_del_attribute_does_not_bind_base_identifier(tmp_path):
    source = (
        "def helper():\n    return 1\n\n"
        "def parent(holder):\n"
        "    del holder.helper\n"
        "    return helper()\n"
    )
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}


def test_del_subscript_does_not_bind_base_identifier(tmp_path):
    source = (
        "def helper():\n    return 1\n\n"
        "def parent(holder):\n"
        "    del holder[0]\n"
        "    return helper()\n"
    )
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}


def test_del_inside_nested_function_does_not_bind_parent(tmp_path):
    source = (
        "def helper():\n    return 1\n\n"
        "def parent():\n"
        "    def nested():\n"
        "        del helper\n"
        "        return helper()\n"
        "    return helper()\n"
    )
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}
