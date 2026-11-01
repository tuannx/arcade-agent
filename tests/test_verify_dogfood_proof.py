"""Independent proof verifier: tampering must fail even when producer hashes are updated."""

import hashlib
import importlib.util
import json
import struct
import zlib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/verify_dogfood_proof.py"
spec = importlib.util.spec_from_file_location("verify_dogfood_proof", SCRIPT)
assert spec is not None and spec.loader is not None
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)

SOURCE_SHA = "a" * 40
ANALYZER_SHA = "b" * 40
REPO = "example/source"


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _valid_png():
    # Small compressed image with realistic dimensions, not a pretend browser screenshot.
    ihdr = struct.pack(">IIBBBBB", 800, 600, 8, 0, 0, 0, 0)
    rows = b"".join(b"\x00" + bytes((y + x) % 256 for x in range(800))
                    for y in range(600))
    return (verifier.PNG_SIGNATURE + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", zlib.compress(rows)) + _chunk(b"IEND", b""))


@pytest.fixture
def bundle(tmp_path):
    payload = {
        "repo_name": REPO, "commit_sha": SOURCE_SHA,
        "analyzer_commit_sha": ANALYZER_SHA, "source_ref": f"commit:{SOURCE_SHA}",
        "num_entities": 8, "num_edges": 9, "num_components": 3,
        "component_dependencies": [{"source": "A", "target": "B"}],
        "metrics": {"RCI": 0.5}, "derived_metrics": {"BalancedArchitectureScore": 0.6},
        "principle_signals": {"LayeringHealth": 1}, "smells": [],
    }
    paths = {name: tmp_path / name for name in (
        "proof.json", "analysis.json", "report.html", "report.png", "replay.json",
    )}
    paths["analysis.json"].write_text(json.dumps(payload))
    paths["replay.json"].write_text(json.dumps(payload))
    paths["report.html"].write_text("<html><body>Actual report</body></html>")
    paths["report.png"].write_bytes(_valid_png())

    def digest(key):
        return hashlib.sha256(paths[key].read_bytes()).hexdigest()

    proof = {
        "target_repository": REPO,
        "target_commit_sha_expected": SOURCE_SHA,
        "target_commit_sha_reported": SOURCE_SHA,
        "analyzer_commit_sha": ANALYZER_SHA,
        "analysis_outcome": "success", "screenshot_outcome": "success",
        "analysis_json_sha256": digest("analysis.json"),
        "screenshot_sha256": digest("report.png"),
        "html_report_sha256": digest("report.html"),
        "num_entities": 8, "num_edges": 9, "num_components": 3,
        "smells_count_heuristic": 0,
    }
    paths["proof.json"].write_text(json.dumps(proof))
    return paths


def run(bundle):
    return verifier.verify_bundle(bundle["proof.json"], bundle["analysis.json"],
        bundle["report.html"], bundle["report.png"], bundle["replay.json"],
        REPO, SOURCE_SHA, ANALYZER_SHA)


def test_valid_replay_and_integrity(bundle):
    result = run(bundle)
    assert result["status"] == "verified-replay-and-artifact-integrity"
    assert result["screenshot_visual_authenticity"] == "not-verified"


def test_corrupted_screenshot_rejected(bundle):
    bundle["report.png"].write_bytes(bundle["report.png"].read_bytes() + b"tamper")
    with pytest.raises(verifier.VerificationError, match="SHA-256 mismatch"):
        run(bundle)


def test_replaced_png_even_with_matching_manifest_digest_rejected(bundle):
    bundle["report.png"].write_bytes(b"not a PNG")
    proof = json.loads(bundle["proof.json"].read_text())
    proof["screenshot_sha256"] = hashlib.sha256(b"not a PNG").hexdigest()
    bundle["proof.json"].write_text(json.dumps(proof))
    with pytest.raises(verifier.VerificationError, match="PNG signature"):
        run(bundle)


def test_modified_report_rejected_by_independent_replay(bundle):
    data = json.loads(bundle["analysis.json"].read_text())
    data["num_edges"] = 10
    bundle["analysis.json"].write_text(json.dumps(data))
    proof = json.loads(bundle["proof.json"].read_text())
    proof["num_edges"] = 10
    proof["analysis_json_sha256"] = hashlib.sha256(bundle["analysis.json"].read_bytes()).hexdigest()
    bundle["proof.json"].write_text(json.dumps(proof))
    with pytest.raises(verifier.VerificationError, match="replay.num_edges"):
        run(bundle)


def test_wrong_expected_commit_rejected(bundle):
    with pytest.raises(verifier.VerificationError, match="proof.target_commit_sha_expected"):
        verifier.verify_bundle(bundle["proof.json"], bundle["analysis.json"],
            bundle["report.html"], bundle["report.png"], bundle["replay.json"],
            REPO, "c" * 40, ANALYZER_SHA)


def test_missing_replay_fails_closed(bundle):
    bundle["replay.json"].unlink()
    with pytest.raises(verifier.VerificationError, match="cannot read JSON"):
        run(bundle)


def test_html_tampering_fails(bundle):
    bundle["report.html"].write_text("<html>altered</html>")
    with pytest.raises(verifier.VerificationError, match="HTML report: SHA-256 mismatch"):
        run(bundle)
