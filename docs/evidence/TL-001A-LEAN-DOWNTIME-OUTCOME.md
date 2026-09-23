# TL-001A LEAN synthetic downtime outcome probe

Status: bounded changed-outcome and fail-closed checkpoint on 2026-09-22 Alaska time. Issue [#2](https://github.com/Loothore907/tidelab/issues/2) remains open. This extends the [pending-order startup probe](TL-001A-LEAN-FORWARD-RECOVERY.md); it does not establish a complete forward-paper runner or adopt LEAN.

## Method

At pinned LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, a first process loaded one `Submitted` synthetic limit order with broker ID `TL001A-BROKER-ORDER-1`, then exited without teardown. A separate synthetic brokerage-report process changed the durable report while LEAN was stopped: the order became `Filled` with execution ID `TL001A-EXECUTION-1`, quantity 1 at 90, fee 0.09 USD, cash 9,909.91 USD, and holding 1. A fresh LEAN process then used its real `BrokerageSetupHandler` and `BrokerageTransactionHandler` with a mock `IBrokerage` reading that report. No exchange, account, real data, paid CLI, or live order was involved.

Two independent negative cases used the same TideLab-authored harness. One report was absent. Another claimed a filled execution and holding 1 but left cash at 10,000 USD, contradicting the 90 USD fill plus 0.09 USD fee. The harness validates the broker report before starting LEAN setup for changed outcomes; it emits `decision=BLOCK` and exits nonzero for missing or contradictory state. The report update uses a flushed temporary file followed by replacement of the synthetic report file. This is a probe policy, not a production reconciliation implementation.

Reproducer: `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>` on WSL/Linux. It checks the pinned commit, builds the TideLab-authored probe in the separate LEAN checkout, then runs pending, filled, contradictory, and missing-report cases with isolated temporary reports. Its completed run exited zero after all expected markers and exit states matched.

## Observed

- The pending seed process held one `Submitted` LEAN order and exited. A fresh pending restore remained successful after the harness change: one open order with the same broker ID, cash 10,000, holding 0, zero new submissions.
- After the synthetic brokerage changed the outcome, fresh LEAN setup called `GetCashBalance`, `GetOpenOrders`, and `GetAccountHoldings`, loaded cash 9,909.91 and holding 1, and found **zero** open orders. `PlaceOrder` was called zero times. LEAN's new transaction handler had zero orders; the closed execution ID and its accounting basis came from the separate brokerage report, not from LEAN's startup open-order API.
- The TideLab report check matched `10000 - 1 × 90 - 0.09 = 9909.91` and holding `1`. This arithmetic and the execution ID are synthetic fixture assertions, not broker-grade accounting proof.
- The missing-report and contradictory-report cases printed `decision=BLOCK ... new_submissions=0` and exited nonzero before LEAN setup. No new submission was possible in those blocked probe paths.
- The isolated .NET 10 Release build completed with 0 errors. The pinned LEAN dependency graph still emitted package audit warnings already described in the prior checkpoint.

## Limits and next gate

This comparison shows what the pinned LEAN setup API loads from brokerage snapshots: open orders and account balances/holdings. It did not reconstruct a closed order or its fill event in the fresh transaction handler. The TideLab harness used an explicit synthetic closed-execution report to reconcile the changed account state. Its guard covers only this one order and deliberately simple accounting; it has no genuine live data clock, strategy callback, order placement, partial fill, duplicate report, fee-currency conversion, or asynchronous event processing. A mock report cannot establish that any real or paper brokerage will provide complete, timely, authoritative data.

Next, test an actual synthetic forward-paper loop through LEAN's direct Launcher or document the executable obstacle, including an order submitted to the mock broker, a later fill, a process restart, and a reconciled event/ledger record. Keep the Nautilus external-Python-client/backing gap and TL-001B rights gate separate. Neither engine is adopted from these probes.
