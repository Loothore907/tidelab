# TL-001A LEAN synthetic submission and reconciliation checkpoint

Status: bounded execution-path probe on 2026-09-22 Alaska time. Issue [#2](https://github.com/Loothore907/tidelab/issues/2) remains open. Neither LEAN nor NautilusTrader is adopted.

## Method

The TideLab-authored probe ran against unmodified LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` with an isolated .NET 10 SDK. LEAN's `BrokerageSetupHandler` initialized a new `QCAlgorithm`, `BrokerageTransactionHandler`, and mock `IBrokerage` with synthetic USD 10,000 cash and no open orders. The algorithm called LEAN's `LimitOrder` for one synthetic `TL001ASYN` unit at 90. The mock broker's `PlaceOrder` received exactly one order, assigned `TL001A-BROKER-ORDER-1`, and flushed a pending broker report. It also emitted a `Submitted` order-status event. The seed process checked that LEAN retained the broker-acknowledged pending order, then exited without teardown.

While LEAN was stopped, the synthetic brokerage step replaced its report with a full fill: execution ID `TL001A-EXECUTION-1`, quantity 1 at 90, fee 0.09 USD, cash 9,909.91 USD, and holding 1. A fresh process loaded the report through LEAN setup. A TideLab probe record then captured the broker and execution IDs, quantity, fill price, fee, and resulting balances. Repeating the restore verified that same record rather than writing a second one.

In a separate same-process control, the mock broker emitted a LEAN `Filled` order-status event after its `Submitted` acknowledgement. LEAN delivered the fill to the algorithm callback and updated cash and holdings. A subsequent fresh startup read the synthetic filled report. The earlier pending, contradictory-report, and missing-report paths were rerun in the same temporary fixture sequence.

The reproducible command is `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>` on WSL/Linux. The script requires the exact LEAN source commit, copies TideLab probe files into the separate checkout, builds the isolated test runner, and checks all expected markers and exit states. It creates only local temporary synthetic reports and removes them after the run. The shell file is forced to LF line endings on Windows by `.gitattributes`.

## Observed

- One LEAN `LimitOrder` reached mock `IBrokerage.PlaceOrder`. The first LEAN process retained one `Submitted` order with the assigned broker ID before process loss.
- An earlier variant returned success from `PlaceOrder` without emitting a broker `Submitted` event. LEAN's ticket and cached open order stayed `New`; waiting 10 seconds did not turn them `Submitted`. The probe now emits the broker acknowledgement explicitly. A successful mock `PlaceOrder` return alone must not be treated as a submitted-order state.
- The independent synthetic brokerage step changed that order to filled while LEAN was down. Fresh LEAN setup loaded cash `9909.91` and holding `1`, found zero open orders, and called `PlaceOrder` zero times.
- In the same-process control, a mock `Filled` event reached `OnOrderEvent`; LEAN showed cash `9909.91`, holding `1`, and no open order. This verifies a narrow event/accounting path under a fully specified synthetic fill, not its behavior after process loss.
- The fresh LEAN transaction handler contained no closed order or fill event. The execution identity and cash/holding reconciliation came from the brokerage report and the TideLab test record.
- The first valid filled restore created one reconciliation record. A second restore verified that exact record (`record=verified_existing`), demonstrating idempotence for this one execution fixture. It did not create a second record or resubmit an order.
- A missing broker report and a contradictory filled report both blocked before setup with nonzero exits. The isolated .NET build finished with 0 errors; the pinned upstream dependency graph still emitted package audit warnings. Existing Python/context checks are independent of this .NET run.

## Limits and remaining gate

This is a **synthetic LEAN order submission through a mock brokerage**, followed by report-based recovery. It has no streaming data clock, strategy signal callback, fill-event delivery **after restart**, real paper brokerage, exchange, or private account. The mock broker writes a perfectly controlled report and the TideLab record is a test artifact, not a production ledger. The hardcoded one-unit arithmetic does not cover partial fills, duplicate/out-of-order execution reports, cancel/reject transitions, fee currencies, reconciliation across multiple orders, or failure during record creation. It does not validate Windows runtime operation of LEAN, distribution/license obligations, or realistic execution.

Next in TL-001A: run the same strategy skeleton under historical and forward synthetic clocks, test delayed and duplicate brokerage events across restart, reconcile them with a durable ledger, and compare these public extension points and costs with the pinned NautilusTrader gap. Keep TL-001B's data-rights decision separate. No engine adoption or live operation follows from this checkpoint.
