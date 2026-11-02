"""Golden call-edge labels for names actually bound by function-local imports.

Import source module paths are not automatically local bindings. Aliased imports
bind aliases, not source module names. Tests concern graph edges, not violations.
"""

from pathlib import Path
from textwrap import dedent

from arcade_agent.parsers.python import PythonParser


def _calls(tmp_path: Path, source: str) -> set[tuple[str, str]]:
    path = tmp_path / "app.py"
    path.write_text(dedent(source), encoding="utf-8")
    graph = PythonParser().parse([path], tmp_path)
    assert graph.metadata["relation_coverage"]["python"]["call_coverage"] == "partial"
    return {
        (caller, callee)
        for caller, callee, relation in graph.to_edge_tuples()
        if relation == "calls"
    }


def test_aliased_import_does_not_shadow_imported_module_name(tmp_path: Path) -> None:
    source = """
    def helper():
        return 1

    def alias():
        return 2

    def parent():
        import helper as alias
        return helper() + alias()
    """
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}


def test_from_import_alias_does_not_shadow_source_module_name(tmp_path: Path) -> None:
    source = """
    def helper():
        return 1

    def local_alias():
        return 2

    def parent():
        from helper import value as local_alias
        return helper() + local_alias()
    """
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}


def test_unaliased_dotted_import_binds_first_module_segment(tmp_path: Path) -> None:
    source = """
    def pkg():
        return 1

    def helper():
        return 2

    def parent():
        import pkg.sub
        return pkg() + helper()
    """
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}


def test_from_import_without_alias_shadows_local_call(tmp_path: Path) -> None:
    source = """
    def helper():
        return 1

    def parent():
        from package import helper
        return helper()
    """
    assert _calls(tmp_path, source) == set()


def test_multi_import_alias_only_shadows_bound_name(tmp_path: Path) -> None:
    source = """
    def helper():
        return 1

    def other():
        return 2

    def parent():
        import helper as alternate, other
        return helper() + other()
    """
    assert _calls(tmp_path, source) == {("app.parent", "app.helper")}
