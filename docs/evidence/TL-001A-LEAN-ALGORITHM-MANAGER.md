# TL-001A LEAN AlgorithmManager synthetic dispatch checkpoint

Status: bounded local probe on 2026-09-23 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open. No engine adoption.

## Method

At pinned LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, the existing `LiveTradingDataFeed` and `LiveSynchronizer` supplied three invented hourly `SPY` bars with closes `100,102,104`. A bounded `ISynchronizer` wrapper advanced only the synthetic clock and ended after the third bar. LEAN's public `AlgorithmManager.Run` received that synchronizer and called the probe algorithm's `OnData`; the harness did not call `OnData` in this phase. The shared `TideLabSyntheticSignal` emitted one signal, which called LEAN's `LimitOrder`. A mock brokerage wrote a durable `Submitted` report and acknowledged the order. The process then exited deliberately with a nonzero code, without transaction teardown.

The independent test brokerage settled the report during downtime at 90 with a 0.09 USD fee. Fresh processes used LEAN's brokerage setup path to restore the same synthetic instrument, cash, and holding twice. Reproduce with `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`; the new `managed_manager_submit_seed` phase runs alongside the existing control cases. No real market data, account, credentials, or paid CLI is involved.

## Observed

- The runner built with zero errors. The manager phase logged `slices=3 signal=1 status=Submitted new_submissions=1 manager=run`. The callback's close and UTC-time assertions matched the earlier managed-feed control.
- After synthetic downtime settlement, fresh setup reported cash `9909.91` USD, holding `1` of `SPY`, zero open orders, and zero new submissions. The first restore created one TideLab test reconciliation record; the second verified the same record.
- Existing feed, manual-clock, pending, partial, conflict, torn-record, and late-event probe cases still passed in the full runner. Pinned upstream package audit warnings remained.

## Limits and next gate

The bounded synchronizer and supporting result, real-time, and lean-manager handlers are test doubles. `AlgorithmManager.Run` ended after three bars before the forced process exit; this is not an abrupt crash inside its callback or transaction handoff. The brokerage report and fill are synthetic. The fresh transaction handler does not reconstruct the closed order; TideLab's test record derives from the report. One shared signal predicate is proven, not full H1 strategy/risk parity. Repository CI does not compile the C# probe. Next, exercise a durable per-execution ledger through partial-to-full reports and interruption at its write boundaries, then compare the total LEAN integration path with NautilusTrader's unresolved external Python client/backing gap before choosing an engine.
