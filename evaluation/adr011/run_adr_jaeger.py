"""ADR-011 verification: jaegertracing/jaeger PR #8800 (base vs head).

ADR claims under test:
  C1. Two new thin facade layers appear: components/ and cmd/jaeger/components/
  C2. Facades are one-liners (var NewFactory = impl.NewFactory) - no logic
  C3. Double-dispatch breaks what would otherwise be an import cycle
      -> NO new dependency cycles introduced
  C4. No new external dependencies (facades re-export only)
"""
import json
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).parent
REPO = ROOT / "repos" / "jaeger"
OUT = ROOT / "eval_out"
OUT.mkdir(exist_ok=True)

BASE = "11b08c08b216d03e52f1d8df04f071ddf57091c3"
HEAD = "8c5ed8c35cefdcda4edbaf50abd4bf4411b61d25"


def sh(*args, cwd=REPO):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


def materialize(sha, dest):
    dest = Path(dest)
    if dest.exists():
        return dest
    sh("git", "fetch", "--depth", "1", "origin", sha)
    sh("git", "worktree", "add", "--detach", str(dest), sha)
    return dest


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    return str(o)


def main():
    from arcade_agent.source.ingest import ingest
    from arcade_agent.tools.parse import parse
    from arcade_agent.tools.recover import recover
    from arcade_agent.tools.detect_smells import detect_smells
    from arcade_agent.tools.compute_metrics import compute_metrics
    from arcade_agent.tools.changelog_architecture import changelog_architecture
    from arcade_agent.tools.visualize import visualize

    versions = {}
    for label, sha in (("base", BASE), ("head", HEAD)):
        wt = ROOT / "repos" / f"jaeger-{label}"
        print(f"[{label}] materializing {sha[:8]}...", flush=True)
        materialize(sha, wt)
        t0 = time.time()
        repo = ingest(str(wt), language="go")
        graph = parse(repo.path, language="go")
        arch = recover(graph, algorithm="pkg")
        smells = detect_smells(arch, graph)
        metrics = compute_metrics(arch, graph)
        dt = time.time() - t0
        versions[label] = dict(graph=graph, arch=arch, smells=smells, metrics=metrics)
        print(f"  entities={len(graph.entities)} edges={len(graph.edges)} "
              f"components={len(arch.components)} smells={len(smells)} in {dt:.1f}s",
              flush=True)
        for sm in smells:
            print(f"    smell: {sm.smell_type} [{sm.severity}] "
                  f"{','.join(sm.affected_components)}", flush=True)
        try:
            visualize(f"jaeger {label} (ADR-011 #{8800})", label, graph, arch,
                      smells, output=str(OUT / f"adr011_{label}.html"))
        except Exception as e:
            print(f"  visualize failed: {e}", flush=True)

    print("[changelog] ...", flush=True)
    cl = changelog_architecture(
        versions["base"]["arch"], versions["base"]["graph"],
        versions["head"]["arch"], versions["head"]["graph"],
        smells_a=versions["base"]["smells"], smells_b=versions["head"]["smells"],
        metrics_a=versions["base"]["metrics"], metrics_b=versions["head"]["metrics"],
        ref_a="base 11b08c08", ref_b="head 8c5ed8c3 (PR #8800)",
    )
    summary = {
        "adr": "jaegertracing/jaeger ADR-011: Custom Distributions via Public Facade Packages",
        "pr": "https://github.com/jaegertracing/jaeger/pull/8800",
        "base_stats": {
            "entities": len(versions["base"]["graph"].entities),
            "edges": len(versions["base"]["graph"].edges),
            "components": len(versions["base"]["arch"].components),
            "smells": len(versions["base"]["smells"]),
        },
        "head_stats": {
            "entities": len(versions["head"]["graph"].entities),
            "edges": len(versions["head"]["graph"].edges),
            "components": len(versions["head"]["arch"].components),
            "smells": len(versions["head"]["smells"]),
        },
        "changelog": clean(cl),
    }
    (OUT / "adr011_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["changelog"].get("summary", {}), indent=2))
    print("DONE")


if __name__ == "__main__":
    main()
