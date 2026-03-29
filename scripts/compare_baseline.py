#!/usr/bin/env python3
"""Compare current analysis results against a baseline and output Markdown.

Uses arcade-agent's compare tool (A2A analysis with Hungarian algorithm) for
proper architecture-to-architecture comparison when entity data is available.

Usage:
    python scripts/compare_baseline.py current.json baseline.json [--output comment.md]

Exits with code 0 always (comparison is informational, not a pass/fail gate).
"""

import argparse
import copy
import json
import os
import sys
from pathlib import Path

# Ensure arcade_agent is importable from src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arcade_agent.algorithms.architecture import Architecture, Component
from arcade_agent.exporters.html import export_evolution_html
from arcade_agent.tools.compare import compare


def _delta(new: float, old: float) -> str:
    diff = new - old
    if abs(diff) < 0.0001:
        return "→ (no change)"
    arrow = "↑" if diff > 0 else "↓"
    return f"{arrow} ({diff:+.4f})"


def _delta_with_impact(metric_name: str, new: float, old: float) -> str:
    """Format delta using metric quality semantics, not raw direction."""
    diff = new - old
    if abs(diff) < 0.0001:
        return "⚪ **→ (no change)**"

    arrow = "↑" if diff > 0 else "↓"
    better_when_higher = {"RCI", "TurboMQ", "BasicMQ"}
    better_when_lower = {"InterConnectivity", "TwoWayPairRatio"}
    low_impact = {"📦 Components", "🧩 Entities", "🔗 Edges", "IntraConnectivity"}

    if metric_name in better_when_higher:
        icon = "🟢" if diff > 0 else "🔴"
    elif metric_name in better_when_lower:
        icon = "🟢" if diff < 0 else "🔴"
    elif metric_name in low_impact:
        icon = "🟡"
    else:
        icon = "🟡"

    return f"{icon} **{arrow} ({diff:+.4f})**"


def _severity_icon(severity: str) -> str:
    return {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity.lower(), "⚪")


def _rci_icon(rci: float) -> str:
    if rci >= 0.8:
        return "🟢"
    if rci >= 0.6:
        return "🟡"
    return "🔴"


def _quality_label(rci: float) -> str:
    if rci >= 0.8:
        return "Good"
    if rci >= 0.6:
        return "Fair"
    return "Poor"


def _numeric_delta(new: float, old: float) -> str:
    diff = new - old
    if abs(diff) < 0.0001:
        return "0"
    sign = "+" if diff > 0 else ""
    if float(diff).is_integer():
        return f"{sign}{int(diff)}"
    return f"{sign}{diff:.4f}"


def _delta_class(new: float, old: float) -> str:
    diff = new - old
    if abs(diff) < 0.0001:
        return "delta-neutral"
    return "delta-positive" if diff > 0 else "delta-negative"


def _component_count(component: dict, key: str) -> int:
    return int(component.get(key, 0))


def _component_size(component: dict) -> int:
    return int(component.get("num_entities") or len(component.get("entities", [])))


def _component_map(data: dict | None) -> dict[str, dict]:
    if not data:
        return {}
    return {
        component.get("comparison_name", component["name"]): component
        for component in data.get("components", [])
    }


def _normalize_snapshot(data: dict | None) -> dict | None:
    """Return a copy with stable unique component labels for comparisons."""
    if not data:
        return None

    normalized = copy.deepcopy(data)
    components = normalized.get("components", [])
    total_counts: dict[str, int] = {}
    for component in components:
        total_counts[component["name"]] = total_counts.get(component["name"], 0) + 1

    seen_counts: dict[str, int] = {}
    rename_map: dict[str, list[str]] = {}
    for component in components:
        base_name = component["name"]
        seen_counts[base_name] = seen_counts.get(base_name, 0) + 1
        if total_counts[base_name] == 1:
            comparison_name = base_name
        else:
            comparison_name = f"{base_name} [{seen_counts[base_name]}]"
        component["comparison_name"] = comparison_name
        rename_map.setdefault(base_name, []).append(comparison_name)

    dependencies = normalized.get("component_dependencies", [])
    dependency_counters: dict[str, int] = {}
    for dependency in dependencies:
        for key in ("source", "target"):
            base_name = dependency[key]
            labeled_names = rename_map.get(base_name)
            if not labeled_names:
                continue
            dependency_counters[base_name] = dependency_counters.get(base_name, 0) + 1
            index = min(dependency_counters[base_name] - 1, len(labeled_names) - 1)
            dependency[key] = labeled_names[index]

    return normalized


def _dependency_set(data: dict | None) -> set[tuple[str, str]]:
    if not data:
        return set()
    return {
        (dep["source"], dep["target"])
        for dep in data.get("component_dependencies", [])
    }


def _build_metric_rows(current: dict, baseline: dict | None) -> list[dict]:
    metric_rows = []
    baseline_metrics = baseline.get("metrics", {}) if baseline else {}
    current_metrics = current.get("metrics", {})
    baseline_num_components = baseline.get("num_components", 0) if baseline else 0
    baseline_num_entities = baseline.get("num_entities", 0) if baseline else 0
    baseline_num_edges = baseline.get("num_edges", 0) if baseline else 0
    baseline_source_entities = (
        baseline.get("source_num_entities", baseline.get("num_entities", 0))
        if baseline
        else 0
    )
    baseline_class_count = baseline.get("class_count", 0) if baseline else 0
    baseline_function_count = baseline.get("function_count", 0) if baseline else 0
    baseline_method_count = baseline.get("method_count", 0) if baseline else 0

    summary_rows = [
        ("Components", baseline_num_components, current.get("num_components", 0)),
        ("Analysis Entities", baseline_num_entities, current.get("num_entities", 0)),
        ("Dependencies", baseline_num_edges, current.get("num_edges", 0)),
        (
            "Source Entities",
            baseline_source_entities,
            current.get("source_num_entities", current.get("num_entities", 0)),
        ),
        ("Classes", baseline_class_count, current.get("class_count", 0)),
        ("Functions", baseline_function_count, current.get("function_count", 0)),
        ("Methods", baseline_method_count, current.get("method_count", 0)),
    ]

    for name, old, new in summary_rows:
        metric_rows.append({
            "name": name,
            "baseline": old,
            "current": new,
            "delta": _numeric_delta(new, old),
            "delta_class": _delta_class(new, old),
        })

    metric_names = sorted(set(baseline_metrics) | set(current_metrics))
    for name in metric_names:
        old = baseline_metrics.get(name, 0.0)
        new = current_metrics.get(name, 0.0)
        metric_rows.append({
            "name": name,
            "baseline": f"{old:.4f}",
            "current": f"{new:.4f}",
            "delta": _numeric_delta(new, old),
            "delta_class": _delta_class(new, old),
        })

    return metric_rows


def _smell_count(data: dict | None) -> int:
    if not data:
        return 0
    return len(data.get("smells", []))


def _build_component_rows(
    current: dict,
    baseline: dict | None,
    a2a_result: dict | None,
) -> list[dict]:
    current_map = _component_map(current)
    baseline_map = _component_map(baseline)
    rows: list[dict] = []

    if not baseline:
        for component in sorted(
            current_map.values(),
            key=lambda comp: (-_component_size(comp), comp["name"]),
        ):
            rows.append({
                "status": "added",
                "baseline_name": "-",
                "current_name": component["name"],
                "similarity": "-",
                "entities": f"0 → {_component_size(component)}",
                "classes": f"0 → {_component_count(component, 'class_count')}",
                "methods": f"0 → {_component_count(component, 'method_count')}",
            })
        return rows

    matched_names: set[str] = set()
    if a2a_result:
        for match in a2a_result.get("matches", []):
            source_name = match.get("source")
            target_name = match.get("target")
            if source_name and target_name:
                source = baseline_map[source_name]
                target = current_map[target_name]
                source_entities = _component_size(source)
                target_entities = _component_size(target)
                source_classes = _component_count(source, "class_count")
                target_classes = _component_count(target, "class_count")
                source_methods = _component_count(source, "method_count")
                target_methods = _component_count(target, "method_count")
                rows.append({
                    "status": "matched",
                    "baseline_name": source_name,
                    "current_name": target_name,
                    "similarity": f"{match['similarity']:.4f}",
                    "entities": (
                        f"{source_entities} → {target_entities} "
                        f"({_numeric_delta(target_entities, source_entities)})"
                    ),
                    "classes": (
                        f"{source_classes} → {target_classes} "
                        f"({_numeric_delta(target_classes, source_classes)})"
                    ),
                    "methods": (
                        f"{source_methods} → {target_methods} "
                        f"({_numeric_delta(target_methods, source_methods)})"
                    ),
                })
                matched_names.add(source_name)
                matched_names.add(target_name)
            elif target_name:
                target = current_map[target_name]
                rows.append({
                    "status": "added",
                    "baseline_name": "-",
                    "current_name": target_name,
                    "similarity": "-",
                    "entities": f"0 → {_component_size(target)}",
                    "classes": f"0 → {_component_count(target, 'class_count')}",
                    "methods": f"0 → {_component_count(target, 'method_count')}",
                })
                matched_names.add(target_name)
            elif source_name:
                source = baseline_map[source_name]
                rows.append({
                    "status": "removed",
                    "baseline_name": source_name,
                    "current_name": "-",
                    "similarity": "-",
                    "entities": f"{_component_size(source)} → 0",
                    "classes": f"{_component_count(source, 'class_count')} → 0",
                    "methods": f"{_component_count(source, 'method_count')} → 0",
                })
                matched_names.add(source_name)

    for name, component in sorted(current_map.items()):
        if name not in matched_names:
            rows.append({
                "status": "added",
                "baseline_name": "-",
                "current_name": name,
                "similarity": "-",
                "entities": f"0 → {_component_size(component)}",
                "classes": f"0 → {_component_count(component, 'class_count')}",
                "methods": f"0 → {_component_count(component, 'method_count')}",
            })

    for name, component in sorted(baseline_map.items()):
        if name not in matched_names:
            rows.append({
                "status": "removed",
                "baseline_name": name,
                "current_name": "-",
                "similarity": "-",
                "entities": f"{_component_size(component)} → 0",
                "classes": f"{_component_count(component, 'class_count')} → 0",
                "methods": f"{_component_count(component, 'method_count')} → 0",
            })

    return rows


def _build_dependency_rows(current: dict, baseline: dict | None) -> list[dict]:
    current_deps = _dependency_set(current)
    baseline_deps = _dependency_set(baseline)
    rows = [
        {"status": "added", "source": source, "target": target}
        for source, target in sorted(current_deps - baseline_deps)
    ]
    rows.extend(
        {"status": "removed", "source": source, "target": target}
        for source, target in sorted(baseline_deps - current_deps)
    )
    if not rows:
        rows.append({"status": "matched", "source": "No dependency delta", "target": "-"})
    return rows


def build_report_payload(current: dict, baseline: dict | None, run_url: str = "") -> dict:
    """Build a unified before/after comparison payload."""
    baseline = _normalize_snapshot(baseline)
    current = _normalize_snapshot(current)
    a2a_result = _run_a2a_comparison(baseline, current) if baseline else None
    overview_cards = [
        {"label": "Current Components", "value": current.get("num_components", 0)},
        {"label": "Current Classes", "value": current.get("class_count", 0)},
        {"label": "Current Methods", "value": current.get("method_count", 0)},
        {
            "label": "A2A Similarity",
            "value": f"{a2a_result['overall_similarity']:.4f}" if a2a_result else "n/a",
        },
    ]
    return {
        "repo_name": "arcade-agent",
        "baseline_commit": (baseline or {}).get("commit_sha", "none")[:7] or "none",
        "current_commit": current.get("commit_sha", "local")[:7],
        "baseline": baseline,
        "current": current,
        "a2a_result": a2a_result,
        "overview_cards": overview_cards,
        "metric_rows": _build_metric_rows(current, baseline),
        "component_rows": _build_component_rows(current, baseline, a2a_result),
        "dependency_rows": _build_dependency_rows(current, baseline),
        "run_url": run_url,
    }


def _write_step_summary(path: Path, report: dict) -> None:
    """Write a compact unified GitHub step summary."""
    current = report["current"]
    baseline = report.get("baseline")
    current_metrics = current.get("metrics", {})
    current_rci = current_metrics.get("RCI", 0.0)
    current_tmq = current_metrics.get("TurboMQ", 0.0)
    rci_icon = _rci_icon(current_rci)
    quality_label = _quality_label(current_rci)
    lines = [
        "## 🏛️ Architecture Summary\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| 📦 Components | {current.get('num_components', 0)} |",
        f"| 🧩 Analysis Entities | {current.get('num_entities', 0)} |",
        f"| 🏷️ Classes | {current.get('class_count', 0)} |",
        f"| 🔧 Methods | {current.get('method_count', 0)} |",
        f"| RCI {rci_icon} | {current_rci:.4f} ({quality_label}) |",
        f"| TurboMQ | {current_tmq:.4f} |",
    ]

    if current.get("smells"):
        smell = current["smells"][0]
        lines.append(
            f"| Top Smell | {smell.get('smell_type', 'Unknown')} ({smell.get('severity', '?')}) |"
        )
    else:
        lines.append("| Smells | None detected |")

    if baseline:
        lines.append("\n## 🔄 Evolution Vs Baseline\n")
        lines.append("| Metric | Baseline | Current | Delta |")
        lines.append("|--------|----------|---------|-------|")
        for row in report["metric_rows"][:9]:
            lines.append(
                f"| {row['name']} | {row['baseline']} | {row['current']} | {row['delta']} |"
            )
        lines.append(
            f"| Smells | {_smell_count(baseline)} | {_smell_count(current)} | "
            f"{_numeric_delta(_smell_count(current), _smell_count(baseline))} |"
        )

    lines.append("\n## 🏗️ High-Level Components\n")
    lines.append("| Component | Entities | Classes | Methods |")
    lines.append("|-----------|----------|---------|---------|")
    for component in sorted(
        current.get("components", []),
        key=lambda comp: (-_component_size(comp), comp.get("comparison_name", comp["name"])),
    ):
        lines.append(
            f"| {component.get('comparison_name', component['name'])} | "
            f"{_component_size(component)} | {component.get('class_count', 0)} | "
            f"{component.get('method_count', 0)} |"
        )

    if baseline:
        lines.append("\n<details><summary>Component Changes</summary>\n")
        lines.append(
            "\n| Status | Baseline | Current | Similarity | Entities | Classes | Methods |"
        )
        lines.append("|--------|----------|---------|------------|----------|---------|---------|")
        for row in report["component_rows"]:
            lines.append(
                f"| {row['status']} | {row['baseline_name']} | {row['current_name']} | "
                f"{row['similarity']} | {row['entities']} | {row['classes']} | {row['methods']} |"
            )
        lines.append("\n</details>")

        dependency_delta = [
            row for row in report["dependency_rows"] if row["status"] != "matched"
        ]
        if dependency_delta:
            lines.append("\n<details><summary>Dependency Delta</summary>\n")
            lines.append("\n| Status | Source | Target |")
            lines.append("|--------|--------|--------|")
            for row in dependency_delta:
                lines.append(f"| {row['status']} | {row['source']} | {row['target']} |")
            lines.append("\n</details>")

    if report.get("run_url"):
        lines.append(
            f"\n📄 [Open workflow run and download comparison artifacts]({report['run_url']})"
        )

    path.write_text("\n".join(lines) + "\n")


def _reconstruct_architecture(data: dict) -> Architecture | None:
    """Reconstruct an Architecture object from stored JSON data."""
    components_data = data.get("components", [])
    if not components_data or "entities" not in components_data[0]:
        return None
    components = [
        Component(
            name=c.get("comparison_name", c["name"]),
            responsibility=c.get("responsibility", ""),
            entities=c.get("entities", []),
        )
        for c in components_data
    ]
    return Architecture(components=components, algorithm=data.get("algorithm", ""))


def _run_a2a_comparison(baseline: dict, current: dict) -> dict | None:
    """Run A2A comparison using arcade-agent's compare tool."""
    arch_a = _reconstruct_architecture(baseline)
    arch_b = _reconstruct_architecture(current)
    if arch_a is None or arch_b is None:
        return None
    return compare(arch_a, arch_b)


def build_comment(current: dict, baseline: dict | None, run_url: str = "") -> str:
    """Build a Markdown PR comment body."""
    lines: list[str] = []

    report = build_report_payload(current, baseline, run_url=run_url)
    current = report["current"]
    baseline = report.get("baseline")
    cur_metrics = current.get("metrics", {})
    cur_smells = current.get("smells", [])
    cur_components = current.get("components", [])
    cur_rci = cur_metrics.get("RCI", 0.0)
    cur_tmq = cur_metrics.get("TurboMQ", 0.0)

    rci_icon = _rci_icon(cur_rci)
    quality_label = _quality_label(cur_rci)

    lines.append("## 🤖 Architecture Analysis Summary\n")
    lines.append(
        "_Powered by [arcade-agent](https://github.com/tuannx/arcade-agent) — "
        "automatic architectural self-analysis_\n"
    )
    lines.append("---\n")

    # -- Metric evolution quick view (top) -------------------------------------
    if baseline:
        bl_metrics = baseline.get("metrics", {})
        bl_rci = bl_metrics.get("RCI", 0.0)
        bl_tmq = bl_metrics.get("TurboMQ", 0.0)
        bl_commit = baseline.get("commit_sha", "unknown")[:7]
        bl_components = baseline.get("num_components", 0)
        cur_components_count = current.get("num_components", 0)
        bl_entities = baseline.get("num_entities", 0)
        cur_entities_count = current.get("num_entities", 0)
        bl_edges = baseline.get("num_edges", 0)
        cur_edges_count = current.get("num_edges", 0)

        lines.append("### 📈 Metric Evolution\n")
        lines.append(f"_Baseline commit: `{bl_commit}`_\n")
        lines.append("_Legend: 🟢 better · 🔴 worse · 🟡 low impact · ⚪ no change_\n")
        lines.append("| Metric | Baseline | Current | Change |")
        lines.append("|--------|----------|---------|--------|")
        lines.append(
            f"| 📦 Components | {bl_components} "
            f"| {cur_components_count} "
            f"| {_delta_with_impact('📦 Components', cur_components_count, bl_components)} |"
        )
        lines.append(
            f"| 🧩 Entities | {bl_entities} "
            f"| {cur_entities_count} "
            f"| {_delta_with_impact('🧩 Entities', cur_entities_count, bl_entities)} |"
        )
        lines.append(
            f"| 🔗 Edges | {bl_edges} "
            f"| {cur_edges_count} "
            f"| {_delta_with_impact('🔗 Edges', cur_edges_count, bl_edges)} |"
        )
        class_delta = _delta_with_impact(
            '🧩 Entities',
            current.get('class_count', 0),
            baseline.get('class_count', 0),
        )
        function_delta = _delta_with_impact(
            '🧩 Entities',
            current.get('function_count', 0),
            baseline.get('function_count', 0),
        )
        method_delta = _delta_with_impact(
            '🧩 Entities',
            current.get('method_count', 0),
            baseline.get('method_count', 0),
        )
        lines.append(
            f"| 🏷️ Classes | {baseline.get('class_count', 0)} | "
            f"{current.get('class_count', 0)} | "
            f"{class_delta} |"
        )
        lines.append(
            f"| ƒ Functions | {baseline.get('function_count', 0)} | "
            f"{current.get('function_count', 0)} | "
            f"{function_delta} |"
        )
        lines.append(
            f"| 🔧 Methods | {baseline.get('method_count', 0)} | "
            f"{current.get('method_count', 0)} | "
            f"{method_delta} |"
        )
        lines.append(
            f"| RCI | {bl_rci:.4f} | {cur_rci:.4f} "
            f"| {_delta_with_impact('RCI', cur_rci, bl_rci)} |"
        )
        lines.append(
            f"| TurboMQ | {bl_tmq:.4f} | {cur_tmq:.4f} "
            f"| {_delta_with_impact('TurboMQ', cur_tmq, bl_tmq)} |"
        )
        for name in bl_metrics:
            if name not in ("RCI", "TurboMQ"):
                bl_v = bl_metrics.get(name, 0.0)
                cur_v = cur_metrics.get(name, 0.0)
                lines.append(
                    f"| {name} | {bl_v:.4f} | {cur_v:.4f} "
                    f"| {_delta_with_impact(name, cur_v, bl_v)} |"
                )
        lines.append("")

    # -- Current state -----------------------------------------------------------
    lines.append("### 🏛️ Current Architecture\n")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| 📦 Components | **{current.get('num_components')}** |")
    lines.append(f"| 🧩 Entities | **{current.get('num_entities')}** |")
    lines.append(f"| 🔗 Edges | **{current.get('num_edges')}** |")
    lines.append(f"| 🏷️ Classes | **{current.get('class_count', 0)}** |")
    lines.append(f"| ƒ Functions | **{current.get('function_count', 0)}** |")
    lines.append(f"| 🔧 Methods | **{current.get('method_count', 0)}** |")
    lines.append(f"| RCI {rci_icon} | **{cur_rci:.4f}** ({quality_label}) |")
    lines.append(f"| TurboMQ | **{cur_tmq:.4f}** |")
    for name, val in cur_metrics.items():
        if name not in ("RCI", "TurboMQ"):
            lines.append(f"| {name} | {val:.4f} |")
    lines.append("")

    # -- Components --------------------------------------------------------------
    if cur_components:
        lines.append("<details><summary>🏗️ Components breakdown</summary>\n")
        lines.append("| Component | Entities | Classes | Methods |")
        lines.append("|-----------|----------|---------|---------|")
        for comp in sorted(
            cur_components,
            key=lambda c: (
                -(c.get("num_entities") or len(c.get("entities", []))),
                c.get("comparison_name", c["name"]),
            ),
        ):
            count = comp.get("num_entities") or len(comp.get("entities", []))
            lines.append(
                f"| {comp.get('comparison_name', comp['name'])} | {count} | "
                f"{comp.get('class_count', 0)} | {comp.get('method_count', 0)} |"
            )
        lines.append("</details>\n")

    # -- Smells ------------------------------------------------------------------
    lines.append("### 🚨 Architectural Smells\n")
    if cur_smells:
        lines.append("| Severity | Type | Affected Components |")
        lines.append("|----------|------|---------------------|")
        for s in cur_smells:
            si = _severity_icon(s.get("severity", ""))
            stype = s.get("smell_type", "Unknown")
            comps = ", ".join(s.get("affected_components", []))
            lines.append(f"| {si} {s.get('severity','?')} | {stype} | {comps} |")
    else:
        lines.append("✅ No architectural smells detected.")
    lines.append("")

    # -- Evolution (before/after) ------------------------------------------------
    if baseline:
        bl_metrics = baseline.get("metrics", {})
        bl_rci = bl_metrics.get("RCI", 0.0)
        bl_tmq = bl_metrics.get("TurboMQ", 0.0)
        bl_smells = baseline.get("smells", [])
        bl_commit = baseline.get("commit_sha", "unknown")[:7]

        # Run A2A comparison via arcade-agent's compare tool
        a2a_result = _run_a2a_comparison(baseline, current)

        lines.append("### 📈 Evolution vs Baseline\n")
        lines.append(f"_Baseline commit: `{bl_commit}`_\n")

        # A2A similarity section
        if a2a_result:
            summary = a2a_result["summary"]
            lines.append("#### Architecture-to-Architecture (A2A) Comparison\n")
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| A2A Similarity | **{a2a_result['overall_similarity']:.4f}** |")
            lines.append(f"| Matched Components | {summary['total_matches']} |")
            lines.append(f"| Components Added | {summary['components_added']} |")
            lines.append(f"| Components Removed | {summary['components_removed']} |")
            if summary.get("possible_splits"):
                lines.append(f"| Possible Splits | {summary['possible_splits']} |")
            if summary.get("possible_merges"):
                lines.append(f"| Possible Merges | {summary['possible_merges']} |")
            lines.append("")

            # Component-level matches detail
            matches = a2a_result.get("matches", [])
            matched = [m for m in matches if m.get("source") and m.get("target")]
            added = [m for m in matches if not m.get("source")]
            removed = [m for m in matches if not m.get("target")]

            if matched or added or removed:
                lines.append("<details><summary>Component matching details</summary>\n")
                if matched:
                    lines.append("**Matched:**")
                    lines.append("| Baseline | Current | Similarity |")
                    lines.append("|----------|---------|------------|")
                    for m in sorted(matched, key=lambda x: -x["similarity"]):
                        lines.append(
                            f"| {m['source']} | {m['target']} | {m['similarity']:.4f} |"
                        )
                    lines.append("")
                if added:
                    lines.append("**New components:** " + ", ".join(
                        f"`{m['target']}`" for m in added
                    ))
                    lines.append("")
                if removed:
                    lines.append("**Removed components:** " + ", ".join(
                        f"`{m['source']}`" for m in removed
                    ))
                    lines.append("")
                lines.append("</details>\n")

        lines.append("<details><summary>High-level component statistics</summary>\n")
        lines.append("| Status | Baseline | Current | Similarity | Entities | Classes | Methods |")
        lines.append("|--------|----------|---------|------------|----------|---------|---------|")
        for row in report["component_rows"]:
            lines.append(
                f"| {row['status']} | {row['baseline_name']} | {row['current_name']} | "
                f"{row['similarity']} | {row['entities']} | {row['classes']} | {row['methods']} |"
            )
        lines.append("</details>\n")

        lines.append("<details><summary>Component dependency delta</summary>\n")
        lines.append("| Status | Source | Target |")
        lines.append("|--------|--------|--------|")
        for row in report["dependency_rows"]:
            lines.append(f"| {row['status']} | {row['source']} | {row['target']} |")
        lines.append("</details>\n")

        # Smell changes
        cur_smell_types = {s.get("smell_type") for s in cur_smells}
        bl_smell_types = {s.get("smell_type") for s in bl_smells}
        new_smells = cur_smell_types - bl_smell_types
        resolved_smells = bl_smell_types - cur_smell_types

        if new_smells or resolved_smells:
            lines.append("**Smell changes:**")
            for t in new_smells:
                lines.append(f"- 🆕 New smell: `{t}`")
            for t in resolved_smells:
                lines.append(f"- ✅ Resolved: `{t}`")
            lines.append("")

    else:
        lines.append(
            "> ℹ️ No baseline available — this is the first analysis run or the "
            "baseline artifact has expired. The current results will be stored "
            "as the new baseline.\n"
        )

    # -- CI/CD Insights ----------------------------------------------------------
    lines.append("### 💡 CI/CD Insights\n")
    lines.append(f"- **Quality Score**: {rci_icon} {quality_label} (RCI={cur_rci:.4f})")

    if baseline:
        bl_rci = baseline.get("metrics", {}).get("RCI", 0.0)
        rci_trend = cur_rci - bl_rci
        if rci_trend > 0.01:
            trend = "📈 Improving modularity"
        elif rci_trend < -0.01:
            trend = "📉 Declining cohesion — consider reviewing recent refactoring"
        else:
            trend = "➡️ Stable architectural quality"
        lines.append(f"- **Trend**: {trend}")

        # A2A insight
        a2a_result = _run_a2a_comparison(baseline, current)
        if a2a_result:
            sim = a2a_result["overall_similarity"]
            if sim >= 0.9:
                lines.append(f"- **Architecture Stability**: 🟢 High (A2A={sim:.4f})")
            elif sim >= 0.7:
                lines.append(f"- **Architecture Stability**: 🟡 Moderate (A2A={sim:.4f})")
            else:
                lines.append(
                    f"- **Architecture Stability**: 🔴 Low (A2A={sim:.4f}) "
                    "— significant restructuring detected"
                )

    smell_count = len(cur_smells)
    if smell_count == 0:
        lines.append("- **Smells**: ✅ Clean — no architectural smells")
    elif smell_count <= 2:
        lines.append(f"- **Smells**: ⚠️ {smell_count} smell(s) — review suggested")
    else:
        lines.append(f"- **Smells**: 🔴 {smell_count} smells — refactoring recommended")

    if run_url:
        lines.append(f"\n📄 [View HTML reports and artifacts]({run_url})")

    lines.append("\n---")
    lines.append(
        "_This comment is auto-generated by the self-dogfooding CI job. "
        "It updates on every push to this PR._"
    )

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare architecture results vs baseline")
    parser.add_argument("current", help="Path to current analysis JSON")
    parser.add_argument("baseline", nargs="?", help="Path to baseline JSON (optional)")
    parser.add_argument(
        "--output",
        default="pr_comment.md",
        help="Output file for the generated Markdown comment",
    )
    parser.add_argument(
        "--run-url",
        default="",
        help="GitHub Actions run URL for artifact linking",
    )
    parser.add_argument(
        "--output-html",
        default="",
        help="Optional output path for the generated HTML comparison report",
    )
    args = parser.parse_args()

    current_path = Path(args.current)
    if not current_path.exists():
        print(f"Error: current results file not found: {current_path}", file=sys.stderr)
        sys.exit(1)

    current = json.loads(current_path.read_text())
    baseline: dict | None = None

    if args.baseline:
        bl_path = Path(args.baseline)
        if bl_path.exists():
            baseline = json.loads(bl_path.read_text())
            print(f"Loaded baseline from {bl_path}")
        else:
            print(f"Baseline file not found: {bl_path} — running without baseline")

    report = build_report_payload(current, baseline, run_url=args.run_url)
    comment = build_comment(current, baseline, run_url=args.run_url)

    out = Path(args.output)
    out.write_text(comment)
    print(f"PR comment written to {out}")

    if args.output_html:
        html_out = Path(args.output_html)
        export_evolution_html(report, html_out)
        print(f"HTML comparison report written to {html_out}")

    summary_file = Path(os.environ.get("GITHUB_STEP_SUMMARY", "/dev/null"))
    if summary_file != Path("/dev/null"):
        _write_step_summary(summary_file, report)

    # Also print inline summary to CI logs
    print("\n" + "=" * 60)
    print("BEFORE/AFTER COMPARISON SUMMARY")
    print("=" * 60)
    if baseline:
        bl_metrics = baseline.get("metrics", {})
        bl_rci = bl_metrics.get("RCI", 0.0)
        cur_rci = current.get("metrics", {}).get("RCI", 0.0)

        # A2A comparison
        a2a_result = _run_a2a_comparison(baseline, current)
        if a2a_result:
            summary = a2a_result["summary"]
            print(f"  A2A Similarity: {a2a_result['overall_similarity']:.4f}")
            print(
                f"  Components:  {summary['arch_a_components']} → "
                f"{summary['arch_b_components']} "
                f"(+{summary['components_added']} / -{summary['components_removed']})"
            )
            if summary.get("possible_splits"):
                print(f"  Possible Splits: {summary['possible_splits']}")
            if summary.get("possible_merges"):
                print(f"  Possible Merges: {summary['possible_merges']}")
        else:
            print(
                f"  Components:  {baseline.get('num_components')} → "
                f"{current.get('num_components')} "
                f"{_delta(current.get('num_components', 0), baseline.get('num_components', 0))}"
            )

        print(
            f"  Entities:    {baseline.get('num_entities')} → "
            f"{current.get('num_entities')} "
            f"{_delta(current.get('num_entities', 0), baseline.get('num_entities', 0))}"
        )
        print(
            f"  Edges:       {baseline.get('num_edges')} → "
            f"{current.get('num_edges')} "
            f"{_delta(current.get('num_edges', 0), baseline.get('num_edges', 0))}"
        )
        print(
            f"  Classes:     {baseline.get('class_count', 0)} → "
            f"{current.get('class_count', 0)} "
            f"{_delta(current.get('class_count', 0), baseline.get('class_count', 0))}"
        )
        print(
            f"  Methods:     {baseline.get('method_count', 0)} → "
            f"{current.get('method_count', 0)} "
            f"{_delta(current.get('method_count', 0), baseline.get('method_count', 0))}"
        )
        print(
            f"  RCI:         {bl_rci:.4f} → {cur_rci:.4f} {_delta(cur_rci, bl_rci)}"
        )
        print(
            f"  TurboMQ:     {bl_metrics.get('TurboMQ', 0):.4f} → "
            f"{current.get('metrics', {}).get('TurboMQ', 0):.4f} "
            f"{_delta(current.get('metrics', {}).get('TurboMQ', 0), bl_metrics.get('TurboMQ', 0))}"
        )
        cur_smell_count = len(current.get("smells", []))
        bl_smell_count = len(baseline.get("smells", []))
        print(f"  Smells:      {bl_smell_count} → {cur_smell_count}")

    else:
        print("  No baseline available — first run or baseline expired.")
        cur_rci = current.get("metrics", {}).get("RCI", 0.0)
        print(f"  Components:  {current.get('num_components')}")
        print(f"  Entities:    {current.get('num_entities')}")
        print(f"  Classes:     {current.get('class_count', 0)}")
        print(f"  Methods:     {current.get('method_count', 0)}")
        print(f"  RCI:         {cur_rci:.4f}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
