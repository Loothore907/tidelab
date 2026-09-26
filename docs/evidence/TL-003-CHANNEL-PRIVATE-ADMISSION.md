# Channel v1 private admission through the shared workflow

Owner: [#95](https://github.com/Loothore907/tidelab/issues/95). Classification: one approved research evaluation plus its exact admission implementation. Base: main `9eed1226eee8ac92709f58ce98abd58e741388b4`, where PR #106 integrated the [source-backed channel implementation](TL-003-CHANNEL-BREAKOUT-SYNTHETIC.md). No trading-rule, source revision, sizing, cost or review threshold changes belong to this slice.

## Outcome, authority and reuse

The owner explicitly approved the frozen private proposal after implementation review: add and independently review the exact admission, integrate after CI, then take one snapshot and execute one 30-job private batch. The ignored proposal and `CHANNEL-BREAKOUT-V1-TRIAL-AUTHORITY.json` bind that decision, the selected v2 intake record, fixed window/universe, costs, five-trip descriptive floor and stop conditions. No other candidate, variant, retry, later partition, acquisition, spend, account, order or publication is authorized. Keep #3 and #48 independent.

`private_workflow.py` extracts the established snapshot, fixed plan, package/partition policy and batch execution from RSI. Its two concrete bindings are frozen RSI and channel v1. Bindings supply exact authority, package, window and review; the shared module grants nothing. Existing replay, fees, ledger, metrics, recovery and review code remain the execution path. There is no second backtester or new source frontend.

`channel_private.py` has no database initializer or arbitrary registry/date/market/parameter flags. It verifies the permanent RSI store anchor and original authorization before appending a distinct channel authorization. The original anchor, grant and historical records must remain intact. The new authorization pins the integrated head; proposal, authority and selected record hashes are fixed in code. Missing stores, changed identities and spent stages fail closed. Snapshot reservation happens before prices; batch reservation happens before snapshot-byte verification and replay. Failures consume their stage rather than enabling another attempt.

The shared snapshot reader selects only the frozen hourly window in one source transaction. It preserves actual OHLC, verifies continuity, closure and archive provenance, hashes local archive bytes without parsing outside-window prices, and freezes the snapshot before batch admission. The channel package uses 480 preceding bars. RSI retains 336 preceding bars, the original hashes/grant/window and its 20-trip review floor.

## Acceptance and operation

Synthetic tests exercise the complete new grant-to-30-job workflow on invented archives, with an invalid outside-window payload that must never be parsed. They verify append-only accounting, retained diagnostics, recovery without replay, unchanged old grant/anchor, duplicate rejection, absent/mismatched authority, changed code, missing store, altered preparation/snapshot identity, fixed-plan rejection, current terms and the CLI timeout. Old RSI and channel/native-LEAN tests remain regression coverage.

Run synthetic verification with `python -m pytest tests/test_channel_private.py tests/test_rsi_private.py tests/test_channel_breakout.py`. Runtime sources include both bindings and shared workflow in every new batch identity.

Only after distinct review, merged-main CI and a current official terms review, the approved local sequence is `scripts/channel_private_batch.py authorize`, then `prepare`, then `run`, each with `--terms-reviewed-utc-date YYYY-MM-DD`. The run command enforces a hard 1,800-second child-process limit. Timeout retains consumed admission and incomplete artifacts; no retry or automatic recovery is launched. Direct Python calls are internal implementation/testing interfaces, not an alternative approved operating sequence.

All research artifacts remain under ignored `data/research_program/channel-v1/`. Audit retained manifests, full job/trial accounting, cash/inventory/fees, signal/fill timing, terminal marks, diagnostics and frozen dispositions without replaying the trial. A separate reviewer audits the retained result. Preserve all prior program rows when appending the new grant and batch. Do not publish market metrics, rankings, traces or derived reports.

Exact-head checks, independent review and integration are recorded on the PR. Public source/synthetic evidence establishes admission behavior, not profitable performance. Private results can nominate deeper review only; no eligible market closes v1 without tuning. Any incomplete job prevents batch nomination, and any further action requires a new decision.
