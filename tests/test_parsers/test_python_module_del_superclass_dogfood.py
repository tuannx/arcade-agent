"""Selected Python inheritance oracle: module-level deletion unbinds base aliases.

These are source-level graph expectations, not measured production precision.
An unbound name raises at class definition time; the analyzer must not
confidently attach an `extends` edge to an import that was deleted.
"""

from pathlib import Path

from arcade_agent.parsers.python import PythonParser


def _edges(tmp_path: Path, consumer: str) -> set[tuple[str, str]]:
    sources = {
        "pkg/base.py": "class Base:\n    pass\nmarker = 1\n",
        "consumer.py": consumer,
    }
    paths = []
    for name, text in sources.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        paths.append(path)
    graph = PythonParser().parse(paths, tmp_path)
    return {
        (source, target)
        for source, target, relation in graph.to_edge_tuples()
        if source == "consumer.Child" and relation == "extends"
    }


def test_module_alias_deleted_before_class_has_no_stale_edge(tmp_path: Path) -> None:
    edges = _edges(tmp_path, (
        "import pkg.base as wire\n"
        "del wire\n"
        "class Child(wire.Base):\n    pass\n"
    ))
    assert edges == set()


def test_from_import_alias_deleted_before_class_has_no_stale_edge(tmp_path: Path) -> None:
    edges = _edges(tmp_path, (
        "from pkg.base import Base as Parent\n"
        "del Parent\n"
        "class Child(Parent):\n    pass\n"
    ))
    assert edges == set()


def test_reimport_after_deletion_restores_known_base(tmp_path: Path) -> None:
    edges = _edges(tmp_path, (
        "import pkg.base as wire\n"
        "del wire\n"
        "import pkg.base as wire\n"
        "class Child(wire.Base):\n    pass\n"
    ))
    assert edges == {("consumer.Child", "pkg.base.Base")}


def test_attribute_deletion_does_not_unbind_module(tmp_path: Path) -> None:
    edges = _edges(tmp_path, (
        "import pkg.base as wire\n"
        "del wire.marker\n"
        "class Child(wire.Base):\n    pass\n"
    ))
    assert edges == {("consumer.Child", "pkg.base.Base")}


def test_deletion_after_class_cannot_rewrite_existing_edge(tmp_path: Path) -> None:
    edges = _edges(tmp_path, (
        "from pkg.base import Base as Parent\n"
        "class Child(Parent):\n    pass\n"
        "del Parent\n"
    ))
    assert edges == {("consumer.Child", "pkg.base.Base")}
