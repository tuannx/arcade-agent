"""Dogfood regression: conservative static Python calls must be provenance-safe.

A known parser gap on arcade-agent itself was that internal Python calls were
not collected. These examples deliberately distinguish statically resolvable
same-module calls from shadowed, imported and nested calls.
"""

from arcade_agent.incremental import ExtractCache
from arcade_agent.parsers.python import PythonParser


def _parse(tmp_path, source):
    path = tmp_path / "app.py"
    path.write_text(source, encoding="utf-8")
    return PythonParser().parse([path], tmp_path)


def test_direct_same_module_function_call_is_a_call_edge(tmp_path):
    graph = _parse(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def run():\n    return helper()\n"
    ))
    assert ("app.run", "app.helper", "calls") in graph.to_edge_tuples()
    assert graph.relation_coverage()["python"] == {
        "collected_relations": ["calls", "extends", "import"],
        "call_coverage": "partial",
    }


def test_parameters_and_local_rebinding_do_not_create_false_edges(tmp_path):
    graph = _parse(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def callback(helper):\n    return helper()\n\n"
        "def rebound():\n"
        "    helper = lambda: 5\n"
        "    return helper()\n\n"
        "def real():\n    return helper()\n"
    ))
    edges = graph.to_edge_tuples()
    assert ("app.real", "app.helper", "calls") in edges
    assert ("app.callback", "app.helper", "calls") not in edges
    assert ("app.rebound", "app.helper", "calls") not in edges


def test_nested_function_calls_and_decorator_expressions_are_not_attributed_to_outer(tmp_path):
    graph = _parse(tmp_path, (
        "def helper():\n    return lambda fn: fn\n\n"
        "@helper()\n"
        "def outer():\n"
        "    def nested():\n"
        "        return helper()\n"
        "    return nested\n"
    ))
    assert ("app.outer", "app.helper", "calls") not in graph.to_edge_tuples()


def test_function_local_import_and_module_rebinding_prevent_false_edges(tmp_path):
    graph = _parse(tmp_path, (
        "def helper():\n    return 1\n\n"
        "def imported():\n"
        "    from external import helper\n"
        "    return helper()\n\n"
        "helper = lambda: 9\n\n"
        "def rewritten():\n    return helper()\n"
    ))
    edges = graph.to_edge_tuples()
    assert ("app.imported", "app.helper", "calls") not in edges
    assert ("app.rewritten", "app.helper", "calls") not in edges


def test_incremental_cache_replays_calls_and_invalidates_when_source_changes(tmp_path):
    source = tmp_path / "app.py"
    source.write_text(
        "def helper():\n    return 1\n\n"
        "def run():\n    return helper()\n",
        encoding="utf-8",
    )
    parser = PythonParser()
    cache = ExtractCache(tmp_path)
    first = parser.parse_incremental([source], tmp_path, cache)
    second = parser.parse_incremental([source], tmp_path, cache)
    assert cache.stats["reused"] >= 1
    assert first.to_edge_tuples() == second.to_edge_tuples()
    assert ("app.run", "app.helper", "calls") in second.to_edge_tuples()
    source.write_text(source.read_text().replace("helper()", "1"), encoding="utf-8")
    after = parser.parse_incremental([source], tmp_path, cache)
    assert ("app.run", "app.helper", "calls") not in after.to_edge_tuples()
    assert after.to_edge_tuples() == parser.parse([source], tmp_path).to_edge_tuples()


def test_attribute_and_dynamic_calls_remain_unknown_not_claimed_complete(tmp_path):
    graph = _parse(tmp_path, (
        "def helper():\n    return 1\n\n"
        "class S:\n"
        "    def call(self):\n"
        "        return self.helper()\n"
    ))
    assert not [e for e in graph.edges if e.relation == "calls"]
    assert graph.relation_coverage()["python"]["call_coverage"] == "partial"
