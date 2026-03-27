#!/usr/bin/env python3
"""Compare recovery algorithms (PKG, ACDC, ARC) on the same project.

Usage:
    python examples/compare_algorithms.py /path/to/project [--language java]
    python examples/compare_algorithms.py /path/to/project --use-llm

Generates a single HTML report with side-by-side comparison of all algorithms.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from arcade_agent.exporters.html import AlgorithmResult, export_comparison_html
from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.ingest import ingest
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover


def main():
    parser = argparse.ArgumentParser(description="Compare recovery algorithms")
    parser.add_argument("source", help="Path to source code directory or git URL")
    parser.add_argument("--language", "-l", default=None, help="Language (java, python)")
    parser.add_argument("--output", "-o", default="comparison_report.html", help="Output file")
    parser.add_argument("--use-llm", action="store_true", help="Use Claude CLI for ARC and smell detection")
    args = parser.parse_args()

    # 1. Ingest & parse (shared)
    print(f"[1/2] Ingesting {args.source}...")
    repo = ingest(args.source, language=args.language)
    print(f"  Found {len(repo.source_files)} source files ({repo.language})")

    if not repo.source_files:
        print("  No source files found. Exiting.")
        return

    print(f"[2/2] Parsing dependencies...")
    graph = parse(str(repo.path), language=repo.language, files=[str(f) for f in repo.source_files])
    print(f"  {graph.num_entities} entities, {graph.num_edges} edges\n")

    algorithms = [
        ("pkg", {}),
        ("acdc", {}),
        ("arc", {"hybrid_weight": 0.5}),
    ]

    results = []
    for i, (algo, kwargs) in enumerate(algorithms, 1):
        label = algo.upper()
        print(f"[{label}] Recovering architecture...")
        arch = recover(graph, algorithm=algo, **kwargs)
        print(f"  {len(arch.components)} components")

        use_llm = args.use_llm and algo == "arc"
        print(f"[{label}] Detecting smells{' (LLM)' if use_llm else ''}...")
        smells = detect_smells(arch, graph, use_llm=use_llm)
        print(f"  {len(smells)} smells")

        print(f"[{label}] Computing metrics...")
        metrics = compute_metrics(arch, graph)

        concerns = {}
        if args.use_llm:
            print(f"[{label}] Extracting concerns...")
            from arcade_agent.algorithms.concern import extract_concerns_llm
            concerns = extract_concerns_llm(arch, graph)

        results.append(AlgorithmResult(
            algorithm=algo,
            architecture=arch,
            smells=smells,
            metrics=metrics,
            concerns=concerns,
        ))
        print()

    # Generate comparison report
    print("Generating comparison report...")
    output_path = Path(args.output)
    export_comparison_html(repo.name, repo.version, graph, results, output_path)
    print(f"Report written to: {output_path}")

    # Print metrics summary
    print("\n--- Metrics Summary ---")
    metric_names = [m.name for m in results[0].metrics]
    header = f"{'Metric':<25}" + "".join(f"{r.algorithm.upper():>10}" for r in results)
    print(header)
    print("-" * len(header))
    for name in metric_names:
        row = f"{name:<25}"
        for r in results:
            val = next((m.value for m in r.metrics if m.name == name), 0)
            row += f"{val:>10.4f}"
        print(row)

    repo.cleanup()


if __name__ == "__main__":
    main()
