"""Hand-labelled Python inheritance edges for module-level rebinding.

A syntactic import does not prove that its name still refers to that class
when a subsequent class definition executes. Runtime reassignment remains
unsupported: omit the edge instead of asserting the wrong superclass.
"""

from pathlib import Path

from arcade_agent.parsers.python import PythonParser


def _extends(tmp_path: Path, consumer: str) -> set[tuple[str, str]]:
    sources = {
        "pkg/base.py": "class Base:\n    pass\n",
        "pkg/other.py": "class Base:\n    pass\n",
        "consumer.py": consumer,
    }
    files = []
    for name, text in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        files.append(path)
    graph = PythonParser().parse(files, tmp_path)
    return {
        (source, target)
        for source, target, relation in graph.to_edge_tuples()
        if relation == "extends" and source == "consumer.Child"
    }


def test_module_alias_rebound_before_class_never_uses_stale_import(tmp_path: Path) -> None:
    edges = _extends(tmp_path, (
        "import pkg.base as wire\n"
        "import pkg.other as alternate\n"
        "wire = alternate\n\n"
        "class Child(wire.Base):\n    pass\n"
    ))
    # The dynamic rebinding targets pkg.other.Base, but this partial linker
    # must not report the stale pkg.base.Base as an established edge.
    assert edges == set()


def test_from_import_alias_rebound_before_class_never_uses_stale_name(tmp_path: Path) -> None:
    edges = _extends(tmp_path, (
        "from pkg.base import Base as Parent\n"
        "from pkg.other import Base as Replacement\n"
        "Parent = Replacement\n\n"
        "class Child(Parent):\n    pass\n"
    ))
    assert edges == set()


def test_same_module_class_rebound_before_subclass_is_not_original_base(tmp_path: Path) -> None:
    edges = _extends(tmp_path, (
        "class Base:\n    pass\n"
        "class Replacement:\n    pass\n"
        "Base = Replacement\n\n"
        "class Child(Base):\n    pass\n"
    ))
    assert edges == set()


def test_rebinding_after_subclass_does_not_erase_valid_edge(tmp_path: Path) -> None:
    edges = _extends(tmp_path, (
        "import pkg.base as wire\n\n"
        "class Child(wire.Base):\n    pass\n\n"
        "wire = object()\n"
    ))
    assert edges == {("consumer.Child", "pkg.base.Base")}


def test_unrelated_assignment_does_not_hide_static_superclass(tmp_path: Path) -> None:
    edges = _extends(tmp_path, (
        "from pkg.base import Base as Parent\n"
        "marker = 1\n\n"
        "class Child(Parent):\n    pass\n"
    ))
    assert edges == {("consumer.Child", "pkg.base.Base")}
