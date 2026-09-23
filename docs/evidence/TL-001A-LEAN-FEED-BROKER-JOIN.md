# TL-001A LEAN managed-feed to brokerage restart checkpoint

Status: bounded synthetic local probe on 2026-09-22 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open. No engine adoption.

## Method

At pinned, unmodified LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, `LiveTradingDataFeed` and `LiveSynchronizer` emitted three synthetic hourly equity bars with values `100,102,104`. TideLab's test harness dispatched those LEAN-produced slices to a probe `QCAlgorithm.OnData` callback. Its fixed three-bar rule generated one signal on the third close and called LEAN's `LimitOrder` for one unit at 90. LEAN's `BrokerageTransactionHandler` called a mock `IBrokerage.PlaceOrder` once. The mock assigned a broker ID, durably wrote a `Submitted` report, and emitted a submission acknowledgement. The first process then exited without teardown.

The independent synthetic brokerage step changed the report to a full execution at 90 with a 0.09 USD fee while LEAN was down. A fresh process used LEAN's brokerage setup path to load the reported `SPY` holding and cash. TideLab's test record captured the broker/execution IDs, instrument, quantity, price, fee, and balances. A second fresh restore verified that same record. The joined sequence runs inside `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>` with only temporary synthetic data and reports.

## Observed

- Three feed slices arrived at the expected UTC hourly boundaries, and `OnData` generated one signal. Exactly one `PlaceOrder` call reached the mock broker. LEAN retained one `Submitted` order with the assigned broker ID before process loss.
- The mock broker reported the fill during downtime. Fresh setup loaded cash `9909.91` USD, holding `1` of the same `SPY` test instrument, and zero open orders. It made zero new `PlaceOrder` calls.
- The first fresh restore created one TideLab test reconciliation record. The repeated restore verified it without duplication. The full isolated .NET 10 runner passed with zero build errors; pinned upstream package audit warnings remained.
- An initial combined run routed the new phase to the old recovery test, which rejected its phase name. The runner dispatch was corrected before the joined behavior was evaluated. This was a test-harness failure, not a LEAN execution result.

## Limits and remaining gate

`SPY` labels invented fixture values; no real market data was fetched. The harness still calls `OnData` for LEAN-produced slices; LEAN's full `AlgorithmManager` loop does not dispatch them in this probe. Brokerage execution, fill timing, and account reports are controlled test doubles. The fresh LEAN transaction handler does not reconstruct the closed execution; TideLab's record relies on the synthetic authoritative report. The record is not a production per-execution ledger, and no partial-to-full sequence or actual crash during a ledger write has been tested. Historical and forward strategy semantics are not yet verified from one shared implementation. Repository CI does not build the C# probe.

Next in TL-001A: test the real `AlgorithmManager` callback path or document its integration boundary, run one shared strategy rule under historical and forward synthetic feeds, and reconcile multiple executions durably across interruption. Compare the total LEAN path with the pinned NautilusTrader backing gap before adoption. Keep TL-001B rights separate.
