# TL-001A joined LEAN setup and two-execution ledger checkpoint

Status: bounded local synthetic probe on 2026-09-23 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open; no engine adoption.

## Method

At pinned LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, `AlgorithmManager.Run` dispatched three invented hourly bars and submitted one limit order to the mock brokerage. Its durable `Submitted` report retained LEAN order ID, broker ID, instrument, quantity, and limit price. The test brokerage then reported two separate half-unit executions. The ledger probe retained those order fields while replacing the synthetic report, validated the execution IDs and decimal totals, and committed a test-only per-execution snapshot.

Fresh processes checked broker-report/ledger agreement before LEAN's `BrokerageSetupHandler.Setup`. With one committed execution, setup loaded a `PartiallyFilled` open order, cash `9954.955`, and holding `0.5`; the test gate held new orders. When the broker report advanced to two executions but the committed ledger still had one, the gate blocked before setup. The two existing interruption sequences then recovered the second execution: one after exit before ledger write, and one after exit following candidate flush but before replacement. Fresh setup loaded cash `9909.91`, holding `1`, and no open order after each recovery; repeated setup produced the same result. Reproduce with `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`.

## Observed

- Partial restore: `open_orders=1 decision=HOLD_NEW_ORDERS new_submissions=0`; LEAN's fresh transaction handler held the reported partially filled broker order.
- Ledger lag: `decision=BLOCK reason=ledger_behind_broker new_submissions=0` before LEAN setup.
- Full restore after either interruption: `open_orders=0 record=ledger_verified new_submissions=0`; LEAN loaded the broker-reported cash and holding. A repeated fresh restore retained the same values.
- The full pinned .NET 10 runner built with zero errors and its earlier synthetic cases still passed. Upstream package audit warnings remained.

## Limits and next gate

The reports, executions, brokerage, and data are synthetic. The test-owned gate deliberately performs no new submission; its `PlaceOrder` assertion shows that setup did not blindly resubmit, but it does not prove a production policy service or safe resumption of future orders. LEAN's fresh transaction handler still does not reconstruct closed executions; the test ledger provides those records. The ledger is a replaceable snapshot, not a production journal, and arbitrary power loss, concurrent writers, broker corrections, and late duplicate events after the second execution remain untested. Repository CI does not compile the C# probe. Before engine adoption, extend shared historical/forward strategy and risk semantics, examine remaining recovery windows and dependency obligations, and compare the total LEAN host work with NautilusTrader's backed external-client gap. Keep TL-001B separate.
