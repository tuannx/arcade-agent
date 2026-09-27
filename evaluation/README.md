# arcade-agent real-world evaluation

Scripts and data behind https://tuannx.github.io/arcade-agent/

- `run_eval.py` — runs the full pipeline (`ingest → parse → recover → detect_smells → compute_metrics`)
  on Django, React and Vue.js (shallow HEAD clones), then computes `changelog_architecture`
  for three landmark large PRs (base vs head tarballs from codeload).
- `build_site.py` — renders `eval_out/*.json` into the static site.
- `eval_out/` — raw JSON results (scale summary + per-PR changelogs).

Requires: `pip install "arcade-agent[languages]"`, Python 3.12+.
