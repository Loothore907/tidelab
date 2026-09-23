# TL-001A LEAN synthetic signal parity checkpoint

Status: bounded local probe on 2026-09-22 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open. No engine adoption.

## Method

At pinned LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, the direct Launcher replay and the synthetic forward probes compiled one TideLab-authored `TideLabSyntheticSignal` class. It records the first close and emits one signal on the third close only when that close is higher. Each path received the invented values `100,102,104`. The historical path used the three local CSV fixture records; the forward paths used LEAN's managed live feed with harness-dispatched `OnData`, and a separate manually clocked `OnData` control. The managed-feed submission case routed the signal through LEAN's `LimitOrder` and mock brokerage.

Reproduction: copy `TideLabSyntheticSignal.cs` and `TideLabSyntheticProbeAlgorithm.cs` into the pinned LEAN checkout's `Algorithm.CSharp/`; copy `fixtures/*.csv` into its `Data/tidelab/`; build and run the direct Launcher as described in `scripts/lean_fallback/README.md`. Run `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>` for the forward sequence. All data, orders, brokerage reports, and balances in this probe are synthetic. No account, credential, paid CLI, or market-data fetch was used.

## Observed

- The direct Launcher replay logged `TL001A_LEAN_SYNTHETIC count=3 sum=306 signals=1` and completed with zero build errors.
- The forward runner built with zero errors. Its managed-feed phase logged `slices=3 closes=100,102,104 callback=3 signal=1 manager=not_run`.
- Its managed-feed submission phase logged `slices=3 signal=1 status=Submitted new_submissions=1 manager=not_run`; the subsequent synthetic downtime settlement and fresh restorations continued to pass. The manually clocked submission phase logged `data_count=3 signal_count=1 ... new_submissions=1`.

## Limits and next gate

This verifies only one shared, simple signal predicate on identical invented closes. The historical records and forward bars differ in clock and data representation. It does not establish TideLab's H1 strategy or risk semantics, production historical/forward parity, LEAN `AlgorithmManager` callback dispatch, realistic brokerage behavior, or a durable per-execution ledger. Repository CI does not build the C# probe. Next in TL-001A: test `AlgorithmManager` dispatch or document its host boundary, then exercise a durable ledger across multiple executions, partial-to-full transitions, and process loss before any engine decision. Keep TL-001B rights separate.
