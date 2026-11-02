"""Ground-truth fixtures for Python imported-module superclass resolution.

These are deterministic source-to-source inheritance edges, not architecture
violations or dynamic-dispatch guarantees.
"""

from pathlib import Path

from arcade_agent.parsers.python import PythonParser


def _extends(tmp_path: Path, files: dict[str, str]) -> set[tuple[str, str]]:
    paths = []
    for relative, body in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
        paths.append(path)
    graph = PythonParser().parse(paths, tmp_path)
    assert graph.relation_coverage()["python"]["call_coverage"] == "partial"
    return {
        (source, target)
        for source, target, relation in graph.to_edge_tuples()
        if relation == "extends"
    }


def test_aliased_module_base_class(tmp_path: Path) -> None:
    edges = _extends(tmp_path, {
        "pkg/base.py": "class Base:\n    pass\n",
        "consumer.py": "import pkg.base as wire\n\nclass Child(wire.Base):\n    pass\n",
    })
    assert ("consumer.Child", "pkg.base.Base") in edges


def test_aliased_nested_module_base_class(tmp_path: Path) -> None:
    edges = _extends(tmp_path, {
        "pkg/models/base.py": "class Base:\n    pass\n",
        "consumer.py": (
            "import pkg.models.base as facade\n\n"
            "class Child(facade.Base):\n    pass\n"
        ),
    })
    assert ("consumer.Child", "pkg.models.base.Base") in edges


def test_unaliased_dotted_module_base_class(tmp_path: Path) -> None:
    edges = _extends(tmp_path, {
        "pkg/base.py": "class Base:\n    pass\n",
        "consumer.py": "import pkg.base\n\nclass Child(pkg.base.Base):\n    pass\n",
    })
    assert ("consumer.Child", "pkg.base.Base") in edges


def test_unaliased_simple_import_keeps_existing_edge(tmp_path: Path) -> None:
    edges = _extends(tmp_path, {
        "base.py": "class Base:\n    pass\n",
        "consumer.py": "import base\n\nclass Child(base.Base):\n    pass\n",
    })
    assert edges == {("consumer.Child", "base.Base")}


def test_module_alias_does_not_resolve_to_unrelated_base(tmp_path: Path) -> None:
    edges = _extends(tmp_path, {
        "pkg/base.py": "class Base:\n    pass\n",
        "pkg/other.py": "class Base:\n    pass\n",
        "consumer.py": "import pkg.other as wire\n\nclass Child(wire.Base):\n    pass\n",
    })
    assert edges == {("consumer.Child", "pkg.other.Base")}


def test_from_import_alias_remains_supported(tmp_path: Path) -> None:
    edges = _extends(tmp_path, {
        "pkg/base.py": "class Base:\n    pass\n",
        "consumer.py": (
            "from pkg.base import Base as Parent\n\n"
            "class Child(Parent):\n    pass\n"
        ),
    })
    assert edges == {("consumer.Child", "pkg.base.Base")}


def test_swapped_aliases_never_link_to_similarly_named_module(tmp_path: Path) -> None:
    # Both imports are valid. The local name 'base' denotes pkg.other,
    # even though the *other* imported module ends in the token 'base'.
    edges = _extends(tmp_path, {
        "pkg/base.py": "class Base:\\n    pass\\n",
        "pkg/other.py": "class Base:\\n    pass\\n",
        "consumer.py": (
            "import pkg.base as other\\n"
            "import pkg.other as base\\n\\n"
            "class Child(base.Base):\\n    pass\\n"
        ),
    })
    assert edges == {("consumer.Child", "pkg.other.Base")}
