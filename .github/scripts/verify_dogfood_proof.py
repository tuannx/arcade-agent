#!/usr/bin/env python3
"""Independently audit a hosted cross-repository dogfood proof artifact.

The verifier runs in a separate CI job, checks producer artifact integrity and
compares a fresh analyzer replay on an independently checked-out pinned target.
It does not attest architecture correctness, human false-positive labels, or
that PNG pixels visually correspond to the HTML report.
"""

import argparse
import hashlib
import hmac
import json
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Timestamp is generated independently on each runner; ref is CI-context
# metadata rather than a property of the analyzed source. All remaining JSON
# fields must match, including components, graph details and score drivers.
VOLATILE_REPLAY_FIELDS = frozenset({"timestamp", "ref"})


class VerificationError(ValueError):
    """A proof cannot be trusted or independently reproduced."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot read JSON {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise VerificationError(f"{path.name}: expected JSON object")
    return value


def _require_equal(actual: Any, expected: Any, field: str) -> None:
    if actual != expected:
        raise VerificationError(f"{field}: expected {expected!r}, got {actual!r}")


def _verify_hash(path: Path, recorded: Any, label: str) -> str:
    if not isinstance(recorded, str) or len(recorded) != 64:
        raise VerificationError(f"{label}: missing or invalid SHA-256 digest")
    try:
        value = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise VerificationError(f"{label}: missing file {path.name}: {exc}") from exc
    if not hmac.compare_digest(value, recorded.lower()):
        raise VerificationError(f"{label}: SHA-256 mismatch")
    return value


def _verify_png(path: Path) -> tuple[int, int]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise VerificationError(f"screenshot: unreadable: {exc}") from exc
    if not data.startswith(PNG_SIGNATURE) or len(data) > 20_000_000:
        raise VerificationError("screenshot: invalid PNG signature or oversized file")
    offset = len(PNG_SIGNATURE)
    dimensions = None
    found_data = False
    found_end = False
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        chunk_type = data[offset + 4 : offset + 8]
        end = offset + 12 + size
        if end > len(data):
            raise VerificationError("screenshot: truncated PNG chunk")
        chunk_data = data[offset + 8 : offset + 8 + size]
        crc = struct.unpack_from(">I", data, offset + 8 + size)[0]
        if zlib.crc32(chunk_type + chunk_data) != crc:
            raise VerificationError("screenshot: invalid PNG chunk CRC")
        if offset == 8 and chunk_type != b"IHDR":
            raise VerificationError("screenshot: missing initial IHDR chunk")
        if chunk_type == b"IHDR":
            if size != 13 or dimensions is not None:
                raise VerificationError("screenshot: invalid IHDR")
            dimensions = struct.unpack_from(">II", chunk_data)
        elif chunk_type == b"IDAT":
            found_data = True
        elif chunk_type == b"IEND":
            if size != 0 or end != len(data):
                raise VerificationError("screenshot: invalid IEND or trailing bytes")
            found_end = True
            break
        offset = end
    if not (dimensions and found_data and found_end):
        raise VerificationError("screenshot: missing PNG image data or IEND")
    width, height = dimensions
    if width < 800 or height < 500:
        raise VerificationError("screenshot: too small to be a CI report capture")
    return width, height


def verify_bundle(
    proof_path: Path,
    analysis_path: Path,
    html_path: Path,
    screenshot_path: Path,
    replay_path: Path,
    expected_repo: str,
    expected_source_sha: str,
    expected_analyzer_sha: str,
) -> dict[str, Any]:
    """Check independent replay, source identity, content hashes and screenshot format."""
    if any(len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha)
           for sha in (expected_source_sha, expected_analyzer_sha)):
        raise VerificationError("expected source and analyzer SHAs must be full lowercase Git SHAs")
    proof = _read_json(proof_path)
    analysis = _read_json(analysis_path)
    replay = _read_json(replay_path)

    _require_equal(proof.get("target_repository"), expected_repo, "proof.target_repository")
    for key in ("target_commit_sha_expected", "target_commit_sha_reported"):
        _require_equal(proof.get(key), expected_source_sha, f"proof.{key}")
    _require_equal(proof.get("analyzer_commit_sha"), expected_analyzer_sha,
                   "proof.analyzer_commit_sha")
    _require_equal(proof.get("analysis_outcome"), "success", "proof.analysis_outcome")
    _require_equal(proof.get("screenshot_outcome"), "success", "proof.screenshot_outcome")

    for label, data in (("producer", analysis), ("fresh replay", replay)):
        _require_equal(data.get("repo_name"), expected_repo, f"{label}.repo_name")
        _require_equal(data.get("commit_sha"), expected_source_sha, f"{label}.commit_sha")
        _require_equal(data.get("source_ref"), f"commit:{expected_source_sha}",
                       f"{label}.source_ref")
        _require_equal(data.get("analyzer_commit_sha"), expected_analyzer_sha,
                       f"{label}.analyzer_commit_sha")

    _verify_hash(analysis_path, proof.get("analysis_json_sha256"), "analysis JSON")
    _verify_hash(screenshot_path, proof.get("screenshot_sha256"), "screenshot")
    _verify_hash(html_path, proof.get("html_report_sha256"), "HTML report")
    try:
        content = html_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise VerificationError(f"HTML report unreadable: {exc}") from exc
    if "<html" not in content.lower():
        raise VerificationError("HTML report does not contain an HTML document")
    width, height = _verify_png(screenshot_path)

    for key in ("num_entities", "num_edges", "num_components"):
        if not isinstance(analysis.get(key), int) or analysis[key] <= 0:
            raise VerificationError(f"analysis.{key}: expected positive integer")
        _require_equal(proof.get(key), analysis[key], f"proof.{key}")
    _require_equal(proof.get("smells_count_heuristic"), len(analysis.get("smells", [])),
                   "proof.smells_count_heuristic")

    replay_fields = sorted((set(analysis) | set(replay)) - VOLATILE_REPLAY_FIELDS)
    for key in replay_fields:
        if key not in analysis or key not in replay:
            raise VerificationError(f"replay.{key}: missing deterministic field")
        _require_equal(replay[key], analysis[key], f"replay.{key}")

    return {
        "status": "verified-replay-and-artifact-integrity",
        "target_repository": expected_repo,
        "source_sha": expected_source_sha,
        "analyzer_sha": expected_analyzer_sha,
        "replay_fields_compared": replay_fields,
        "screenshot_dimensions": {"width": width, "height": height},
        "analysis_sha256": hashlib.sha256(analysis_path.read_bytes()).hexdigest(),
        "screenshot_sha256": hashlib.sha256(screenshot_path.read_bytes()).hexdigest(),
        "screenshot_visual_authenticity": "not-verified",
        "architecture_correctness": "not-verified",
        "human_false_positive_review": "not-evaluated",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("proof", "analysis", "html", "screenshot", "replay", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--expected-repo", required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--expected-analyzer-sha", required=True)
    args = parser.parse_args()
    try:
        verified = verify_bundle(
            args.proof, args.analysis, args.html, args.screenshot, args.replay,
            args.expected_repo, args.expected_source_sha, args.expected_analyzer_sha,
        )
    except VerificationError as exc:
        print(f"VERIFICATION FAILED: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verified, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verified, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
