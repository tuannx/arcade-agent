"""Golden controls: analyzer revision must not be inferred from hosting workflow."""

import shutil
import subprocess
from pathlib import Path

import pytest

from arcade_agent.ci.provenance import resolve_analyzer_commit


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


@pytest.fixture
def analyzer_checkout(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "source"
    package = root / "src" / "arcade_agent"
    package.mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\\nname = "arcade-agent"\\n')
    (package / "__init__.py").write_text("__version__ = 'test'\\n")
    (package / "ci").mkdir()
    (package / "ci" / "run_self_analysis.py").write_text("def main(): pass\\n")
    git(root, "init", "-q")
    git(root, "add", ".")
    git(root, "-c", "user.name=Test", "-c", "user.email=test@example.com",
        "commit", "-m", "pinned", "-q")
    installed = tmp_path / "site-packages" / "arcade_agent"
    shutil.copytree(package, installed)
    return root, installed, git(root, "rev-parse", "HEAD")


def test_pinned_analyzer_sha_ignores_host_runner_env(analyzer_checkout, monkeypatch):
    root, installed, sha = analyzer_checkout
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    assert resolve_analyzer_commit(root, sha, installed_package=installed) == sha


def test_missing_provenance_is_explicitly_unavailable(monkeypatch):
    monkeypatch.setenv("GITHUB_SHA", "a" * 40)
    assert resolve_analyzer_commit() == "unavailable"


@pytest.mark.parametrize("missing", ["source", "sha"])
def test_partial_attestation_is_rejected(analyzer_checkout, missing):
    root, installed, sha = analyzer_checkout
    with pytest.raises(ValueError, match="requires both"):
        if missing == "source":
            resolve_analyzer_commit(expected_sha=sha, installed_package=installed)
        else:
            resolve_analyzer_commit(root, installed_package=installed)


def test_wrong_checkout_sha_is_rejected(analyzer_checkout):
    root, installed, sha = analyzer_checkout
    with pytest.raises(ValueError, match="source commit mismatch"):
        resolve_analyzer_commit(root, "f" * 40, installed_package=installed)


def test_installed_package_mismatch_is_rejected(analyzer_checkout):
    root, installed, sha = analyzer_checkout
    (installed / "ci" / "run_self_analysis.py").write_text("def main(): pass # tampered\\n")
    with pytest.raises(ValueError, match="differs"):
        resolve_analyzer_commit(root, sha, installed_package=installed)


def test_missing_installed_module_is_rejected(analyzer_checkout):
    root, installed, sha = analyzer_checkout
    (installed / "ci" / "run_self_analysis.py").unlink()
    with pytest.raises(ValueError, match="differs"):
        resolve_analyzer_commit(root, sha, installed_package=installed)


def test_modified_checkout_is_rejected(analyzer_checkout):
    root, installed, sha = analyzer_checkout
    (root / "src" / "arcade_agent" / "__init__.py").write_text("changed = True\\n")
    with pytest.raises(ValueError, match="dirty"):
        resolve_analyzer_commit(root, sha, installed_package=installed)


def test_rejects_arbitrary_git_checkout(analyzer_checkout):
    root, installed, sha = analyzer_checkout
    (root / "pyproject.toml").unlink()
    with pytest.raises(ValueError, match="not an arcade-agent source"):
        resolve_analyzer_commit(root, sha, installed_package=installed)
