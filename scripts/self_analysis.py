#!/usr/bin/env python3
"""CI self-analysis script for arcade-agent.

Runs arcade-agent on its own source code, produces:
- A JSON baseline file with metrics, components, and smells
- A human-readable summary printed to CI logs
- An optional Markdown PR comment file (--comment-output)
- Optional before-after comparison when a previous baseline is provided (--baseline)

Usage:
    # First run (no baseline)
    python scripts/self_analysis.py --output analysis.json

    # Subsequent run with comparison
    python scripts/self_analysis.py --baseline previous.json --output analysis.json

    # Also generate PR comment markdown
    python scripts/self_analysis.py --baseline previous.json --output analysis.json \\
        --comment-output pr_comment.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure arcade_agent is importable when running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arcade_agent.models.architecture import Architecture, Component
from arcade_agent.tools.compare import compare
from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.ingest import ingest
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trend(old: float, new: float) -> str:
    """Return a short trend indicator string."""
    diff = new - old
    if abs(diff) < 1e-4:
        return "→"
    return f"↑ +{diff:.4f}" if diff > 0 else f"↓ {diff:.4f}"


def _severity_emoji(severity: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity.lower(), "⚪")


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def run_analysis(source_path: str) -> dict:
    """Run full architecture analysis and return a serialisable result dict."""
    repo = ingest(source_path, language="python")
    if not repo.source_files:
        raise RuntimeError("No Python source files found in the project.")

    graph = parse(
        str(repo.path),
        language=repo.language,
        files=[str(f) for f in repo.source_files],
    )
    if graph.num_entities == 0:
        raise RuntimeError("No entities extracted from source files.")

    arch = recover(graph, algorithm="pkg")
    smells = detect_smells(arch, graph)
    metrics = compute_metrics(arch, graph)

    # Serialise to plain dict so we can store as JSON
    result: dict = {
        "version": repo.version or "unknown",
        "entities": graph.num_entities,
        "edges": graph.num_edges,
        "components": [
            {"name": c.name, "entity_count": len(c.entities), "entities": c.entities}
            for c in arch.components
        ],
        "metrics": {m.name: round(m.value, 6) for m in metrics},
        "smells": [
            {
                "type": s.smell_type,
                "severity": s.severity,
                "affected": s.affected_components,
                "description": s.description,
            }
            for s in smells
        ],
    }

    # Keep arch and graph objects for comparison (not returned)
    result["_arch"] = arch
    result["_graph"] = graph

    repo.cleanup()
    return result


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def build_comparison(baseline: dict, current: dict) -> dict:
    """Compare current analysis against a baseline using the compare tool."""
    arch_a = baseline.get("_arch")
    arch_b = current.get("_arch")

    comparison: dict = {}

    if arch_a is not None and arch_b is not None:
        diff = compare(arch_a, arch_b)
        comparison["a2a_similarity"] = diff["overall_similarity"]
        comparison["summary"] = diff["summary"]
        comparison["matches"] = diff["matches"]
    else:
        # Fallback: summarise from raw component names only
        a_comps = {c["name"] for c in baseline.get("components", [])}
        b_comps = {c["name"] for c in current.get("components", [])}
        added = sorted(b_comps - a_comps)
        removed = sorted(a_comps - b_comps)
        comparison["a2a_similarity"] = None
        comparison["summary"] = {
            "arch_a_components": len(a_comps),
            "arch_b_components": len(b_comps),
            "components_added": len(added),
            "components_removed": len(removed),
            "total_matches": len(a_comps & b_comps),
        }
        matched = [
            {"source": n, "target": n, "similarity": 1.0,
             "entities_added": [], "entities_removed": []}
            for n in a_comps & b_comps
        ]
        new_comps = [
            {"source": None, "target": n, "similarity": 0.0,
             "entities_added": [], "entities_removed": []}
            for n in added
        ]
        old_comps = [
            {"source": n, "target": None, "similarity": 0.0,
             "entities_added": [], "entities_removed": []}
            for n in removed
        ]
        comparison["matches"] = matched + new_comps + old_comps

    # Metric trends
    old_metrics = baseline.get("metrics", {})
    new_metrics = current.get("metrics", {})
    trends: dict[str, dict] = {}
    for name, new_val in new_metrics.items():
        old_val = old_metrics.get(name)
        trends[name] = {
            "old": old_val,
            "new": new_val,
            "delta": round(new_val - old_val, 6) if old_val is not None else None,
        }

    comparison["metric_trends"] = trends
    comparison["entity_delta"] = current["entities"] - baseline["entities"]
    comparison["edge_delta"] = current["edges"] - baseline["edges"]
    comparison["smell_delta"] = len(current["smells"]) - len(baseline["smells"])

    return comparison


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def print_ci_summary(current: dict, comparison: dict | None = None) -> None:
    """Print a human-readable summary to stdout (appears in CI logs)."""
    sep = "━" * 60
    print("\n🏗️  Architecture Self-Analysis — arcade-agent")
    print(sep)

    print("\n📦 Project Snapshot")
    print(f"   Entities : {current['entities']}")
    print(f"   Edges    : {current['edges']}")
    print(f"   Components: {len(current['components'])}")
    for comp in current["components"]:
        print(f"     • {comp['name']} ({comp['entity_count']} entities)")

    print("\n📊 Quality Metrics")
    for name, val in current["metrics"].items():
        print(f"   {name:<24} {val:.4f}")

    smells = current["smells"]
    print(f"\n🚨 Architectural Smells ({len(smells)} detected)")
    if smells:
        for s in smells:
            emoji = _severity_emoji(s["severity"])
            print(f"   {emoji} [{s['severity']}] {s['type']}: {s['description'][:80]}")
    else:
        print("   ✅ No smells detected")

    if comparison:
        print("\n🔄 Evolution vs Baseline")
        summ = comparison.get("summary", {})
        sim = comparison.get("a2a_similarity")
        if sim is not None:
            print(f"   A2A Similarity  : {sim:.4f}")
        print(f"   Components      : {summ.get('arch_a_components', '?')} → "
              f"{summ.get('arch_b_components', '?')} "
              f"(+{summ.get('components_added', 0)} / "
              f"-{summ.get('components_removed', 0)})")
        print(f"   Entities delta  : {comparison['entity_delta']:+d}")
        print(f"   Edges delta     : {comparison['edge_delta']:+d}")
        print(f"   Smells delta    : {comparison['smell_delta']:+d}")

        print("\n📈 Metric Trends")
        for name, trend in comparison.get("metric_trends", {}).items():
            if trend["old"] is None:
                print(f"   {name:<24} {trend['new']:.4f}  (new)")
            else:
                indicator = _trend(trend["old"], trend["new"])
                print(f"   {name:<24} {trend['old']:.4f} → {trend['new']:.4f}  {indicator}")

    print(f"\n{sep}\n")


def build_pr_comment(current: dict, comparison: dict | None = None) -> str:
    """Build a Markdown string suitable for posting as a PR comment."""
    lines: list[str] = []
    lines.append("## 🏗️ Architecture Self-Analysis")
    lines.append("")

    lines.append("### 📦 Snapshot")
    lines.append(
        "| Entities | Edges | Components | Smells |"
    )
    lines.append("|----------|-------|------------|--------|")
    lines.append(
        f"| {current['entities']} | {current['edges']} "
        f"| {len(current['components'])} | {len(current['smells'])} |"
    )
    lines.append("")

    lines.append("### 📊 Quality Metrics")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    for name, val in current["metrics"].items():
        lines.append(f"| {name} | `{val:.4f}` |")
    lines.append("")

    smells = current["smells"]
    lines.append(f"### 🚨 Architectural Smells ({len(smells)})")
    if smells:
        lines.append("| Severity | Type | Description |")
        lines.append("|----------|------|-------------|")
        for s in smells:
            emoji = _severity_emoji(s["severity"])
            desc = s["description"][:100]
            lines.append(f"| {emoji} {s['severity']} | {s['type']} | {desc} |")
    else:
        lines.append("✅ No smells detected")
    lines.append("")

    if comparison:
        lines.append("### 🔄 Evolution vs Baseline")
        summ = comparison.get("summary", {})
        sim = comparison.get("a2a_similarity")
        sim_str = f"`{sim:.4f}`" if sim is not None else "n/a"
        e_delta = comparison["entity_delta"]
        ed_delta = comparison["edge_delta"]
        sm_delta = comparison["smell_delta"]
        lines.append("| | Before | After | Delta |")
        lines.append("|---|--------|-------|-------|")
        lines.append(
            f"| Components | {summ.get('arch_a_components', '?')} "
            f"| {summ.get('arch_b_components', '?')} "
            f"| +{summ.get('components_added', 0)} / "
            f"-{summ.get('components_removed', 0)} |"
        )
        lines.append(
            f"| Entities | {current['entities'] - e_delta} "
            f"| {current['entities']} | `{e_delta:+d}` |"
        )
        lines.append(
            f"| Edges | {current['edges'] - ed_delta} "
            f"| {current['edges']} | `{ed_delta:+d}` |"
        )
        lines.append(
            f"| Smells | {len(current['smells']) - sm_delta} "
            f"| {len(current['smells'])} | `{sm_delta:+d}` |"
        )
        lines.append(f"| A2A Similarity | — | {sim_str} | — |")
        lines.append("")

        lines.append("### 📈 Metric Trends")
        lines.append("| Metric | Before | After | Trend |")
        lines.append("|--------|--------|-------|-------|")
        for name, trend in comparison.get("metric_trends", {}).items():
            if trend["old"] is None:
                lines.append(f"| {name} | — | `{trend['new']:.4f}` | _(new)_ |")
            else:
                indicator = _trend(trend["old"], trend["new"])
                lines.append(
                    f"| {name} | `{trend['old']:.4f}` | `{trend['new']:.4f}` | {indicator} |"
                )
        lines.append("")

    lines.append(
        "<sub>Generated by [arcade-agent](https://github.com/tuannx/arcade-agent) "
        "self-dogfooding CI</sub>"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Serialisation helpers (strip non-JSON fields before saving)
# ---------------------------------------------------------------------------

def _strip_runtime(data: dict) -> dict:
    """Return a copy of result dict without non-serialisable runtime objects."""
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_baseline(path: Path) -> dict:
    """Load a baseline JSON file produced by a previous run.

    Reconstructs an in-memory Architecture object so that A2A comparison
    is always available, even when comparing across CI runs.
    """
    with path.open() as fh:
        data = json.load(fh)

    # Reconstruct Architecture from stored component data
    components = [
        Component(
            name=c["name"],
            responsibility=c.get("responsibility", ""),
            entities=c.get("entities", []),
        )
        for c in data.get("components", [])
    ]
    data["_arch"] = Architecture(components=components)
    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Self-analysis CI script for arcade-agent"
    )
    parser.add_argument(
        "--source",
        default=".",
        help="Path to analyse (default: current directory)",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the current analysis JSON result",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="Path to a previous analysis JSON (enables before-after comparison)",
    )
    parser.add_argument(
        "--comment-output",
        default=None,
        dest="comment_output",
        help="Path to write the PR comment Markdown (optional)",
    )
    args = parser.parse_args()

    # Run current analysis
    print(f"[self-analysis] Analysing {args.source} ...")
    current = run_analysis(args.source)

    # Load baseline if provided
    baseline: dict | None = None
    if args.baseline:
        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            print(f"[self-analysis] Loading baseline from {args.baseline}")
            baseline = load_baseline(baseline_path)
        else:
            print(f"[self-analysis] Baseline not found at {args.baseline} — skipping comparison")

    # Compare if we have a baseline
    comparison: dict | None = None
    if baseline is not None:
        print("[self-analysis] Running before-after comparison ...")
        comparison = build_comparison(baseline, current)

    # Print summary to CI logs
    print_ci_summary(current, comparison)

    # Write output JSON (baseline for next run)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as fh:
        json.dump(_strip_runtime(current), fh, indent=2)
    print(f"[self-analysis] Analysis saved to {output_path}")

    # Write PR comment markdown
    if args.comment_output:
        comment_md = build_pr_comment(current, comparison)
        comment_path = Path(args.comment_output)
        comment_path.parent.mkdir(parents=True, exist_ok=True)
        with comment_path.open("w") as fh:
            fh.write(comment_md)
        print(f"[self-analysis] PR comment written to {comment_path}")


if __name__ == "__main__":
    main()
