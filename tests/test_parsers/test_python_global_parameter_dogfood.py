"""Golden call-edge fixtures: globals, annotations and parameter defaults.

A global declaration resolves to module scope. An annotation or a parameter's
default expression does not bind an identifier in the called function's scope.
Local assignments and formal parameter names remain shadowing controls.
These assert graph edges, never verified architecture violations.
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


def test_global_declaration_still_calls_module_function(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def global_reader():\n"
        "    global helper\n"
        "    return helper()\n"
    ))
    assert edges == {("app.global_reader", "app.helper")}


def test_parameter_annotation_does_not_bind_module_function_name(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def annotated(value: helper):\n"
        "    return helper()\n"
    ))
    assert edges == {("app.annotated", "app.helper")}


def test_parameter_default_is_not_binding_but_real_parameters_are(tmp_path):
    edges = _calls(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def defaulted(value=helper):\n"
        "    return helper()\n\n"
        "def direct_parameter(helper):\n"
        "    return helper()\n\n"
        "def annotated_parameter(helper: int):\n"
        "    return helper()\n\n"
        "def assigned():\n"
        "    helper = lambda: 1\n"
        "    return helper()\n"
    ))
    assert edges == {("app.defaulted", "app.helper")}


def test_global_and_parameter_bindings_survive_direct_cold_warm_cache(tmp_path):
    """Four true calls and four shadowed controls on identical source bytes."""
    from arcade_agent.tools.parse import parse

    path = tmp_path / "app.py"
    path.write_text(
        "def helper():\n    return 1\n\n"
        "def read_global():\n    global helper\n    return helper()\n\n"
        "def typed_default(value: helper = helper):\n    return helper()\n\n"
        "def positional_default(value=helper, /):\n    return helper()\n\n"
        "def keyword_default(*, value: helper = helper):\n    return helper()\n\n"
        "def bound_positional(helper, /):\n    return helper()\n\n"
        "def bound_keyword(*, helper: int):\n    return helper()\n\n"
        "def bound_varargs(*helper):\n    return helper()\n\n"
        "def bound_kwargs(**helper):\n    return helper()\n",
        encoding="utf-8",
    )
    expected = {
        ("app.read_global", "app.helper"),
        ("app.typed_default", "app.helper"),
        ("app.positional_default", "app.helper"),
        ("app.keyword_default", "app.helper"),
    }
    graphs = [
        PythonParser().parse([path], tmp_path),
        parse(str(tmp_path), language="python", use_cache=True),
        parse(str(tmp_path), language="python", use_cache=True),
    ]
    for graph in graphs:
        actual = {
            (source, target)
            for source, target, relation in graph.to_edge_tuples()
            if relation == "calls"
        }
        assert actual == expected
