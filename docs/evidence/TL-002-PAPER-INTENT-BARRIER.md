# TL-002 durable paper intent barrier

Status: first synthetic runtime-control slice for [issue #48](https://github.com/Loothore907/tidelab/issues/48), 2026-09-24. No engine order, external broker, account, credential, market-data acquisition, or trade occurs in this slice.

`src/tidelab/paper_intent.py` owns an isolated SQLite paper-authority database. It records a stable client ID, exact instrument, side, decimal quantity and limit price, and source-report revision. `prepare` is idempotent only for identical terms. Another intent is held while the first remains unresolved. `claim_once` uses an immediate SQLite transaction to change `prepared` to `submission_unknown` before its caller could invoke a synthetic paper source. A process exit, missing acknowledgment, or second caller cannot reset this state or authorize another submission. The module exposes no order-submission path and no automatic retry.

The focused tests check restart persistence, changed terms under the same client ID, invalid quantities/prices, and four independent Windows-compatible spawned processes contending for one claim. Exactly one claim succeeds. This establishes a local transaction boundary for the synthetic single-writer design, not durable brokerage reconciliation or LEAN integration. It assumes all future paper submission routes use this authority; bypassing it would defeat the gate.

Next, join this barrier to the selected pinned LEAN public brokerage route and an authoritative local paper report. Reconcile stable broker/execution IDs, order state, cash and holdings, corrections, and an absent-versus-unknown outcome before allowing a later order. Test a forced exit on both sides of the source call. Keep `submission_unknown` held until that evidence exists. This is separate from [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3); no real-data research permission or strategy result follows from this test.

The follow-on [synthetic local source check](TL-002-SYNTHETIC-LOCAL-RECONCILIATION.md) exercises both forced-exit windows in a same-database test double. It does not establish LEAN or external-source reconciliation.
