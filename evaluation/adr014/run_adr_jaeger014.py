"""ADR-014 verification: jaegertracing/jaeger PR #9093 (base vs head). Small neutral control."""
import json, subprocess, time
from pathlib import Path
ROOT = Path(__file__).parent
REPO = ROOT / "repos" / "jaeger"
OUT = ROOT / "eval_out"; OUT.mkdir(exist_ok=True)
BASE = "e25782b69e8b071828f2f79f62383eca80e8c3cd"
HEAD = "f4c6acf1133dfe16e768723353807c9b8fa2ba98"
def sh(*a):
    return subprocess.run(a, cwd=REPO, capture_output=True, text=True, check=True)
def mat(sha, dest):
    dest = Path(dest)
    if not dest.exists():
        sh("git","fetch","--depth","1","origin",sha)
        sh("git","worktree","add","--detach",str(dest),sha)
    return dest
def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)): return [clean(v) for v in o]
    if isinstance(o,(str,int,float,bool)) or o is None: return o
    return str(o)
from arcade_agent.source.ingest import ingest
from arcade_agent.tools.parse import parse
from arcade_agent.tools.recover import recover
from arcade_agent.tools.detect_smells import detect_smells
from arcade_agent.tools.compute_metrics import compute_metrics
from arcade_agent.tools.changelog_architecture import changelog_architecture
V={}
for label,sha in (("base",BASE),("head",HEAD)):
    wt = ROOT/"repos"/f"jaeger014-{label}"
    print(f"[{label}] {sha[:8]}...", flush=True)
    mat(sha,wt); t0=time.time()
    repo=ingest(str(wt),language="go"); graph=parse(repo.path,language="go")
    arch=recover(graph,algorithm="pkg"); smells=detect_smells(arch,graph); metrics=compute_metrics(arch,graph)
    V[label]=dict(graph=graph,arch=arch,smells=smells,metrics=metrics)
    print(f"  entities={len(graph.entities)} edges={len(graph.edges)} components={len(arch.components)} smells={len(smells)} in {time.time()-t0:.1f}s",flush=True)
cl=changelog_architecture(V["base"]["arch"],V["base"]["graph"],V["head"]["arch"],V["head"]["graph"],
    smells_a=V["base"]["smells"],smells_b=V["head"]["smells"],metrics_a=V["base"]["metrics"],metrics_b=V["head"]["metrics"],
    ref_a="base e25782b6",ref_b="head f4c6acf1 (PR #9093)")
s={"adr":"jaegertracing/jaeger ADR-014: Synchronous Elasticsearch writes","pr":"https://github.com/jaegertracing/jaeger/pull/9093",
   "base_stats":{"entities":len(V["base"]["graph"].entities),"edges":len(V["base"]["graph"].edges),"components":len(V["base"]["arch"].components),"smells":len(V["base"]["smells"])},
   "head_stats":{"entities":len(V["head"]["graph"].entities),"edges":len(V["head"]["graph"].edges),"components":len(V["head"]["arch"].components),"smells":len(V["head"]["smells"])},
   "changelog":clean(cl)}
(OUT/"adr014_summary.json").write_text(json.dumps(s,indent=2))
print(json.dumps(s["changelog"].get("summary",{}),indent=2)); print("DONE")
