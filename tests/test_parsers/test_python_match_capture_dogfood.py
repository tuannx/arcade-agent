"""Golden fixtures for Python match/case binding provenance.

Python capture patterns are local assignments, not references to a same-named
module function. Value patterns and unrelated names must retain real call edges.
These assertions test graph facts, not architecture quality verdicts.
"""

from arcade_agent.parsers.python import PythonParser


def _edges(tmp_path, source: str) -> set[tuple[str, str]]:
    path = tmp_path / "app.py"
    path.write_text(source, encoding="utf-8")
    graph = PythonParser().parse([path], tmp_path)
    return {(src, dst) for src, dst, rel in graph.to_edge_tuples()
            if rel == "calls"}


def test_match_bare_capture_shadows_module_call(tmp_path):
    edges = _edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def captured(value):\n"
        "    match value:\n"
        "        case helper:\n"
        "            return helper()\n\n"
        "def unaffected(value):\n"
        "    match value:\n"
        "        case _:\n"
        "            return helper()\n"
    ))
    assert ("app.captured", "app.helper") not in edges
    assert ("app.unaffected", "app.helper") in edges


def test_match_list_and_mapping_destructuring_shadow(tmp_path):
    edges = _edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def list_capture(value):\n"
        "    match value:\n"
        "        case [first, *helper]:\n"
        "            return helper()\n"
        "        case _:\n"
        "            return 0\n\n"
        "def mapping_capture(value):\n"
        "    match value:\n"
        "        case {'item': helper, **tail}:\n"
        "            return helper()\n"
        "        case _:\n"
        "            return 0\n\n"
        "def unaffected(value):\n"
        "    match value:\n"
        "        case {'item': other}:\n"
        "            return helper()\n"
        "        case _:\n"
        "            return 0\n"
    ))
    assert ("app.list_capture", "app.helper") not in edges
    assert ("app.mapping_capture", "app.helper") not in edges
    assert ("app.unaffected", "app.helper") in edges


def test_match_class_keyword_and_as_capture_shadow(tmp_path):
    edges = _edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def class_capture(value):\n"
        "    match value:\n"
        "        case Point(x=helper):\n"
        "            return helper()\n"
        "        case _:\n"
        "            return 0\n\n"
        "def alias_capture(value):\n"
        "    match value:\n"
        "        case (1 | 2) as helper:\n"
        "            return helper()\n"
        "        case _:\n"
        "            return 0\n"
    ))
    assert ("app.class_capture", "app.helper") not in edges
    assert ("app.alias_capture", "app.helper") not in edges


def test_match_dotted_value_pattern_does_not_shadow(tmp_path):
    edges = _edges(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def actual_call(value):\n"
        "    match value:\n"
        "        case Constants.helper:\n"
        "            return helper()\n"
        "        case _:\n"
        "            return helper()\n"
    ))
    assert ("app.actual_call", "app.helper") in edges
