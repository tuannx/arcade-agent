"""Regression: scope-binding false calls must stay absent with cached parsing."""

from arcade_agent.parsers.python import PythonParser
from arcade_agent.tools.parse import parse


def test_with_except_walrus_shadows_are_cache_stable(tmp_path):
    path = tmp_path / "app.py"
    path.write_text(
        "def helper():\n    return 1\n\n"
        "def via_with(manager):\n"
        "    with manager as helper:\n"
        "        return helper()\n\n"
        "def via_except():\n"
        "    try:\n        raise ValueError()\n"
        "    except ValueError as helper:\n"
        "        return helper()\n\n"
        "def via_walrus():\n"
        "    (helper := lambda: 1)\n"
        "    return helper()\n\n"
        "def unaffected():\n    return helper()\n",
        encoding="utf-8",
    )
    graphs = [
        PythonParser().parse([path], tmp_path),
        parse(str(tmp_path), language="python", use_cache=True),
        parse(str(tmp_path), language="python", use_cache=True),
    ]
    expected = {("app.unaffected", "app.helper")}
    for graph in graphs:
        edges = {
            (source, target)
            for source, target, relation in graph.to_edge_tuples()
            if relation == "calls"
        }
        assert edges == expected
