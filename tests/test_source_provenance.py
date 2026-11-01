"""Regression: cross-repository analyses must report the target commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from arcade_agent.ci.provenance import resolve_source_commit


def _git(path: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


def test_pinned_source_commit_does_not_use_ci_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "target"
    source.mkdir()
    _git(source, "init", "-q")
    _git(
        source, "-c", "user.name=Test", "-c", "user.email=test@example.com",
        "commit", "--allow-empty", "-m", "init", "-q",
    )
    target_sha = _git(source, "rev-parse", "HEAD")
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)

    assert resolve_source_commit(source) == target_sha
    assert resolve_source_commit(source, expected_sha=target_sha) == target_sha
    with pytest.raises(ValueError, match="source commit mismatch"):
        resolve_source_commit(source, expected_sha="c" * 40)


def test_non_git_source_is_explicitly_local(tmp_path: Path) -> None:
    assert resolve_source_commit(tmp_path) == "local"
    with pytest.raises(ValueError, match="not a Git checkout"):
        resolve_source_commit(tmp_path, expected_sha="a" * 40)


@pytest.mark.parametrize("sha", ["", "abc", "A" * 40, "z" * 40])
def test_invalid_pin_is_rejected(tmp_path: Path, sha: str) -> None:
    with pytest.raises(ValueError, match="exactly 40"):
        resolve_source_commit(tmp_path, expected_sha=sha)
