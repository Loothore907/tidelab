# TL-001A LEAN synthetic historical probe

These TideLab-authored files use only three synthetic hourly values. They submit no orders and require no QuantConnect account, API token, or market-data download. They exercise the open-source LEAN Launcher directly, not the paid LEAN CLI.

Reproduce in an **isolated** LEAN source checkout at commit [`88bce0fc6fe282378ee73c54cef1090d0d7a73ee`](https://github.com/QuantConnect/Lean/commit/88bce0fc6fe282378ee73c54cef1090d0d7a73ee) with .NET SDK 10:

1. Copy `TideLabSyntheticProbeAlgorithm.cs` and `TideLabSyntheticSignal.cs` into LEAN's `Algorithm.CSharp/`.
2. Copy the three `fixtures/*.csv` files into LEAN's `Data/tidelab/`.
3. Build `Launcher/QuantConnect.Lean.Launcher.csproj` in `Release` mode.
4. In the **built copy** at `Launcher/bin/Release/config.json`, set `algorithm-type-name` to `TideLabSyntheticProbeAlgorithm`. Keep `environment` as `backtesting`, `algorithm-language` as `CSharp`, and `data-folder` pointing to LEAN's local `Data/` directory.
5. From `Launcher/bin/Release/`, run `dotnet QuantConnect.Lean.Launcher.dll`.

The expected log marker is `TL001A_LEAN_SYNTHETIC count=3 sum=306 signals=1`, followed by analysis completion. A successful run establishes local historical data delivery and the shared synthetic signal rule. It does not test TideLab's H1 strategy, order accounting, forward-paper operation, process-loss recovery, or LEAN adoption. See `docs/evidence/TL-001A-LEAN-SIGNAL-PARITY.md`.

## Synthetic brokerage startup/restart probe

The three `TideLabForwardRecovery*` files exercise LEAN's public brokerage setup path with a mock brokerage reading a durable synthetic report. The report is the test authority for a pending order, USD cash, and holdings. This is a setup-seam probe, not an unattended forward-paper runner.

In the same pinned LEAN checkout:

1. Copy `TideLabSyntheticSignal.cs` into `Algorithm.CSharp/`, and `TideLabForwardRecoveryProbe.cs` into `Tests/Engine/Setup/`.
2. Create `TideLabForwardProbe/` at the LEAN root and copy the runner `.cs` and `.csproj` there.
3. Build `TideLabForwardProbe/TideLabForwardRecoveryRunner.csproj` with .NET 10 in Release mode.
4. From LEAN's `Launcher/bin/Release` directory, set `TL001A_REPORT_PATH` to a new temporary path and `TL001A_PHASE=seed`, then run the built `TideLabForwardRecoveryRunner.dll` with `dotnet`. Expect `phase=seed status=pending` and a forced nonzero exit after LEAN registers the order.
5. In a fresh process with the same report path and `TL001A_PHASE=restore`, run the same DLL. Expect a zero exit and `phase=restore status=pending ... new_submissions=0`.

Keep the synthetic report local and discard it after the run. Details, observations, and limits are in [the recovery evidence](../../docs/evidence/TL-001A-LEAN-FORWARD-RECOVERY.md). The probe requires neither a QuantConnect login nor a paid CLI.

### Changed outcome and blocked reports

The same runner supports a second, separate synthetic sequence. Use a new report path and run `seed` as above. While LEAN is stopped, run with `TL001A_PHASE=settle` and the same path; this simulates a brokerage fill at 90 with a 0.09 USD fee. Run `TL001A_PHASE=restore_filled` in a fresh process. It should show cash `9909.91`, holding `1`, zero open orders, and zero new submissions. The closed execution is in the brokerage report; LEAN's fresh transaction handler does not reconstruct that closed order from `GetOpenOrders`.

For the conflict case, use another new report path: run `seed`, then `settle_conflict`, then `restore_conflict`. The final phase must print `decision=BLOCK` and exit nonzero before LEAN setup. For an absent report, use a path that does not exist with `TL001A_PHASE=restore_missing`; it must also block and exit nonzero. These phases are synthetic test assertions, not a production submit policy. See [the downtime-outcome evidence](../../docs/evidence/TL-001A-LEAN-DOWNTIME-OUTCOME.md).

On WSL/Linux, `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>` builds the probe and runs the synthetic recovery cases with isolated temporary reports. Its final exit code is zero only when the expected success and blocked outcomes are observed.

Set `TL001A_PAPER_ONLY=1` for the bounded forward-paper source probe. It checks stale-revision rejection, correction/submission serialization, a stable-revision mock submission in a fresh process, and an interrupted-correction restart hold. The source is test-only and does not persist an order intent or recover an ambiguous submission. See [the paper submission barrier evidence](../../docs/evidence/TL-001A-LEAN-PAPER-SUBMISSION-BARRIER.md).

Set `TL001A_INTENT_ONLY=1` for the synthetic durable-intent probe. It exits after flushing an intent but before dispatch and after a mock broker stores an order but before acknowledgement, then recovers in new processes by stable client ID. Unknown and conflicting reports hold without a retry. This local paper authority can declare absence final; an external broker cannot be assumed to do so. See [the paper intent evidence](../../docs/evidence/TL-001A-LEAN-PAPER-INTENT-RECOVERY.md).

Set `TL001A_COST_FILL_ONLY=1` for one bounded synthetic LEAN equity quote-size and cost-model probe. It shows that the default market fill returns a complete one-unit fill against only 0.4 displayed ask size, despite configured slippage and a separate fee model. This is a held modeling assumption, not execution realism. See [the cost/fill evidence](../../docs/evidence/TL-001A-LEAN-COST-FILL-GATE.md).

The same focused runner now joins each recovered accepted intent to a fresh LEAN brokerage setup with three mock open orders and matching cash/holding. A third-order broker-ID mismatch holds with zero new submissions. It does not send a next order. See [the restart join evidence](../../docs/evidence/TL-001A-LEAN-PAPER-RESTART-JOIN.md).

The runner also includes `submit_seed`: LEAN's own `LimitOrder` reaches the mock brokerage once, which writes the pending report and emits a `Submitted` acknowledgement before process loss. The script then settles that report and performs two fresh `restore_filled` runs. The first creates a small synthetic reconciliation record; the second verifies the same record without duplication or resubmission. A separate `submit_fill` control emits a `Filled` brokerage event in the same process and checks LEAN's fill callback and cash/holding update. See [the submission checkpoint](../../docs/evidence/TL-001A-LEAN-SUBMISSION-RECONCILIATION.md). No live data clock or post-restart fill event is part of this checkpoint.

The `submit_clock_seed` sequence manually advances LEAN's UTC algorithm clock through three synthetic hourly `TradeBar` slices and invokes `OnData`. The third callback submits one order through LEAN. After synthetic downtime settlement, `restore_late_event` runs twice in fresh processes: the brokerage reports the filled account, then emits a late duplicate `Filled` event bearing the original LEAN order ID. The fresh transaction handler rejects that unknown closed order ID; the test record remains single and balances unchanged. See [the clock and late-event checkpoint](../../docs/evidence/TL-001A-LEAN-CLOCK-LATE-EVENT.md). This harness does not exercise LEAN's live data feed or historical/forward strategy parity.

The runner additionally restores a synthetic partial fill with the order still open, blocks contradictory partial cash or full executed quantity, and blocks a truncated reconciliation record. The valid partial path holds new orders because the current test record does not model a remaining fill. See [the partial/record checkpoint](../../docs/evidence/TL-001A-LEAN-PARTIAL-RECORD-FAILURE.md). These are fail-closed probes, not a production reconciliation ledger.

The `managed_feed` phase uses LEAN's `LiveTradingDataFeed` and `LiveSynchronizer` to emit three invented hourly values from a local test queue at exchange-local timestamps. The harness consumes the LEAN-produced slices and invokes `OnData`; LEAN's `AlgorithmManager` is not running. See [the managed-feed checkpoint](../../docs/evidence/TL-001A-LEAN-MANAGED-FEED.md). This phase does not submit an order or prove historical/forward strategy parity.

The `managed_feed_submit_seed` phase adds one `LimitOrder` from that callback through LEAN's transaction handler to the mock broker. The broker writes a pending report and acknowledges it before the process exits. The runner settles the report while LEAN is stopped, then restores the same synthetic instrument and balances twice with zero resubmissions and one test reconciliation record. See [the joined feed/broker checkpoint](../../docs/evidence/TL-001A-LEAN-FEED-BROKER-JOIN.md). The historical replay and forward probes now call one shared synthetic signal rule; see [the parity checkpoint](../../docs/evidence/TL-001A-LEAN-SIGNAL-PARITY.md). This phase still dispatches `OnData` from the test harness.

The `managed_manager_submit_seed` phase runs the same synthetic managed feed through LEAN's `AlgorithmManager.Run`, which dispatches `OnData` and sends one order to the mock broker. The runner settles its report during downtime and verifies two fresh restores without resubmission. See [the manager checkpoint](../../docs/evidence/TL-001A-LEAN-ALGORITHM-MANAGER.md). The bounded clock, brokerage, and supporting handlers are test doubles; full strategy/risk parity and a durable per-execution ledger remain open.

The `ledger_*` phases use a separate test-only ledger reader after the manager-generated synthetic order. Two mock brokerage executions advance the authoritative report from a half-unit partial fill to a full fill. Separate processes exit before a ledger write and after a candidate file flush; fresh processes recover both executions and verify repeated reconciliation. See [the execution-ledger checkpoint](../../docs/evidence/TL-001A-LEAN-EXECUTION-LEDGER.md). This snapshot probe does not connect multi-execution recovery to LEAN's fresh transaction handler or establish production durability.

The `restore_ledger_partial`, `restore_ledger_full_lag`, and `restore_ledger_full` phases now join that report and ledger to a fresh LEAN brokerage setup. The partial path restores one open order and holds new orders. A full broker report with a lagging ledger blocks before setup. Once both executions are committed, fresh setup loads the final cash and holding twice with zero new submissions. See [the joined setup checkpoint](../../docs/evidence/TL-001A-LEAN-LEDGER-SETUP-GATE.md). This remains a test-owned gate, not a production order policy.

The `restore_ledger_partial_late_events` and `restore_ledger_full_late_events` phases deliberately deliver late synthetic half-fill events after fresh setup. The partial handler applies two duplicate-shaped events again and overstates inventory; the probe records an expected blocked outcome. The closed handler rejects those events. See [the late-event checkpoint](../../docs/evidence/TL-001A-LEAN-LATE-MULTI-EXECUTION.md).

The `restore_ledger_partial_screened` phase tests a TideLab-owned boundary before constructing a LEAN `OrderEvent`: broker execution IDs already committed in the test ledger are suppressed, absent or mismatched executions are blocked, and a newly reported execution is committed before one event reaches LEAN. The `_crash` variant exits after commit but before delivery; fresh setup reads the final authoritative report without resubmission. See [the execution-event gate checkpoint](../../docs/evidence/TL-001A-LEAN-EXECUTION-EVENT-GATE.md). This is a controlled mock adapter seam, not a deployed broker adapter or a general crash-safe event journal.

The `restore_ledger_partial_reconnect_gap` phase interrupts the replaceable event sink after the second execution is committed. A reconnect suppresses its already committed broker ID, leaving the running LEAN account behind the broker and test ledger. The probe blocks new orders; a separate fresh setup recovers the broker state. See [the engine decision map](../../docs/evidence/TL-001A-ENGINE-DECISION-MAP.md).

The `restore_ledger_partial_reconcile_running` and `restore_ledger_partial_ack_lost` phases use replaceable test source and engine-port interfaces. One interrupts before LEAN applies the second fill; the other loses the acknowledgement after application. Reconnect compares cash, holding, open-order count and broker order ID before deciding whether to deliver the committed execution, then repeats twice to check duplicate suppression. Wrong account or order identity blocks. See [the running reconciliation evidence](../../docs/evidence/TL-001A-LEAN-RUNNING-RECONCILIATION.md). This remains a one-order synthetic adapter protocol, not a production journal or live brokerage.

For synthetic H1 strategy/risk decision parity, run the forward runner above and then `bash scripts/lean_fallback/run_h1_historical_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`. The shared `TideLabH1Skeleton` is compiled into both paths. Forward `managed_h1_baseline` and `managed_h1_drawdown` use four invented closed hourly bars and submit no orders. The direct Launcher reads the corresponding contiguous local fixture and asserts its UTC close boundaries; the script restores the Launcher configuration afterward. See [the H1 parity evidence](../../docs/evidence/TL-001A-LEAN-H1-RISK-PARITY.md).
