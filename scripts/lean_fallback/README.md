# TL-001A LEAN synthetic historical probe

These TideLab-authored files use only three synthetic hourly values. They submit no orders and require no QuantConnect account, API token, or market-data download. They exercise the open-source LEAN Launcher directly, not the paid LEAN CLI.

Reproduce in an **isolated** LEAN source checkout at commit [`88bce0fc6fe282378ee73c54cef1090d0d7a73ee`](https://github.com/QuantConnect/Lean/commit/88bce0fc6fe282378ee73c54cef1090d0d7a73ee) with .NET SDK 10:

1. Copy `TideLabSyntheticProbeAlgorithm.cs` into LEAN's `Algorithm.CSharp/`.
2. Copy the three `fixtures/*.csv` files into LEAN's `Data/tidelab/`.
3. Build `Launcher/QuantConnect.Lean.Launcher.csproj` in `Release` mode.
4. In the **built copy** at `Launcher/bin/Release/config.json`, set `algorithm-type-name` to `TideLabSyntheticProbeAlgorithm`. Keep `environment` as `backtesting`, `algorithm-language` as `CSharp`, and `data-folder` pointing to LEAN's local `Data/` directory.
5. From `Launcher/bin/Release/`, run `dotnet QuantConnect.Lean.Launcher.dll`.

The expected log marker is `TL001A_LEAN_SYNTHETIC count=3 sum=306`, followed by analysis completion. A successful run establishes only local historical data delivery. It does not test TideLab's H1 strategy, order accounting, forward-paper operation, process-loss recovery, or LEAN adoption. See `docs/evidence/TL-001A-LEAN-FALLBACK-PREFLIGHT.md`.

## Synthetic brokerage startup/restart probe

The three `TideLabForwardRecovery*` files exercise LEAN's public brokerage setup path with a mock brokerage reading a durable synthetic report. The report is the test authority for a pending order, USD cash, and holdings. This is a setup-seam probe, not an unattended forward-paper runner.

In the same pinned LEAN checkout:

1. Copy `TideLabForwardRecoveryProbe.cs` into `Tests/Engine/Setup/`.
2. Create `TideLabForwardProbe/` at the LEAN root and copy the runner `.cs` and `.csproj` there.
3. Build `TideLabForwardProbe/TideLabForwardRecoveryRunner.csproj` with .NET 10 in Release mode.
4. From LEAN's `Launcher/bin/Release` directory, set `TL001A_REPORT_PATH` to a new temporary path and `TL001A_PHASE=seed`, then run the built `TideLabForwardRecoveryRunner.dll` with `dotnet`. Expect `phase=seed status=pending` and a forced nonzero exit after LEAN registers the order.
5. In a fresh process with the same report path and `TL001A_PHASE=restore`, run the same DLL. Expect a zero exit and `phase=restore status=pending ... new_submissions=0`.

Keep the synthetic report local and discard it after the run. Details, observations, and limits are in [the recovery evidence](../../docs/evidence/TL-001A-LEAN-FORWARD-RECOVERY.md). The probe requires neither a QuantConnect login nor a paid CLI.

### Changed outcome and blocked reports

The same runner supports a second, separate synthetic sequence. Use a new report path and run `seed` as above. While LEAN is stopped, run with `TL001A_PHASE=settle` and the same path; this simulates a brokerage fill at 90 with a 0.09 USD fee. Run `TL001A_PHASE=restore_filled` in a fresh process. It should show cash `9909.91`, holding `1`, zero open orders, and zero new submissions. The closed execution is in the brokerage report; LEAN's fresh transaction handler does not reconstruct that closed order from `GetOpenOrders`.

For the conflict case, use another new report path: run `seed`, then `settle_conflict`, then `restore_conflict`. The final phase must print `decision=BLOCK` and exit nonzero before LEAN setup. For an absent report, use a path that does not exist with `TL001A_PHASE=restore_missing`; it must also block and exit nonzero. These phases are synthetic test assertions, not a production submit policy. See [the downtime-outcome evidence](../../docs/evidence/TL-001A-LEAN-DOWNTIME-OUTCOME.md).

On WSL/Linux, `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>` builds the probe and runs the synthetic recovery cases with isolated temporary reports. Its final exit code is zero only when the expected success and blocked outcomes are observed.

The runner also includes `submit_seed`: LEAN's own `LimitOrder` reaches the mock brokerage once, which writes the pending report and emits a `Submitted` acknowledgement before process loss. The script then settles that report and performs two fresh `restore_filled` runs. The first creates a small synthetic reconciliation record; the second verifies the same record without duplication or resubmission. A separate `submit_fill` control emits a `Filled` brokerage event in the same process and checks LEAN's fill callback and cash/holding update. See [the submission checkpoint](../../docs/evidence/TL-001A-LEAN-SUBMISSION-RECONCILIATION.md). No live data clock or post-restart fill event is part of this checkpoint.

The `submit_clock_seed` sequence manually advances LEAN's UTC algorithm clock through three synthetic hourly `TradeBar` slices and invokes `OnData`. The third callback submits one order through LEAN. After synthetic downtime settlement, `restore_late_event` runs twice in fresh processes: the brokerage reports the filled account, then emits a late duplicate `Filled` event bearing the original LEAN order ID. The fresh transaction handler rejects that unknown closed order ID; the test record remains single and balances unchanged. See [the clock and late-event checkpoint](../../docs/evidence/TL-001A-LEAN-CLOCK-LATE-EVENT.md). This harness does not exercise LEAN's live data feed or historical/forward strategy parity.

The runner additionally restores a synthetic partial fill with the order still open, blocks contradictory partial cash or full executed quantity, and blocks a truncated reconciliation record. The valid partial path holds new orders because the current test record does not model a remaining fill. See [the partial/record checkpoint](../../docs/evidence/TL-001A-LEAN-PARTIAL-RECORD-FAILURE.md). These are fail-closed probes, not a production reconciliation ledger.
