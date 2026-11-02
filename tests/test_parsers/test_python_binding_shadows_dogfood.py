"""Golden fixtures: Python local binding constructs must not invent call edges.

These cases are intentionally scoped to names whose runtime bindings are
known. A same-module function with the same spelling is *not* the target
of a locally-bound alias or assignment expression.
"""

from arcade_agent.parsers.python import PythonParser


def _call_edges(tmp_path, source):
    path = tmp_path / "app.py"
    path.write_text(source, encoding="utf-8")
    graph = PythonParser().parse([path], tmp_path)
    return {(src, dst) for src, dst, relation in graph.to_edge_tuples()
            if relation == "calls"}


def test_with_as_binding_shadows_top_level_function(tmp_path):
    edges = _call_edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def caller(manager):\n"
        "    with manager as helper:\n"
        "        return helper()\n\n"
        "def real(manager):\n"
        "    with manager as resource:\n"
        "        return helper()\n"
    ))
    assert ("app.caller", "app.helper") not in edges
    assert ("app.real", "app.helper") in edges


def test_except_as_binding_shadows_top_level_function(tmp_path):
    edges = _call_edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def caller():\n"
        "    try:\n"
        "        raise RuntimeError()\n"
        "    except RuntimeError as helper:\n"
        "        return helper()\n\n"
        "def real():\n"
        "    try:\n"
        "        raise RuntimeError()\n"
        "    except RuntimeError as error:\n"
        "        return helper()\n"
    ))
    assert ("app.caller", "app.helper") not in edges
    assert ("app.real", "app.helper") in edges


def test_walrus_binding_shadows_top_level_function(tmp_path):
    edges = _call_edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def caller():\n"
        "    (helper := lambda: 5)\n"
        "    return helper()\n\n"
        "def real():\n"
        "    (unrelated := lambda: 5)\n"
        "    return helper()\n"
    ))
    assert ("app.caller", "app.helper") not in edges
    assert ("app.real", "app.helper") in edges
