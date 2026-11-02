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
        # A commit pin is only defensible when tracked/untracked status can be checked.
        state = source_worktree_state(source)
        if state == "unknown":
            raise ValueError("could not verify pinned source worktree cleanliness")
        if state == "dirty":
            raise ValueError("pinned source worktree is dirty (tracked or untracked changes)")
    return actual


def source_worktree_state(source: str | Path) -> str:
    """Classify Git status as clean, dirty, or unknown (cannot verify).

    This is not a byte-level attestation: ignored/generated files, submodules,
    and concurrent source changes can still make a SHA-labelled report incomplete.
    """
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
    except OSError:
        return "unknown"
    if status.returncode != 0:
        return "unknown"
    return "dirty" if status.stdout.strip() else "clean"


def source_provenance_fields(
    source: str | Path, expected_sha: str | None = None,
) -> dict[str, str]:
    """Produce report fields without calling a dirty checkout commit-exact."""
    source_sha = resolve_source_commit(source, expected_sha)
    if source_sha == "local":
        return {
            "commit_sha": "local",
            "source_ref": "local",
            "source_worktree_state": "not-git",
        }

    # resolve_source_commit already rejected dirty/unknown pinned worktrees.
    state = "clean" if expected_sha is not None else source_worktree_state(source)
    label = {"clean": "commit", "dirty": "worktree", "unknown": "unverified"}[state]
    return {
        "commit_sha": source_sha,
        "source_ref": f"{label}:{source_sha}",
        "source_worktree_state": state,
    }
