# Cross-repository dogfooding protocol

## Goal
Improve arcade-agent by running it on its own source and diverse real repositories. Findings must drive reproducible regression tests and measured improvements, not just attractive reports.

## Initial corpus
| Repository | Language / focus | Evidence status |
|---|---|---|
| tuannx/arcade-agent | Python self-analysis | Pending fresh run |
| tuannx/spring-boot-multi-region-ha | Java / Spring Boot | Pending |
| tuannx/python-multi-agent-ha | Python async / agents | Pending |
| tuannx/arcade-agent-examples | Integration examples | Pending |
| tuannx/arcade-agent-action | GitHub Action | Pending |

## Iteration contract
1. Pin repository URL, commit SHA, analyzer SHA, configuration and environment.
2. Execute real analysis; record commands, exit codes, graph size, metrics, warnings, time and resource use.
3. Triage findings: verified violation, heuristic lead, false positive, unsupported or unknown.
4. Convert one concrete weakness into a minimal fixture that fails before the fix.
5. Make the smallest engine change; rerun targeted and full available tests.
6. Rerun affected repositories and compare before/after with identical settings.
7. Open/update PR with logs and CI artifact links; capture genuine screenshots of CI/PR/UI where possible.
8. Record limitations, regressions and next iteration.

## Proof record
```yaml
repository: owner/name
repository_sha: <40-char-sha>
analyzer_sha_before: <40-char-sha>
analyzer_sha_after: <40-char-sha>
command: <exact-command>
environment: <runner-and-tool-versions>
result: pass|fail|blocked|not-run
before: {entities: null, edges: null, findings: null}
after: {entities: null, edges: null, findings: null}
verified_findings: []
false_positives: []
unsupported: []
ci_url: null
screenshot_url: null
notes: ""
```

## Guardrails
- Never call a screenshot proof unless it was captured from a real running interface.
- Never claim improvement based only on a reduced smell count.
- Distinguish failed checks from checks not run.
- No automated merge without an explicit applicable authorization.
- Preserve private repository confidentiality in public artifacts.
