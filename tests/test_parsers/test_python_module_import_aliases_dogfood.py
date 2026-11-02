"""Golden labels: module-level `import ... as ...` binds its alias.

This exercises ordinary Python lexical binding and graph import dependencies.
These are hand-labelled graph edges, not verified architecture violations.
"""

from pathlib import Path
from textwrap import dedent

from arcade_agent.parsers.python import PythonParser


def _calls(tmp_path: Path, source: str) -> set[tuple[str, str]]:
    path = tmp_path / "app.py"
    path.write_text(dedent(source), encoding="utf-8")
    graph = PythonParser().parse([path], tmp_path)
    assert graph.relation_coverage()["python"]["call_coverage"] == "partial"
    return {
        (source_fqn, target_fqn)
        for source_fqn, target_fqn, relation in graph.to_edge_tuples()
        if relation == "calls"
    }


def test_module_alias_masks_same_module_function(tmp_path: Path) -> None:
    source = """
    def helper():
        return 1

    import json as helper

    def parent():
        return helper()
    """
    assert _calls(tmp_path, source) == set()


def test_dotted_module_alias_masks_same_module_function(tmp_path: Path) -> None:
    source = """
    def helper():
        return 1

    import json.encoder as helper

    def parent():
        return helper()
    """
    assert _calls(tmp_path, source) == set()


def test_multi_module_import_alias_masks_only_bound_name(tmp_path: Path) -> None:
    source = """
    def helper():
        return 1

    def actual():
        return 2

    import json, collections as helper

    def parent():
        return helper() + actual()
    """
    assert _calls(tmp_path, source) == {("app.parent", "app.actual")}


def test_non_conflicting_module_alias_preserves_true_call(tmp_path: Path) -> None:
    source = """
    def helper():
        return 1

    import json as wire

    def parent():
        return helper()
    """
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}


def test_module_alias_references_imported_module_entity(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    module = package / "sub.py"
    module.write_text("VERSION = 1\n", encoding="utf-8")
    service = tmp_path / "service.py"
    service.write_text(
        "import pkg.sub as gateway\n\ndef parent():\n    return gateway.VERSION\n",
        encoding="utf-8",
    )

    graph = PythonParser().parse([module, service], tmp_path)
    assert ("service.parent", "pkg.sub", "import") in graph.to_edge_tuples()
    assert graph.relation_coverage()["python"]["call_coverage"] == "partial"
