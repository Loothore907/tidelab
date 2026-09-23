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
  "$lean_root/Algorithm.CSharp/"
cp "$source_dir/TideLabForwardRecoveryProbe.cs" \
  "$source_dir/TideLabExecutionLedgerProbe.cs" \
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
trap 'rm -f "$report_dir"/*.json "$report_dir"/*.json.next "$report_dir"/*.log; rmdir "$report_dir"' EXIT
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
  grep -E 'TL001A_LEAN_(FORWARD|FEED|LEDGER)' "$report_dir/$report-$phase.log" || {
    cat "$report_dir/$report-$phase.log" >&2
    return 1
  }
  if [[ -n "$required" ]]; then
    grep -q "$required" "$report_dir/$report-$phase.log"
  fi
}

run_phase feed managed_feed success 'slices=3 closes=100,102,104 callback=3'
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
