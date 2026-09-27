"""Build the static evaluation site from eval_out/*.json -> site/."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "eval_out"
SITE = ROOT / "site"
SITE.mkdir(exist_ok=True)

CSS = """
:root{--bg:#0d1117;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff;--card:#161b22;--line:#30363d;--ok:#3fb950;--warn:#d29922}
*{box-sizing:border-box}body{background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;margin:0;line-height:1.6}
.wrap{max-width:1020px;margin:0 auto;padding:0 24px}
header.hero{padding:72px 0 40px;border-bottom:1px solid var(--line)}
.hero h1{font-size:2.6rem;margin:0 0 8px}.hero h1 .a{color:var(--acc)}
.hero p.sub{color:var(--mut);font-size:1.15rem;max-width:760px}
.badges{margin:20px 0;display:flex;gap:10px;flex-wrap:wrap}
.badge{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:4px 14px;font-size:.85rem;color:var(--mut)}
.badge b{color:var(--fg)}
.btn{display:inline-block;background:#1f6feb;color:#fff;padding:10px 22px;border-radius:8px;text-decoration:none;font-weight:600;margin:6px 8px 6px 0}
.btn.ghost{background:transparent;border:1px solid var(--line);color:var(--fg)}
h2{margin:48px 0 12px;font-size:1.6rem}h3{margin:28px 0 8px}
table{width:100%;border-collapse:collapse;margin:16px 0;font-size:.95rem}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:600}td.num{font-variant-numeric:tabular-nums}
tr:hover td{background:#ffffff06}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:22px;margin:18px 0}
.card h3{margin:0 0 6px}.card h3 a{color:var(--acc);text-decoration:none}
.meta{color:var(--mut);font-size:.88rem;margin:8px 0}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}
.kv div{background:#0d1117;border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.kv .v{font-size:1.35rem;font-weight:700}.kv .k{color:var(--mut);font-size:.8rem}
.delta-up{color:var(--ok)}.delta-dn{color:#f85149}.delta-flat{color:var(--mut)}
ul.tight li{margin:6px 0}code{background:#ffffff12;padding:2px 6px;border-radius:6px;font-size:.88em}
pre{background:#0d1117;border:1px solid var(--line);border-radius:8px;padding:14px;overflow:auto;font-size:.85rem}
footer{border-top:1px solid var(--line);margin-top:64px;padding:28px 0;color:var(--mut);font-size:.9rem}
a{color:var(--acc)}nav.top{padding:14px 0;border-bottom:1px solid var(--line);font-size:.95rem}
nav.top a{margin-right:18px;text-decoration:none;color:var(--mut)}nav.top a:hover{color:var(--fg)}
.tag{display:inline-block;font-size:.75rem;border:1px solid var(--line);border-radius:12px;padding:1px 10px;color:var(--mut);margin-right:6px}
"""

HEADER = """<nav class="top"><div class="wrap">
<a href="./index.html"><b style="color:#e6edf3">arcade-agent</b> · evaluation</a>
<a href="./index.html#scale">Scale benchmark</a>
<a href="./index.html#prs">PR case studies</a>
<a href="./index.html#method">Methodology</a>
<a href="https://github.com/arcade-agent/arcade-agent">GitHub</a>
</div></nav>"""

FOOTER = """<footer><div class="wrap">
<p>Evaluation generated with <a href="https://github.com/arcade-agent/arcade-agent">arcade-agent</a> (open-source, MIT).
Results are automatically recovered architecture views — heuristic, not ground truth.
<a href="https://github.com/tuannx/arcade-agent">Fork with this evaluation</a>.</p>
<p style="color:#6e7681">Built 2026-09-27 · Xuan / AI Kit LLC</p>
</div></footer>"""


def page(title, body):
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · arcade-agent evaluation</title><style>{CSS}</style></head>
<body>{HEADER}<div class="wrap">{body}</div>{FOOTER}</body></html>"""


NARRATIVES = {
    "react-37187": {
        "story": ("19,239 lines deleted — and the architecture didn't move. "
                  "Every recovered component is stable: no additions, removals, renames, splits or merges, "
                  "and zero responsibility shifts. Metric deltas are noise (TurboMQ −0.005, RCI −0.004). "
                  "That is exactly the answer a reviewer wants from a dead-code removal PR: "
                  "<b>surgical, zero architectural risk, safe to merge</b> — computed, not guessed."),
        "signals": [
            "310 entities deleted, 0 added — the deletion is visible and quantified",
            "7/7 components stable at PKG granularity — nothing was restructured",
            "Persisting finding the tool keeps surfacing: a medium-severity dependency cycle "
            "<code>Compiler ↔ Fixtures ↔ Packages</code> that survived the deletion",
        ],
    },
    "vue-15633": {
        "story": ("The PR title says 'test infra migration' — the architecture diff names what actually moved. "
                  "Five benchmark entities (<code>packages.reactivity.__benchmarks__.*.bench</code>) shifted "
                  "from the <b>Packages</b> component to <b>Scripts</b> as Vitest 5 re-homed them. "
                  "TurboMQ dipped 3.00 → 2.82, reflecting the churn. "
                  "A maintainer gets the structural story without opening 30 files."),
        "signals": [
            "5 responsibility shifts, all in <code>__benchmarks__</code> — the migration's real footprint",
            "35 entities added / 60 deleted — mostly config and runner code",
            "No component added or removed — the migration stayed inside existing boundaries",
        ],
    },
    "django-18036": {
        "story": ("A new capability — async auth backends — landed with essentially <b>zero architectural disturbance</b>. "
                  "+43 entities, 19/19 components stable, metrics flat (RCI −0.0001). "
                  "The only movement worth noting: <code>aauthenticate</code> settling from Views into Contrib and "
                  "<code>aget_user</code> from Contrib into Utils — the new async variants finding their architectural homes. "
                  "This is the 'safe feature PR' signal maintainers want in CI."),
        "signals": [
            "+43 entities / 1 deleted — pure addition, no restructuring",
            "2 responsibility shifts pinpoint the new async surface",
            "Smell count unchanged (17 → 17) — no new architectural debt introduced",
        ],
    },
}


def fmt(n):
    return f"{n:,}"


def main():
    full = json.loads((OUT / "full_summary.json").read_text())
    repos = full["repos"]
    prs = full["prs"]

    repo_names = {"django": "Django", "react": "React", "vue": "Vue.js"}
    repo_urls = {
        "django": "https://github.com/django/django",
        "react": "https://github.com/facebook/react",
        "vue": "https://github.com/vuejs/core",
    }

    # ---------- index ----------
    rows = []
    for key, s in repos.items():
        m = s["metrics"]
        rows.append(
            f"<tr><td><a href='{repo_urls[key]}'><b>{repo_names[key]}</b></a> "
            f"<a href='./reports/{key}_report.html' class='tag'>report</a></td>"
            f"<td class='num'>{fmt(s['num_entities'])}</td>"
            f"<td class='num'>{fmt(s['num_edges'])}</td>"
            f"<td class='num'>{s['num_components']}</td>"
            f"<td class='num'>{s['num_smells']}</td>"
            f"<td class='num'>{m.get('RCI', 0):.3f}</td>"
            f"<td class='num'>{m.get('TurboMQ', 0):.1f}</td>"
            f"<td class='num'>{s['analysis_seconds']:.0f}s</td></tr>"
        )
    scale_table = ("<table><tr><th>Repository</th><th>Entities</th><th>Edges</th>"
                   "<th>Components</th><th>Smells</th><th>RCI</th><th>TurboMQ</th>"
                   "<th>Analysis time</th></tr>" + "".join(rows) + "</table>")

    pr_cards = []
    for pr_key, p in prs.items():
        b, h = p["base_stats"], p["head_stats"]
        d_comp = h["components"] - b["components"]
        d_smell = h["smells"] - b["smells"]
        cls_c = "delta-up" if d_comp > 0 else ("delta-dn" if d_comp < 0 else "delta-flat")
        cls_s = "delta-dn" if d_smell > 0 else ("delta-up" if d_smell < 0 else "delta-flat")
        pr_cards.append(f"""<div class="card"><h3><a href="./pr-{pr_key}.html">{p['repo']} #{p['pr']}</a></h3>
<div class="meta">{p['title']}</div>
<div class="kv">
<div><div class="v">{fmt(b['entities'])} → {fmt(h['entities'])}</div><div class="k">entities</div></div>
<div><div class="v">{b['components']} → {h['components']} <span class="{cls_c}">({d_comp:+d})</span></div><div class="k">components</div></div>
<div><div class="v">{b['smells']} → {h['smells']} <span class="{cls_s}">({d_smell:+d})</span></div><div class="k">smells</div></div>
</div>
<div class="meta"><a href="{p['url']}">View PR on GitHub ↗</a></div></div>""")

    index_body = f"""
<header class="hero">
<h1><span class="a">arcade-agent</span> in the wild</h1>
<p class="sub">Can an AI-agent tool library recover the architecture of the world's largest
open-source codebases — and narrate what a landmark pull request changed architecturally?
We ran it on Django, React and Vue.js, then diffed the architecture across three large PRs.</p>
<div class="badges">
<span class="badge"><b>{sum(s['num_entities'] for s in repos.values()):,}</b> entities parsed</span>
<span class="badge"><b>{sum(s['num_edges'] for s in repos.values()):,}</b> dependencies</span>
<span class="badge"><b>{len(prs)}</b> large-PR case studies</span>
<span class="badge">100% open methodology</span>
</div>
<a class="btn" href="https://github.com/arcade-agent/arcade-agent">Star on GitHub</a>
<a class="btn ghost" href="#method">How it was measured</a>
</header>

<h2 id="scale">Scale benchmark</h2>
<p>Full pipeline — <code>ingest → parse → recover (PKG) → detect_smells → compute_metrics</code> —
on a shallow HEAD clone, tests excluded. One command per repo:</p>
<pre>python -m asyncio -c "await analyze('/path/to/django', language='python')"</pre>
{scale_table}
<p class="meta">RCI = relative cluster index (cohesion); TurboMQ = Bunch-style modularization quality (higher = better).
Times measured on a single commodity VM, cold parse, tree-sitter based.</p>

<h2 id="prs">Large-PR case studies</h2>
<p>For each PR we recovered the architecture at the base commit and at the merge commit,
then ran <code>changelog_architecture</code> — the same tool arcade-agent's GitHub Action uses
to comment on PRs. Click through for the full architectural changelog.</p>
{''.join(pr_cards)}

<h2 id="method">Methodology &amp; reproducibility</h2>
<ul class="tight">
<li><b>Parser:</b> tree-sitter per language (Python, TypeScript/JavaScript). Test, vendor and build directories excluded.</li>
<li><b>Recovery:</b> PKG algorithm (package-structure clustering), identical settings for every repo and every revision.</li>
<li><b>PR diffing:</b> <code>ingest(ref=&lt;base_sha&gt;)</code> and <code>ingest(ref=&lt;head_sha&gt;)</code> materialize each revision without touching the working tree.</li>
<li><b>Honesty note:</b> recovered architectures are heuristic approximations. Component names come from package structure; smell detection is threshold-based unless <code>--use-llm</code> is enabled.</li>
<li><b>Reproduce:</b> <code>pip install "arcade-agent[languages]"</code>, then run the scripts in
<a href="https://github.com/tuannx/arcade-agent/tree/gh-pages/evaluation">tuannx/arcade-agent/evaluation</a> (gh-pages branch).</li>
</ul>

<h2>What this proves</h2>
<ul class="tight">
<li><b>For AI-agent builders:</b> a single <code>analyze()</code> call gives an agent a structural map of a 10k-file codebase in minutes — cheaper than reading files.</li>
<li><b>For maintainers:</b> <code>changelog_architecture</code> turns "what did this PR do to our architecture?" from a manual review question into a computed answer.</li>
<li><b>For everyone:</b> architecture recovery isn't a research toy anymore — it runs on Django, React and Vue at commodity cost.</li>
</ul>
"""
    (SITE / "index.html").write_text(page("Real-world evaluation", index_body))

    # ---------- per-PR pages ----------
    for pr_key, p in prs.items():
        cl = p["changelog"]
        b, h = p["base_stats"], p["head_stats"]
        nar = NARRATIVES.get(pr_key, {})
        story = f"<div class='card'><h3>What the tool saw</h3><p>{nar.get('story','')}</p><ul class='tight'>" + "".join(
            f"<li>{s}</li>" for s in nar.get("signals", [])) + "</ul></div>" if nar else ""
        body = f"""
<header class="hero" style="padding:48px 0 24px">
<p class="meta"><a href="./index.html">← all case studies</a></p>
<h1 style="font-size:2rem">{p['repo']} <a href="{p['url']}">#{p['pr']}</a></h1>
<p class="sub">{p['title']}</p>
<div class="badges"><span class="badge">base <code>{p['base'][:8]}</code></span>
<span class="badge">head <code>{p['head'][:8]}</code></span></div>
</header>
{story}
<div class="kv">
<div><div class="v">{fmt(b['entities'])} → {fmt(h['entities'])}</div><div class="k">entities</div></div>
<div><div class="v">{fmt(b['edges'])} → {fmt(h['edges'])}</div><div class="k">dependency edges</div></div>
<div><div class="v">{b['components']} → {h['components']}</div><div class="k">recovered components</div></div>
<div><div class="v">{b['smells']} → {h['smells']}</div><div class="k">architectural smells</div></div>
</div>
<h2>Architectural changelog</h2>
<p class="meta">Computed by <code>changelog_architecture(base, head)</code> — components added/removed/renamed/rewritten/split/merged, entity moves, smell &amp; metric deltas.</p>
<pre>{json.dumps(cl, indent=2, ensure_ascii=False)[:12000]}</pre>
<p class="meta">Full JSON: <code>eval_out/pr_{pr_key}.json</code> in the
<a href="https://github.com/tuannx/arcade-agent/tree/gh-pages/evaluation">evaluation folder</a>.
Full interactive reports: <a href="./reports/pr_{pr_key}_base.html">base</a> ·
<a href="./reports/pr_{pr_key}_head.html">head</a>.
Discuss this PR: <a href="{p['url']}">{p['url']}</a></p>
"""
        (SITE / f"pr-{pr_key}.html").write_text(
            page(f"{p['repo']} #{p['pr']}", body))

    print("site written to", SITE, "-", len(list(SITE.glob('*.html'))), "pages")


if __name__ == "__main__":
    main()
