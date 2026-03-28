#!/usr/bin/env python3
"""Parse an arcade-agent HTML report and print a formatted summary to stdout.

Usage:
    python scripts/log_analysis_results.py <report.html>

This script is intended to be run inside a CI job immediately after
``basic_analysis.py`` generates the HTML report.  It extracts key metrics,
the architecture summary, and detected smells from the HTML and prints them
as plain text so they are immediately visible in the GitHub Actions log
without requiring artifact downloads.
"""

import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Regex-based parsers
# The HTML report is generated from a fixed Jinja2 template (see
# src/arcade_agent/exporters/html.py), so the structure is stable enough
# for simple pattern matching.
# ---------------------------------------------------------------------------

# Matches: <div class="stat-card">
#              <div class="number">115</div>
#              <div class="label">Entities</div>
#          </div>
_STAT_CARD_RE = re.compile(
    r'<div\s+class="stat-card">\s*'
    r'<div\s+class="number">(\d+)</div>\s*'
    r'<div\s+class="label">([^<]+)</div>',
    re.DOTALL,
)

# Matches: <div class="metric-card">
#              <div class="value">0.529</div>
#              <div class="name">RCI</div>
#          </div>
_METRIC_CARD_RE = re.compile(
    r'<div\s+class="metric-card">\s*'
    r'<div\s+class="value">([^<]+)</div>\s*'
    r'<div\s+class="name">([^<]+)</div>',
    re.DOTALL,
)

# Matches a component table row (tbody rows only — skip thead).
# Template: <td><strong>Name</strong></td><td>Responsibility</td><td>Count</td>
_COMP_ROW_RE = re.compile(
    r'<td><strong>([^<]+)</strong></td>\s*'
    r'<td>([^<]*)</td>\s*'
    r'<td>(\d+)</td>',
    re.DOTALL,
)

# Used inside each smell block to extract type and description.
_SMELL_TYPE_RE = re.compile(r'<strong>([^<]+)</strong>')
_SMELL_DESC_RE = re.compile(r'<p\s+class="smell-detail">([^<]+)</p>')


# ---------------------------------------------------------------------------
# Public parsing function
# ---------------------------------------------------------------------------

def parse_report(html: str) -> dict[str, Any]:
    """Parse an arcade-agent HTML report and return structured data.

    Args:
        html: Full HTML content of the report.

    Returns:
        Dictionary with keys: ``stats``, ``metrics``, ``components``,
        ``smells``.  Each value is a list or dict of extracted strings.
    """
    # Overview stat cards
    stats: dict[str, str] = {}
    for number, label in _STAT_CARD_RE.findall(html):
        stats[label.strip()] = number.strip()

    # Quality metric cards
    metrics: list[tuple[str, str]] = [
        (name.strip(), value.strip())
        for value, name in _METRIC_CARD_RE.findall(html)
    ]

    # Architecture components (table rows in the Components section)
    # Restrict to the region between the Components and Smells headings to
    # avoid accidentally matching rows in other tables.
    comp_section_match = re.search(
        r'<h2[^>]*>\s*Components\s*</h2>(.*?)<h2',
        html,
        re.DOTALL,
    )
    components: list[tuple[str, str, str]] = []
    if comp_section_match:
        components = [
            (name.strip(), responsibility.strip(), count.strip())
            for name, responsibility, count in _COMP_ROW_RE.findall(comp_section_match.group(1))
        ]

    # Architectural smells
    # Restrict to the Smells section, then split by outer smell divs (which
    # use class="smell high|medium|low").  We split rather than use a greedy
    # lookahead to avoid the inner "smell-header" class triggering early.
    smell_section_match = re.search(
        r'<h2[^>]*>\s*Architectural Smells.*?</h2>(.*?)(?:<h2|<footer)',
        html,
        re.DOTALL,
    )
    smells: list[dict[str, str]] = []
    if smell_section_match:
        smell_html = smell_section_match.group(1)
        # Split on the start of each outer smell div.
        parts = re.split(
            r'(?=<div\s+class="smell\s+(?:high|medium|low)">)',
            smell_html,
        )
        for part in parts:
            sev_match = re.match(r'<div\s+class="smell\s+(high|medium|low)">', part)
            if not sev_match:
                continue
            severity = sev_match.group(1)
            type_match = _SMELL_TYPE_RE.search(part)
            desc_match = _SMELL_DESC_RE.search(part)
            smells.append({
                "severity": severity,
                "type": type_match.group(1).strip() if type_match else "",
                "description": desc_match.group(1).strip() if desc_match else "",
            })

    return {
        "stats": stats,
        "metrics": metrics,
        "components": components,
        "smells": smells,
    }


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _severity_icon(severity: str) -> str:
    """Return an emoji icon for a smell severity level.

    Args:
        severity: One of ``"high"``, ``"medium"``, or ``"low"``.
            Any other value returns a neutral white circle (⚪).

    Returns:
        A single emoji string representing the severity.
    """
    return {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(severity, "⚪")


def _quality_label(rci: float | None) -> str:
    """Return a human-readable quality label based on the RCI score.

    RCI (Ratio of Cohesive Interactions) measures how well entities are
    grouped into cohesive components relative to total coupling.  Higher
    values indicate a more modular architecture.

    Args:
        rci: The RCI metric value, or ``None`` if not available.

    Returns:
        A coloured label string: 🟢 GOOD (≥ 0.8), 🟡 NEEDS ATTENTION
        (≥ 0.6), 🔴 POOR (< 0.6), or ``"N/A"`` if *rci* is ``None``.
    """
    if rci is None:
        return "N/A"
    if rci >= 0.8:
        return "🟢 GOOD"
    if rci >= 0.6:
        return "🟡 NEEDS ATTENTION"
    return "🔴 POOR"


def print_summary(data: dict) -> None:
    """Print a human-readable summary of the parsed report data.

    Args:
        data: Dictionary returned by :func:`parse_report`.
    """
    sep = "━" * 60
    print()
    print("🏗️  Architecture Self-Analysis Results")
    print(sep)

    # ── Overview stats ───────────────────────────────────────────────
    stats = data["stats"]
    print("📊 Overview:")
    for label in ("Entities", "Dependencies", "Components", "Smells"):
        value = stats.get(label, "?")
        print(f"   • {label}: {value}")

    # ── Quality metrics ──────────────────────────────────────────────
    metrics = data["metrics"]
    if metrics:
        print()
        print("📈 Quality Metrics:")
        rci_value: float | None = None
        for name, value in metrics:
            print(f"   • {name}: {value}")
            if name.upper() == "RCI":
                try:
                    rci_value = float(value)
                except ValueError:
                    pass
        print(f"   Quality Assessment: {_quality_label(rci_value)}")
    else:
        print()
        print("📈 Quality Metrics: (none computed)")

    # ── Architecture summary ─────────────────────────────────────────
    components = data["components"]
    if components:
        print()
        print(f"🧩 Components ({len(components)} recovered):")
        for name, responsibility, count in components:
            label = f" — {responsibility}" if responsibility else ""
            print(f"   • {name}{label} [{count} entities]")

    # ── Smells ──────────────────────────────────────────────────────
    smells = data["smells"]
    print()
    if smells:
        print(f"🚨 Architectural Smells ({len(smells)} detected):")
        for smell in smells:
            icon = _severity_icon(smell["severity"])
            print(f"   {icon} [{smell['severity'].upper()}] {smell['type']}")
            if smell.get("description"):
                desc = smell["description"]
                if len(desc) > 100:
                    desc = desc[:97] + "..."
                print(f"      {desc}")
    else:
        print("✅ No architectural smells detected.")

    print(sep)
    print()


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <report.html>", file=sys.stderr)
        sys.exit(1)

    report_path = Path(sys.argv[1])
    if not report_path.exists():
        print(f"Error: report file not found: {report_path}", file=sys.stderr)
        sys.exit(1)

    html = report_path.read_text(encoding="utf-8")
    data = parse_report(html)
    print_summary(data)


if __name__ == "__main__":
    main()
