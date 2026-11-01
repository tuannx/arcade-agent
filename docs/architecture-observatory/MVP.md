# MVP: Java Architecture PR Reviewer

## Input
Repository commit SHA, optional baseline SHA, configuration file, source inclusion/exclusion rules.

## Pipeline
`ingest -> parse -> graph -> component recovery -> deterministic rules -> baseline diff -> verification -> report`

## Initial checks
1. Forbidden package/layer imports.
2. Circular module dependencies.
3. New boundary crossings introduced by a PR.
4. Unresolved imports and unsupported language features as explicit unknowns.

## Finding contract
```json
{
  "rule_id": "domain-no-infrastructure",
  "status": "violation",
  "severity": "error",
  "location": {"path": "src/main/java/example/domain/Payment.java", "line": 12},
  "evidence": [{"kind": "static-import", "target": "example.infrastructure.StripeClient"}],
  "confidence": "high",
  "verification": "static",
  "baseline": "new",
  "unknowns": []
}
```

## Delivery stages
- M1: freeze schema and config, golden fixtures, reproducible CLI JSON.
- M2: baseline diff, PR annotation, GitHub Action.
- M3: compiler/test verification and false-positive benchmark.
- M4: optional MCP and HTML projection.

## Acceptance
- All golden fixtures produce expected findings.
- Every reported rule violation has an exact source location.
- No duplicate PR findings across reruns.
- CI does not block on heuristic smells by default.
- Test report includes pass/fail and environment limitations.
- Proof bundle includes commit SHA, CI URL and genuine screenshots of PR annotations/dashboard captured after execution.

## Proof policy
Never present a mockup as a screenshot. Screenshots must come from a real running UI or CI run, with repository, commit and timestamp documented.
