# arch-demo — a deterministic architectural-smell laboratory

A tiny synthetic Python shop used to demonstrate arcade-agent's smell detection
and `changelog_architecture` the way `mvn-perf/mvn-perf-examples` demonstrates
build parallelism: **planted, deterministic, one command to reproduce, one report
per scenario published to GitHub Pages.**

## The reactor (5 packages)

```
shop/
  billing/        invoice.py, pricing.py, events.py(after only)
  notifications/  emailer.py, sms.py
  utils/          helpers.py god module (before) / text.py, crypto.py, timex.py (after)
  orders/         service.py (orchestrator), validators.py
  auth/           login.py, tokens.py
```

## What is planted (before/)

1. **Dependency Cycle — Billing ↔ Notifications.**
   `billing/invoice.py` imports `notifications.emailer.send_receipt` to mail receipts,
   while `notifications/emailer.py` imports back into billing (`Invoice`, `subtotal`)
   to rebuild receipt lines. Two components, edges in both directions.
2. **Concern Overload — Utils.** `utils/helpers.py` is a 20-function god module
   (strings, crypto, dates, http, files, money) with zero internal cohesion:
   23 entities, 0.00 internal edges per entity.

Both are detected by the stock pipeline
(`ingest → parse → recover(pkg) → detect_smells → compute_metrics`).

## The refactor (after/)

- The cycle is broken with a domain event: billing publishes `InvoiceIssued`
  (`billing/events.py`); `orders/service.py` orchestrates delivery to notifications.
  Notifications now depends only on the event — edges flow one way.
- The god module is split; only the 4 helpers actually used survive, in cohesive
  modules (`text`, `crypto`, `timex`). 16 dead helpers are deleted.

## Expected result

| | before | after |
|---|---|---|
| entities | 39 | 20 |
| edges | 24 | 22 |
| components | 5 | 5 |
| smells | 2 (cycle + concern overload) | **0** |

`changelog_architecture(before, after)` reports `smells_resolved: 2`, 25 entities
deleted, 6 added, 0 new smells.

## Reproduce

```bash
pip install "arcade-agent[languages]"
python run_synthetic.py
# writes synthetic_before.html / synthetic_after.html / synthetic_summary.json
```

## CI

`ci.yml` is a GitHub Actions workflow that regenerates both HTML reports on every
push touching this directory and commits them back to the `gh-pages` branch —
one report per scenario, same pattern as mvn-perf's per-scenario Pages.
