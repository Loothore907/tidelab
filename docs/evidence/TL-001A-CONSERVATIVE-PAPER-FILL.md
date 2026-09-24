# TL-001A conservative fill and paper restart checkpoint

Status: synthetic engine-selection evidence for [issue #2](https://github.com/Loothore907/tidelab/issues/2), 2026-09-24 Alaska time. Neither LEAN nor NautilusTrader is adopted. No market data, account, credential, order, or paid service was used.

## Working selection boundary

The owner accepted a bounded TideLab-owned paper-source boundary as a reasonable candidate design. TL-001A is selecting an engine for reproducible historical research and local forward-paper evaluation. It is not selecting a live broker or proving a profitable strategy. An initial selection may rely on synthetic compatibility evidence; TL-005 will separately test a structurally different adapter.

TideLab may own four replaceable responsibilities: venue/product capabilities and conservative execution assumptions; stable client/execution identity and authoritative paper order/account reports; durable reconciliation and a hold on new submissions until broker, journal, and engine agree; and engine-independent experiment identity/export. The engine should still supply replay, clock/dispatch, portfolio, and public brokerage/fill extension seams. If TideLab must reproduce general order matching, portfolio accounting, or engine internals, or maintain a private engine fork, the integration exceeds this working boundary and the engine choice must be reconsidered.

Before selection, require a pinned candidate and reproducible evidence for one shared historical/forward strategy and risk rule; explicit costs and product rules; conservative partial, missed, rejected and stale outcomes; accounting and restart invariants through a replaceable paper authority; a protected next-order route after reconciliation; experiment provenance; and a maintainable distribution/upgrade path. These are selection evidence, not a claim that TL-002 is already built. A future external brokerage requires its own authoritative lookup, snapshot, correction and submission guarantees.

## Focused synthetic case

`TL001A_CONSERVATIVE_ONLY=1 bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned LEAN checkout> <dotnet 10 binary>` copies TideLab-authored probe files into an isolated checkout at LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, builds, and runs the focused phases. Repository CI neither compiles this C# probe nor runs the shell script.

One versioned rule set specifies USD, 0.01 price tick, 0.1 quantity lot, 0.1% fee rounded to six USD decimals, one tick of adverse slippage, minimum notional 1 USD, and a two-minute maximum quote age. The invented bid/ask is 100/100.20 with 0.4 units displayed on each side. A one-unit buy at 18:00 UTC sees a quote from 17:59. The TideLab policy caps its initial modeled fill at the displayed 0.4 units: **partial fill 0.4 at 100.21, fee 0.040084 USD, remainder 0.6**. Starting with 1,000 USD and zero holding yields 959.875916 USD cash and 0.4 holding. The same policy produces a sell-side partial at 99.99 with 0.039996 USD fee; a stale quote or less than one displayed lot holds, and an invalid lot rejects.

The historical check enters the custom policy through LEAN's public `FillModel.Fill` dispatch on a synthetic US-equity symbol and asserts the returned `OrderEvent` quantity, price, fee, and partial status. The forward double calls that same policy, writes one stable execution/account report, then exits the process. A fresh LEAN brokerage setup reads the report and restores one partially filled open order, cash, and holding. A repeat fresh setup agrees and makes zero submissions. A deliberately altered cash report blocks before setup. The synthetic paper report is the authority in this case; there is no initial LEAN submission or external broker.

Observed focused runner: build **0 errors**, with upstream dependency audit and SDK warnings. The phases printed:

```text
phase=historical fill=0.4@100.21 fee=0.040084 remaining=0.6 stale=HOLD no_lot=HOLD bad_order=REJECT
phase=forward_seed execution=committed fill=0.4@100.21 remaining=0.6 cash=959.875916 holding=0.4 new_submissions=0
phase=conservative_forward_restore decision=HOLD_REMAINING_OPEN cash=959.875916 holding=0.4 open_orders=1 new_submissions=0
phase=conservative_forward_repeat decision=HOLD_REMAINING_OPEN cash=959.875916 holding=0.4 open_orders=1 new_submissions=0
phase=mismatch decision=BLOCK_FILL_OR_ACCOUNT_MISMATCH new_submissions=0
```

## What the result changes

This removes the default full-fill assumption for this one synthetic buy and demonstrates that an explicit rule can feed LEAN's historical fill seam while its paper report can restore a matching partial state. It strengthens the case that the fill policy can remain TideLab-owned and replaceable. It does **not** establish that displayed size is executable, correct real fill probabilities, a venue-specific fee schedule, complete sell-side P&L, a managed historical Launcher run using this model, or an uninterrupted paper submission through fill, recovery, and the next safe order. The report writer is a test double, not a production journal or broker adapter. A partial order is held after restart; the remaining 0.6 is not automatically filled or resubmitted.

The decisive remaining paper test should join a stable intent, conservative partial/missed/rejected outcomes, execution IDs, ledger and LEAN account state, correction/restart, and a conditional next-order submission under one authority. It should block on a revision, identity, or account mismatch and make zero new submissions while ambiguous. Count the TideLab-owned code and upgrade/distribution obligations against the boundary above before selecting LEAN. TL-001B data rights remains independent; this synthetic result supplies no strategy-performance evidence.
