"""Resolve commit provenance from the analyzed repository, not the CI runner."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_FULL_SHA = re.compile(r"[0-9a-f]{40}")


def resolve_source_commit(source: str | Path, expected_sha: str | None = None) -> str:
    """Return source Git commit, or 'local' for non-Git source trees.

    When expected_sha is supplied, analysis must target that exact commit.
    Invalid SHA, missing Git metadata, mismatch, or a dirty checkout is a hard
    error: changed source bytes would otherwise be mislabeled with the Git SHA.
    """
    if expected_sha is not None and not _FULL_SHA.fullmatch(expected_sha):
        raise ValueError("expected source SHA must be exactly 40 lowercase hex characters")

    try:
        result = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "--verify", "HEAD^{commit}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        result = None

    actual = result.stdout.strip() if result is not None and result.returncode == 0 else None
    if actual is None or not _FULL_SHA.fullmatch(actual):
        if expected_sha is not None:
            raise ValueError("source is not a Git checkout at the expected commit")
        return "local"
    if expected_sha is not None and actual != expected_sha:
        raise ValueError(f"source commit mismatch: expected {expected_sha}, got {actual}")
    if expected_sha is not None:
        # HEAD alone is insufficient: tracked edits and untracked source files
        # may change the bytes analyzed without changing the commit identity.
        try:
            status = subprocess.run(
                [
                    "git", "-C", str(source), "status", "--porcelain=v1",
                    "--untracked-files=all", "--ignore-submodules=none",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise ValueError("could not verify pinned source worktree cleanliness") from exc
        if status.returncode != 0:
            raise ValueError("could not verify pinned source worktree cleanliness")
        if status.stdout.strip():
            raise ValueError("pinned source worktree is dirty (tracked or untracked changes)")
    return actual

def resolve_analyzer_commit(
    analyzer_source: str | Path | None = None,
    expected_sha: str | None = None,
    *,
    installed_package: str | Path | None = None,
) -> str:
    """Attest analyzer checkout HEAD and the Python package actually imported.

    A non-editable pip install is not within a Git checkout. An explicit pinned
    checkout and byte equality check prevent a hosting runner's GITHUB_SHA from
    being mislabeled as the actual analyzer source commit. This only attests
    Python package files, not external/native dependencies or the environment.
    """
    if analyzer_source is None and expected_sha is None:
        return "unavailable"
    if analyzer_source is None or expected_sha is None:
        raise ValueError(
            "analyzer provenance requires both --analyzer-source and --expected-analyzer-sha"
        )

    source = Path(analyzer_source).resolve()
    committed_package = source / "src" / "arcade_agent"
    runtime_package = (
        Path(installed_package).resolve()
        if installed_package is not None
        else Path(__file__).resolve().parents[1]
    )
    if not (source / "pyproject.toml").is_file() or not committed_package.is_dir():
        raise ValueError("analyzer source is not an arcade-agent source checkout")

    commit = resolve_source_commit(source, expected_sha)

    def python_files(root: Path) -> dict[str, bytes]:
        return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*.py")}

    try:
        committed = python_files(committed_package)
        installed = python_files(runtime_package)
    except OSError as exc:
        raise ValueError("cannot verify installed analyzer Python package") from exc
    if not committed or committed != installed:
        raise ValueError("installed analyzer Python package differs from pinned source checkout")
    return commit
