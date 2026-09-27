"""Evaluation: run arcade-agent on large OSS repos + landmark large PRs.

Outputs JSON summaries + HTML reports under ./eval_out/.
"""
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).parent / "eval_out"
REPO_DIR = Path(__file__).parent / "repos"
OUT.mkdir(exist_ok=True)
REPO_DIR.mkdir(exist_ok=True)

REPOS = {
    "django": {
        "url": "https://github.com/django/django.git",
        "language": "python",
        "homepage": "https://www.djangoproject.com/",
    },
    "react": {
        "url": "https://github.com/facebook/react.git",
        "language": "typescript",
        "homepage": "https://react.dev/",
    },
    "vue": {
        "url": "https://github.com/vuejs/core.git",
        "language": "typescript",
        "homepage": "https://vuejs.org/",
    },
}

# Landmark large PRs: (repo_key, owner/repo, pr_number, base_sha, head_sha, title, url)
PRS = [
    (
        "react", "facebook/react", 37187,
        "44fe7e953a05", "c89931b2c4e0",
        "[DevTools] Remove the dead Timeline profiler code",
        "https://github.com/facebook/react/pull/37187",
    ),
    (
        "vue", "vuejs/core", 15633,
        "a429b2a6fd43", "7dd8954e8cfa",
        "chore: migrate to Vitest 5 with Vite+",
        "https://github.com/vuejs/core/pull/15633",
    ),
    (
        "django", "django/django", 18036,
        "d876be794f59", "3ab611d7a1d9",
        "Fixed #35303 -- Added async auth backends and associated functionality",
        "https://github.com/django/django/pull/18036",
    ),
]


def sh(cmd, cwd=None):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        print("CMD FAILED:", cmd, "\n", r.stderr[-2000:])
        raise SystemExit(1)
    return r.stdout.strip()


def ensure_repo(key, url):
    dest = REPO_DIR / key
    if not (dest / ".git").exists():
        print(f"[clone] {key} ...", flush=True)
        sh(f"git clone --depth 1 {url} {dest}")
    else:
        print(f"[exists] {key}", flush=True)
    return dest


def summarize_analysis(result):
    arch = result.architecture
    smells = result.smells or []
    metrics = {m.name: m.value for m in (result.metrics or [])}
    comp_sizes = sorted([len(c.entities) for c in arch.components], reverse=True)
    return {
        "num_entities": len(result.graph.entities),
        "num_edges": len(result.graph.edges),
        "num_components": len(arch.components),
        "algorithm": arch.algorithm,
        "largest_components": comp_sizes[:10],
        "num_smells": len(smells),
        "smells_by_type": {},
        "metrics": metrics,
    }


def main():
    from arcade_agent.tools.analyze import analyze
    from arcade_agent.source.ingest import ingest
    from arcade_agent.tools.parse import parse
    from arcade_agent.tools.recover import recover
    from arcade_agent.tools.detect_smells import detect_smells
    from arcade_agent.tools.compute_metrics import compute_metrics
    from arcade_agent.tools.changelog_architecture import changelog_architecture
    from arcade_agent.tools.visualize import visualize

    summary = {"repos": {}, "prs": {}}

    # ---- Phase 1: full-repo scale analysis ----
    if (OUT / "scale_summary.json").exists():
        print("[skip] Phase 1 already done", flush=True)
        summary["repos"] = json.loads((OUT / "scale_summary.json").read_text())
    else:
        for key, cfg in REPOS.items():
            dest = ensure_repo(key, cfg["url"])
            print(f"[analyze] {key} ({cfg['language']}) ...", flush=True)
            t0 = time.time()
            result = asyncio.run(analyze(str(dest), language=cfg["language"]))
            dt = time.time() - t0
            s = summarize_analysis(result)
            s["analysis_seconds"] = round(dt, 1)
            s["homepage"] = cfg["homepage"]
            # smell type breakdown
            by_type = {}
            for sm in result.smells or []:
                by_type[sm.smell_type] = by_type.get(sm.smell_type, 0) + 1
            s["smells_by_type"] = by_type
            summary["repos"][key] = s
            print(f"  -> entities={s['num_entities']} edges={s['num_edges']} "
                  f"components={s['num_components']} smells={s['num_smells']} "
                  f"in {dt:.0f}s", flush=True)
            # HTML report
            rep_path = OUT / f"{key}_report.html"
            try:
                visualize(result.graph and dest.name or key, "HEAD",
                          result.graph, result.architecture, result.smells or [],
                          output=str(rep_path))
                print(f"  report: {rep_path.name}", flush=True)
            except Exception as e:
                print(f"  visualize failed: {e}", flush=True)

    (OUT / "scale_summary.json").write_text(json.dumps(summary["repos"], indent=2))

    # ---- Phase 2: PR architectural changelogs ----
    # GitHub blocks fetching arbitrary SHAs over git, but codeload tarballs
    # work for any commit SHA.
    for repo_key, gh_repo, pr_num, base_sha, head_sha, title, url in PRS:
        lang = REPOS[repo_key]["language"]
        pr_key = f"{repo_key}-{pr_num}"
        print(f"[pr] {repo_key}#{pr_num}: downloading {base_sha[:8]}..{head_sha[:8]}",
              flush=True)
        versions = {}
        for label, sha in (("base", base_sha), ("head", head_sha)):
            dest = REPO_DIR / "pr" / pr_key / label
            if not dest.exists():
                dest.mkdir(parents=True)
                tgz = dest / "src.tgz"
                sh(f"curl -sSL -o {tgz} https://github.com/{gh_repo}/archive/{sha}.tar.gz")
                sh(f"tar xzf {tgz} -C {dest} --strip-components=1")
                tgz.unlink()
            print(f"  [{label}] ingest+parse+recover ...", flush=True)
            t0 = time.time()
            repo = ingest(str(dest), language=lang)
            graph = parse(repo.path, language=lang)
            arch = recover(graph, algorithm="pkg")
            smells = detect_smells(arch, graph)
            metrics = compute_metrics(arch, graph)
            dt = time.time() - t0
            versions[label] = dict(repo=repo, graph=graph, arch=arch,
                                  smells=smells, metrics=metrics)
            print(f"    entities={len(graph.entities)} edges={len(graph.edges)} "
                  f"components={len(arch.components)} smells={len(smells)} "
                  f"in {dt:.0f}s", flush=True)
            # HTML report per revision
            rep_path = OUT / f"pr_{pr_key}_{label}.html"
            try:
                visualize(f"{repo_key} PR#{pr_num} {label}", sha[:8],
                          graph, arch, smells, output=str(rep_path))
            except Exception as e:
                print(f"    visualize failed: {e}", flush=True)
        print("  [changelog] ...", flush=True)
        cl = changelog_architecture(
            versions["base"]["arch"], versions["base"]["graph"],
            versions["head"]["arch"], versions["head"]["graph"],
            smells_a=versions["base"]["smells"], smells_b=versions["head"]["smells"],
            metrics_a=versions["base"]["metrics"], metrics_b=versions["head"]["metrics"],
            ref_a=f"PR#{pr_num} base {base_sha[:8]}",
            ref_b=f"PR#{pr_num} head {head_sha[:8]}",
        )
        pr_key = f"{repo_key}-{pr_num}"
        # make JSON-serializable (drop non-serializable internals)
        def clean(o):
            if isinstance(o, dict):
                return {k: clean(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return [clean(v) for v in o]
            if isinstance(o, (str, int, float, bool)) or o is None:
                return o
            return str(o)
        pr_summary = {
            "repo": repo_key, "pr": pr_num, "title": title, "url": url,
            "base": base_sha, "head": head_sha,
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
        summary["prs"][pr_key] = pr_summary
        (OUT / f"pr_{pr_key}.json").write_text(json.dumps(pr_summary, indent=2))
        print(f"  saved pr_{pr_key}.json", flush=True)

    (OUT / "full_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print("DONE. outputs in", OUT)


if __name__ == "__main__":
    main()
