# Evidence-Backed Architecture Observatory

## Purpose
Turn source code and verified runtime evidence into a queryable, versioned architecture model. This is not a generic 3D simulator.

## Product loop
1. Ingest a pinned repository commit.
2. Parse source and construct a provenance-aware dependency graph.
3. Recover candidate components and compare against explicit architecture contracts.
4. Produce findings with source spans, rule IDs, evidence types, confidence and unknowns.
5. Compare with the baseline; report only newly introduced violations on PRs.
6. Verify using compiler, tests and optionally runtime traces.
7. Publish JSON, CLI and PR reports; record reviewer feedback.
8. Repeat on new commits. Never auto-merge unverified changes.

## Four distinct views
- Intended: rules and ADRs declared by maintainers.
- Recovered: architecture inferred from static analysis.
- Runtime: observed behavior and dependencies.
- Evolution: changes across commits and pull requests.

## MVP scope
Java / Spring Boot first; JSON output and GitHub PR comments. Reuse existing arcade-agent ingest, parser, graph, metrics and smells where applicable. No 3D, no mandatory LLM and no claims of causal prediction without measured evidence.

## Quality gates
- Deterministic reruns on the same commit and configuration.
- Every finding links to a source span or explicitly states evidence is missing.
- Rule violations are distinguishable from heuristic smells.
- No regression in existing tests.
- Report unknown/unsupported constructs rather than inventing architecture.

See [MVP](MVP.md) and [Architecture Decision](ADR-0001.md).
