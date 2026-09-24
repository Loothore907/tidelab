#!/usr/bin/env bash
# Run only against a separate, pinned LEAN checkout with a local .NET 10 SDK.
set -euo pipefail

lean_root=$(realpath "$1")
dotnet_bin=$(realpath "$2")
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

test "$(git -C "$lean_root" rev-parse HEAD)" = \
  "88bce0fc6fe282378ee73c54cef1090d0d7a73ee"
mkdir -p "$lean_root/TideLabForwardProbe"
cp "$source_dir/TideLabSyntheticSignal.cs" \
  "$source_dir/TideLabSyntheticProbeAlgorithm.cs" \
  "$source_dir/TideLabH1Skeleton.cs" \
  "$source_dir/TideLabH1ProbeAlgorithm.cs" \
  "$lean_root/Algorithm.CSharp/"
mkdir -p "$lean_root/Data/tidelab_h1"
cp "$source_dir/fixtures/h1_20260101.csv" \
  "$lean_root/Data/tidelab_h1/20260101.csv"
cp "$source_dir/TideLabForwardRecoveryProbe.cs" \
  "$source_dir/TideLabExecutionLedgerProbe.cs" \
  "$source_dir/TideLabExecutionDeliveryProbe.cs" \
  "$source_dir/TideLabCorrectionJournalProbe.cs" \
  "$source_dir/TideLabAtomicSnapshotProbe.cs" \
  "$lean_root/Tests/Engine/Setup/"
cp "$source_dir/TideLabManagedFeedProbe.cs" \
  "$lean_root/Tests/Engine/DataFeeds/"
cp "$source_dir/TideLabForwardRecoveryRunner.cs" \
  "$source_dir/TideLabForwardRecoveryRunner.csproj" \
  "$lean_root/TideLabForwardProbe/"

"$dotnet_bin" build \
  "$lean_root/TideLabForwardProbe/TideLabForwardRecoveryRunner.csproj" \
  -c Release -p:RunAnalyzers=false -p:WarningLevel=0 -v quiet

report_dir=$(mktemp -d)
trap 'rm -f "$report_dir"/*.json "$report_dir"/*.json.next "$report_dir"/*.jsonl "$report_dir"/*.log; rmdir "$report_dir"' EXIT
runner="$lean_root/TideLabForwardProbe/bin/Release/net10.0/TideLabForwardRecoveryRunner.dll"
cd "$lean_root/Launcher/bin/Release"

run_phase() {
  local report=$1 phase=$2 expected=$3 required=${4:-} rc=0
  TL001A_REPORT_PATH="$report_dir/$report.json" TL001A_PHASE="$phase" \
    "$dotnet_bin" "$runner" >"$report_dir/$report-$phase.log" 2>&1 || rc=$?
  if [[ "$expected" == "success" && "$rc" -ne 0 ]] ||
     [[ "$expected" != "success" && "$rc" -eq 0 ]]; then
    cat "$report_dir/$report-$phase.log" >&2
    return 1
  fi
  grep -E 'TL001A_(LEAN_(FORWARD|FEED|LEDGER|JOURNAL|SNAPSHOT)|H1_PARITY)' "$report_dir/$report-$phase.log" || {
    cat "$report_dir/$report-$phase.log" >&2
    return 1
  }
  if [[ -n "$required" ]]; then
    grep -q "$required" "$report_dir/$report-$phase.log"
  fi
}

run_journal_probe() {
  run_phase journal managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
  run_phase journal ledger_partial_report success 'revision=2 executions=1'
  run_phase journal ledger_reconcile success 'state=created_from_report executions=1'
  run_phase journal journal_seed success 'orders=2 events=3 cash=9954.955 holding=0.5'
  run_phase journal journal_reverse success 'decision=HOLD_CORRECTION_PENDING events=4'
  run_phase journal journal_replace success 'orders=2 events=5 cash=9955.455 holding=0.5'
  run_phase journal journal_verify success 'orders=2 events=5 duplicate=none'
  run_phase journal journal_verify success 'orders=2 events=5 duplicate=none'
  run_phase journal restore_ledger_partial_journal_correction success 'decision=BLOCK_CORRECTION_EVENT thrown=none cash_after_failure=10000.000 holding_after_failure=0.5 callbacks=1 replacement=not_sent new_submissions=0'
  run_phase journal restore_ledger_partial_journal_fresh success 'decision=FRESH_SETUP_MATCHES_JOURNAL cash=9955.455 holding=0.5 open_orders=2 callbacks=0 new_submissions=0'
}

run_snapshot_probe() {
  run_phase snapshot managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
  run_phase snapshot ledger_partial_report success 'revision=2 executions=1'
  run_phase snapshot ledger_reconcile success 'state=created_from_report executions=1'
  run_phase snapshot journal_seed success 'orders=2 events=3 cash=9954.955 holding=0.5'
  run_phase snapshot snapshot_seed success 'revision=2 orders=2 journal_events=3'
  run_phase snapshot restore_snapshot_race success 'decision=BLOCK_REVISION_RACE before=2 after=3 new_submissions=0'
  run_phase snapshot restore_snapshot_stable success 'decision=STABLE_SNAPSHOT revision=3 cash=9955.455 holding=0.5 open_orders=2 callbacks=0 new_submissions=0'
}

run_handoff_probe() {
  run_phase handoff managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
  run_phase handoff ledger_partial_report success 'revision=2 executions=1'
  run_phase handoff ledger_reconcile success 'state=created_from_report executions=1'
  run_phase handoff journal_seed success 'orders=2 events=3 cash=9954.955 holding=0.5'
  run_phase handoff snapshot_seed success 'revision=2 orders=2 journal_events=3'
  run_phase handoff restore_snapshot_handoff success 'decision=BLOCK_UNVERSIONED_HANDOFF final_check=2 broker_now=3 new_submissions=0'
  run_phase handoff restore_snapshot_stable success 'decision=STABLE_SNAPSHOT revision=3 cash=9955.455 holding=0.5 open_orders=2 callbacks=0 new_submissions=0'
}

if [[ "${TL001A_JOURNAL_ONLY:-0}" == 1 ]]; then
  run_journal_probe
  exit 0
fi
if [[ "${TL001A_SNAPSHOT_ONLY:-0}" == 1 ]]; then
  run_snapshot_probe
  exit 0
fi
if [[ "${TL001A_HANDOFF_ONLY:-0}" == 1 ]]; then
  run_handoff_probe
  exit 0
fi

run_phase feed managed_feed success 'slices=3 closes=100,102,104 callback=3'
run_phase h1_baseline managed_h1_baseline success 'clock=forward scenario=baseline bars=4 decisions=3:EnterLong:Approve|4:ExitToCash:Approve'
run_phase h1_drawdown managed_h1_drawdown success 'clock=forward scenario=drawdown bars=4 decisions=3:EnterLong:BlockDrawdown|4:ExitToCash:Approve'
run_phase managed_order managed_feed_submit_seed forced_exit 'signal=1 status=Submitted new_submissions=1'
run_phase managed_order settle success
run_phase managed_order restore_filled success 'symbol=SPY .*record=created new_submissions=0'
run_phase managed_order restore_filled success 'symbol=SPY .*record=verified_existing new_submissions=0'
run_phase manager_order managed_manager_submit_seed forced_exit 'signal=1 status=Submitted new_submissions=1 manager=run'
run_phase manager_order settle success
run_phase manager_order restore_filled success 'symbol=SPY .*record=created new_submissions=0'
run_phase manager_order restore_filled success 'symbol=SPY .*record=verified_existing new_submissions=0'
run_phase ledger_pre managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
run_phase ledger_pre ledger_partial_report success 'revision=2 executions=1'
run_phase ledger_pre ledger_reconcile success 'state=created_from_report executions=1'
run_phase ledger_pre restore_ledger_partial success 'open_orders=1 decision=HOLD_NEW_ORDERS new_submissions=0'
run_phase ledger_pre restore_ledger_partial_late_events blocked 'delivery=applied_duplicate events=2 .*decision=BLOCK reason=duplicate_partial_event new_submissions=0'
run_phase ledger_pre ledger_full_report success 'revision=3 executions=2'
run_phase ledger_pre restore_ledger_full_lag blocked 'reason=ledger_behind_broker new_submissions=0'
run_phase ledger_pre ledger_crash_before_write forced_exit 'broker_executions=2 ledger_executions=1'
run_phase ledger_pre ledger_reconcile success 'state=created_from_report executions=2'
run_phase ledger_pre restore_ledger_full success 'open_orders=0 record=ledger_verified new_submissions=0'
run_phase ledger_pre restore_ledger_full_late_events success 'events=2 .*open_orders=0 ledger=unchanged new_submissions=0'
run_phase ledger_pre ledger_reconcile success 'state=verified_existing executions=2'
run_phase ledger_pre restore_ledger_full success 'open_orders=0 record=ledger_verified new_submissions=0'
run_phase ledger_flush managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
run_phase ledger_flush ledger_partial_report success 'revision=2 executions=1'
run_phase ledger_flush ledger_reconcile success 'state=created_from_report executions=1'
run_phase ledger_flush restore_ledger_partial success 'open_orders=1 decision=HOLD_NEW_ORDERS new_submissions=0'
run_phase ledger_flush restore_ledger_partial_late_events blocked 'delivery=applied_duplicate events=2 .*decision=BLOCK reason=duplicate_partial_event new_submissions=0'
run_phase ledger_flush ledger_full_report success 'revision=3 executions=2'
run_phase ledger_flush restore_ledger_full_lag blocked 'reason=ledger_behind_broker new_submissions=0'
run_phase ledger_flush ledger_crash_after_flush forced_exit 'candidate_flushed=true'
run_phase ledger_flush ledger_reconcile success 'state=recovered_flushed_candidate executions=2'
run_phase ledger_flush restore_ledger_full success 'open_orders=0 record=ledger_verified new_submissions=0'
run_phase ledger_flush restore_ledger_full_late_events success 'events=2 .*open_orders=0 ledger=unchanged new_submissions=0'
run_phase ledger_flush ledger_reconcile success 'state=verified_existing executions=2'
run_phase screened managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
run_phase screened ledger_partial_report success 'revision=2 executions=1'
run_phase screened ledger_reconcile success 'state=created_from_report executions=1'
run_phase screened restore_ledger_partial_screened success 'second=delivered_after_commit callbacks=1 cash=9909.91 holding=1 open_orders=0 new_submissions=0'
run_phase screened restore_ledger_full success 'open_orders=0 record=ledger_verified new_submissions=0'
run_phase reconnect_gap managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
run_phase reconnect_gap ledger_partial_report success 'revision=2 executions=1'
run_phase reconnect_gap ledger_reconcile success 'state=created_from_report executions=1'
run_phase reconnect_gap restore_ledger_partial_reconnect_gap blocked 'reason=engine_behind_broker reconnect=suppressed_committed .*new_submissions=0'
run_phase reconnect_gap restore_ledger_full success 'open_orders=0 record=ledger_verified new_submissions=0'
run_phase reconcile_running managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
run_phase reconcile_running ledger_partial_report success 'revision=2 executions=1'
run_phase reconcile_running ledger_reconcile success 'state=created_from_report executions=1'
run_phase reconcile_running restore_ledger_partial_reconcile_running success 'reconnect=APPLIED_FROM_COMMITTED repeats=2 callbacks=1 .*new_submissions=0'
run_phase reconcile_running restore_ledger_full success 'open_orders=0 record=ledger_verified new_submissions=0'
run_phase ack_lost managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
run_phase ack_lost ledger_partial_report success 'revision=2 executions=1'
run_phase ack_lost ledger_reconcile success 'state=created_from_report executions=1'
run_phase ack_lost restore_ledger_partial_ack_lost success 'reconnect=ALREADY_APPLIED repeats=2 callbacks=1 .*new_submissions=0'
run_phase ack_lost restore_ledger_full success 'open_orders=0 record=ledger_verified new_submissions=0'
run_phase corrected managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
run_phase corrected ledger_partial_report success 'revision=2 executions=1'
run_phase corrected ledger_reconcile success 'state=created_from_report executions=1'
run_phase corrected restore_ledger_partial_correction success 'decision=BLOCK_ENGINE_MISMATCH open_orders=1 callbacks=0 new_submissions=0'
run_phase concurrent managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
run_phase concurrent ledger_partial_report success 'revision=2 executions=1'
run_phase concurrent ledger_reconcile success 'state=created_from_report executions=1'
run_phase concurrent restore_ledger_partial_concurrent success 'decision=BLOCK_ENGINE_MISMATCH open_orders=2 callbacks=0 new_submissions=0'
run_journal_probe
run_snapshot_probe
run_handoff_probe
run_phase screened_crash managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
run_phase screened_crash ledger_partial_report success 'revision=2 executions=1'
run_phase screened_crash ledger_reconcile success 'state=created_from_report executions=1'
run_phase screened_crash restore_ledger_partial_screened_crash forced_exit 'second=committed delivery=not_started new_submissions=0'
run_phase screened_crash restore_ledger_full success 'open_orders=0 record=ledger_verified new_submissions=0'
run_phase pending seed forced_exit
run_phase pending restore success
run_phase filled seed forced_exit
run_phase filled settle success
run_phase filled restore_filled success
run_phase submitted submit_seed forced_exit
run_phase submitted settle success
run_phase submitted restore_filled success 'record=created'
run_phase submitted restore_filled success 'record=verified_existing'
run_phase clock submit_clock_seed forced_exit 'data_count=3 signal_count=1'
run_phase clock settle success
run_phase clock restore_late_event success 'delivery=rejected_unknown_order record=created'
run_phase clock restore_late_event success 'delivery=rejected_unknown_order record=verified_existing'
run_phase partial submit_clock_seed forced_exit
run_phase partial settle_partial success
run_phase partial restore_partial success 'decision=HOLD_NEW_ORDERS'
run_phase partial_conflict seed forced_exit
run_phase partial_conflict settle_partial_conflict success
run_phase partial_conflict restore_partial_conflict blocked 'reason=account_execution_mismatch'
run_phase quantity_conflict seed forced_exit
run_phase quantity_conflict settle_quantity_conflict success
run_phase quantity_conflict restore_quantity_conflict blocked 'reason=account_execution_mismatch'
run_phase torn submit_clock_seed forced_exit
run_phase torn settle success
run_phase torn tear_record success 'record=truncated'
run_phase torn restore_torn_record blocked 'reason=truncated_reconciliation_record'
run_phase event submit_fill success
run_phase event restore_filled success 'record=created'
run_phase conflict seed forced_exit
run_phase conflict settle_conflict success
run_phase conflict restore_conflict blocked
run_phase missing restore_missing blocked
