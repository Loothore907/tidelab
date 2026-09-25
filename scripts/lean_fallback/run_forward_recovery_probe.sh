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
  "$source_dir/TideLabH1V1Policy.cs" \
  "$source_dir/TideLabH1V1ResearchReplay.cs" \
  "$source_dir/TideLabH1ConservativeExecution.cs" \
  "$source_dir/TideLabH1V1TrialAccounting.cs" \
  "$source_dir/TideLabH1V1PaperProposal.cs" \
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
  "$source_dir/TideLabPaperSubmissionBarrierProbe.cs" \
  "$source_dir/TideLabPaperIntentRecoveryProbe.cs" \
  "$source_dir/TideLabCostFillProbe.cs" \
  "$source_dir/TideLabConservativePaperFillProbe.cs" \
  "$source_dir/TideLabJoinedPaperWorkflowProbe.cs" \
  "$source_dir/TideLabH1LocalReportProbe.cs" \
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
trap 'rm -f "$report_dir"/*.json "$report_dir"/*.json.next "$report_dir"/*.json.unknown "$report_dir"/*.jsonl "$report_dir"/*.log "$report_dir"/*.sqlite3 "$report_dir"/*.sqlite3-wal "$report_dir"/*.sqlite3-shm; rmdir "$report_dir"' EXIT
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
  grep -E 'TL001A_(LEAN_(FORWARD|FEED|LEDGER|JOURNAL|SNAPSHOT|PAPER|INTENT|COST_FILL|CONSERVATIVE|JOINED)|H1_PARITY)|H1V1_(PARITY|ACCOUNTING|LEAN_REPORT)' "$report_dir/$report-$phase.log" || {
    cat "$report_dir/$report-$phase.log" >&2
    return 1
  }
  if [[ -n "$required" ]]; then
    grep -q "$required" "$report_dir/$report-$phase.log"
  fi
}

if [[ ${TL_H1_REPORT_ONLY:-0} == 1 ]]; then
  bridge="$source_dir/../h1_lean_report_bridge.py"
  proposal="$report_dir/h1-proposal.json"
  "$dotnet_bin" run --project "$source_dir/h1_v1_check/H1V1Check.csproj" \
    -c Release -- --emit-paper-proposal >"$report_dir/h1-proposal.log"
  sed -n 's/^H1V1_PAPER_PROPOSAL_JSON=//p' "$report_dir/h1-proposal.log" >"$proposal"
  test -s "$proposal"
  export TL_H1_PROPOSAL_PATH="$proposal" TL_H1_BRIDGE_SCRIPT="$bridge" \
    TL_H1_BRIDGE_PYTHON=python3
  export TL_H1_BRIDGE_DATABASE="$report_dir/h1.sqlite3"
  python3 "$bridge" prepare "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1.json"
  run_phase h1 h1_report_seed success 'quantity=25 revision=1 new_submissions=1'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1.json"
  run_phase h1 h1_report_restore success 'revision=1 cash=10000 holding=0 new_submissions=0'
  run_phase h1 h1_report_partial success 'quantity=10.0 cash=9009.9 holding=10.0 new_submissions=0'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1.json"
  run_phase h1 h1_report_restore success 'revision=2 cash=9009.9 holding=10.0 new_submissions=0'
  run_phase h1 h1_report_restore success 'revision=2 cash=9009.9 holding=10.0 new_submissions=0'
  run_phase h1 h1_report_cancel success 'revision=3 holding=10.0 new_submissions=0'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1.json"
  run_phase h1 h1_report_restore success 'revision=3 cash=9009.9 holding=10.0 new_submissions=0'
  test "$(python3 "$bridge" state "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1.json")" = submission_unknown
  echo 'H1V1_LEAN_REPORT gate=closed_report_still_holds_next_intent'
  revision=$(python3 "$bridge" revision "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1.json")
  next_proposal="$report_dir/h1-next-proposal.json"
  "$dotnet_bin" run --project "$source_dir/h1_v1_check/H1V1Check.csproj" \
    -c Release -- --emit-paper-handoff "$report_dir/h1.json" "$revision" \
    >"$report_dir/h1-handoff.log"
  sed -n 's/^H1V1_PAPER_HANDOFF_JSON=//p' "$report_dir/h1-handoff.log" >"$next_proposal"
  test -s "$next_proposal"
  python3 "$bridge" handoff "$TL_H1_BRIDGE_DATABASE" "$proposal" \
    "$report_dir/h1.json" "$next_proposal"
  python3 "$bridge" handoff "$TL_H1_BRIDGE_DATABASE" "$proposal" \
    "$report_dir/h1.json" "$next_proposal"
  test "$(python3 "$bridge" state "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1.json")" = resolved
  export TL_H1_PROPOSAL_PATH="$next_proposal"
  run_phase h1_next h1_report_seed success 'quantity=-10 revision=1 new_submissions=1'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$next_proposal" "$report_dir/h1_next.json"
  run_phase h1_next h1_report_restore success 'holding=10.0 new_submissions=0'
  test "$(python3 "$bridge" state "$TL_H1_BRIDGE_DATABASE" "$next_proposal" "$report_dir/h1_next.json")" = submission_unknown
  echo 'H1V1_LEAN_REPORT gate=terminal_handoff_next_exit_submitted_once'

  export TL_H1_PROPOSAL_PATH="$proposal"
  export TL_H1_BRIDGE_DATABASE="$report_dir/h1-correct.sqlite3"
  python3 "$bridge" prepare "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1_correct.json"
  run_phase h1_correct h1_report_seed success 'quantity=25 revision=1 new_submissions=1'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1_correct.json"
  run_phase h1_correct h1_report_partial success 'quantity=10.0 cash=9009.9 holding=10.0 new_submissions=0'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1_correct.json"
  run_phase h1_correct h1_report_correct success 'journal=must_hold new_submissions=0'
  if python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$proposal" \
      "$report_dir/h1_correct.json" >"$report_dir/h1-correction-block.log" 2>&1; then
    echo 'Corrected H1 execution unexpectedly reconciled' >&2
    exit 1
  fi
  grep -q 'H1 execution removed or corrected; hold' "$report_dir/h1-correction-block.log"
  if TL001A_REPORT_PATH="$report_dir/h1_correct.json" TL001A_PHASE=h1_report_restore \
      "$dotnet_bin" "$runner" >"$report_dir/h1-restore-block.log" 2>&1; then
    echo 'Corrected H1 execution unexpectedly restored' >&2
    exit 1
  fi
  grep -q 'BLOCK_H1_reconcile' "$report_dir/h1-restore-block.log"
  test "$(python3 "$bridge" state "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1_correct.json")" = submission_unknown
  echo 'H1V1_LEAN_REPORT gate=corrected_execution_holds_before_setup'
  exit 0
fi

if [[ ${TL_H1_COST_ONLY:-0} == 1 ]]; then
  bridge="$source_dir/../h1_lean_report_bridge.py"
  proposal="$report_dir/h1-cost-proposal.json"
  "$dotnet_bin" run --project "$source_dir/h1_v1_check/H1V1Check.csproj" \
    -c Release -- --emit-paper-proposal >"$report_dir/h1-cost-proposal.log"
  sed -n 's/^H1V1_PAPER_PROPOSAL_JSON=//p' "$report_dir/h1-cost-proposal.log" >"$proposal"
  test -s "$proposal"
  export TL_H1_PROPOSAL_PATH="$proposal" TL_H1_BRIDGE_SCRIPT="$bridge" \
    TL_H1_BRIDGE_PYTHON=python3
  export TL_H1_BRIDGE_DATABASE="$report_dir/h1-cost.sqlite3"
  python3 "$bridge" prepare "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1_cost.json"
  run_phase h1_cost h1_report_seed success 'quantity=25 revision=1 new_submissions=1'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1_cost.json"
  run_phase h1_cost h1_report_cost_missed success 'stale=HOLD empty=HOLD limit=HOLD revision=1 new_submissions=0'
  run_phase h1_cost h1_report_cost_partial success 'price=99.8998 fee=2.497495'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1_cost.json"
  run_phase h1_cost h1_report_restore success 'revision=2 cash=8998.504505'
  run_phase h1_cost h1_report_cancel success 'revision=3'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1_cost.json"
  run_phase h1_cost h1_report_restore success 'revision=3 cash=8998.504505'
  revision=$(python3 "$bridge" revision "$TL_H1_BRIDGE_DATABASE" "$proposal" "$report_dir/h1_cost.json")
  next_proposal="$report_dir/h1-cost-next.json"
  "$dotnet_bin" run --project "$source_dir/h1_v1_check/H1V1Check.csproj" \
    -c Release -- --emit-paper-handoff "$report_dir/h1_cost.json" "$revision" \
    >"$report_dir/h1-cost-handoff.log"
  sed -n 's/^H1V1_PAPER_HANDOFF_JSON=//p' "$report_dir/h1-cost-handoff.log" >"$next_proposal"
  test -s "$next_proposal"
  python3 "$bridge" handoff "$TL_H1_BRIDGE_DATABASE" "$proposal" \
    "$report_dir/h1_cost.json" "$next_proposal"
  export TL_H1_PROPOSAL_PATH="$next_proposal"
  run_phase h1_cost_next h1_report_seed success 'quantity=-10 revision=1 new_submissions=1'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$next_proposal" "$report_dir/h1_cost_next.json"
  run_phase h1_cost_next h1_report_cost_sell_fill success 'price=98.1018 fee=2.452545'
  python3 "$bridge" reconcile "$TL_H1_BRIDGE_DATABASE" "$next_proposal" "$report_dir/h1_cost_next.json"
  run_phase h1_cost_next h1_report_restore success 'revision=2 cash=9977.069960'
  test "$(python3 "$bridge" state "$TL_H1_BRIDGE_DATABASE" "$next_proposal" "$report_dir/h1_cost_next.json")" = submission_unknown
  python3 - "$report_dir/h1_cost.json" "$report_dir/h1_cost_next.json" <<'PY'
import json
import sys
from decimal import Decimal

entry, exit_report = [json.load(open(path, encoding="utf-8"), parse_float=Decimal)
                      for path in sys.argv[1:]]
buy, sell = entry["Executions"][0], exit_report["Executions"][0]
amount = lambda row, key: Decimal(str(row[key]))
assert amount(buy, "Quantity") == amount(sell, "Quantity") == 10
assert amount(entry, "Cash") == (Decimal("10000") -
    amount(buy, "Quantity") * amount(buy, "Price") - amount(buy, "Fee"))
assert amount(exit_report, "Cash") == (amount(entry, "Cash") +
    amount(sell, "Quantity") * amount(sell, "Price") - amount(sell, "Fee"))
assert amount(entry, "Holding") == 10 and amount(exit_report, "Holding") == 0
assert amount(buy, "Fee") + amount(sell, "Fee") == Decimal("4.950040")
assert amount(exit_report, "Cash") == Decimal("9977.069960")
PY
  echo 'H1V1_LEAN_REPORT gate=costed_round_trip account=9977.069960 units=0 fees=4.950040 realized=-22.930040 next=HOLD'
  exit 0
fi

if [[ ${TL_H1_V1_ACCOUNTING_ONLY:-0} == 1 ]]; then
  run_phase h1_v1 managed_h1_v1_accounting success 'H1V1_ACCOUNTING clock=forward warmup=168 feed_bars=3'
  exit 0
fi

if [[ ${TL_H1_V1_ONLY:-0} == 1 ]]; then
  run_phase h1_v1 managed_h1_v1_baseline success 'H1V1_PARITY clock=forward drawdown=False warmup=168 feed_bars=3'
  run_phase h1_v1 managed_h1_v1_drawdown success 'H1V1_PARITY clock=forward drawdown=True warmup=168 feed_bars=3'
  exit 0
fi

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

run_paper_probe() {
  for scenario in stale concurrent; do
    run_phase "paper_$scenario" managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
    run_phase "paper_$scenario" ledger_partial_report success 'revision=2 executions=1'
    run_phase "paper_$scenario" ledger_reconcile success 'state=created_from_report executions=1'
    run_phase "paper_$scenario" journal_seed success 'orders=2 events=3 cash=9954.955 holding=0.5'
    run_phase "paper_$scenario" snapshot_seed success 'revision=2 orders=2 journal_events=3'
    run_phase "paper_$scenario" "paper_$scenario" success "phase=$scenario decision=$( [[ "$scenario" == stale ]] && echo BLOCK_STALE_REVISION || echo SERIALIZED )"
  done
  run_phase paper_stale paper_stable success 'phase=stable decision=SUBMITTED_PAPER snapshot=3 current=3 new_submissions=1'
  run_phase paper_torn managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
  run_phase paper_torn ledger_partial_report success 'revision=2 executions=1'
  run_phase paper_torn ledger_reconcile success 'state=created_from_report executions=1'
  run_phase paper_torn journal_seed success 'orders=2 events=3 cash=9954.955 holding=0.5'
  run_phase paper_torn snapshot_seed success 'revision=2 orders=2 journal_events=3'
  run_phase paper_torn journal_reverse success 'decision=HOLD_CORRECTION_PENDING events=4'
  run_phase paper_torn paper_torn success 'phase=torn decision=BLOCK_PAPER_SOURCE_MISMATCH new_submissions=0'
}

seed_intent_report() {
  local report=$1
  run_phase "$report" managed_manager_submit_seed forced_exit 'new_submissions=1 manager=run'
  run_phase "$report" ledger_partial_report success 'revision=2 executions=1'
  run_phase "$report" ledger_reconcile success 'state=created_from_report executions=1'
  run_phase "$report" journal_seed success 'orders=2 events=3 cash=9954.955 holding=0.5'
  run_phase "$report" snapshot_seed success 'revision=2 orders=2 journal_events=3'
  run_phase "$report" paper_stale success 'decision=BLOCK_STALE_REVISION snapshot=2 current=3 new_submissions=0'
}

run_intent_probe() {
  seed_intent_report intent_before
  run_phase intent_before intent_crash_before_dispatch forced_exit 'phase=before_dispatch intent=durable broker=absent new_submissions=0'
  run_phase intent_before intent_recover_absent success 'decision=RECOVERED_ABSENT new_submissions=1'
  run_phase intent_before intent_recover_repeat success 'decision=RECOVERED_EXISTING new_submissions=0'
  run_phase intent_before restore_paper_intent_join success 'decision=JOINED_RESTART_MATCH revision=3 cash=9955.455 holding=0.5 open_orders=3 callbacks=0 new_submissions=0'
  run_phase intent_before restore_paper_intent_join_mismatch success 'decision=BLOCK_ORDER_IDENTITY open_orders=3 new_submissions=0'

  seed_intent_report intent_after
  run_phase intent_after intent_crash_after_commit forced_exit 'phase=after_commit intent=pending broker=submitted ack=lost new_submissions=1'
  run_phase intent_after intent_recover_existing success 'decision=RECOVERED_EXISTING new_submissions=0'
  run_phase intent_after intent_recover_repeat success 'decision=RECOVERED_EXISTING new_submissions=0'
  run_phase intent_after restore_paper_intent_join success 'decision=JOINED_RESTART_MATCH revision=3 cash=9955.455 holding=0.5 open_orders=3 callbacks=0 new_submissions=0'

  seed_intent_report intent_unknown
  run_phase intent_unknown intent_crash_before_dispatch forced_exit 'phase=before_dispatch intent=durable broker=absent new_submissions=0'
  run_phase intent_unknown intent_mark_unknown success 'phase=mark_unknown report=unknown'
  run_phase intent_unknown intent_recover_unknown success 'decision=BLOCK_UNKNOWN_REPORT new_submissions=0'

  seed_intent_report intent_conflict
  run_phase intent_conflict intent_crash_before_dispatch forced_exit 'phase=before_dispatch intent=durable broker=absent new_submissions=0'
  run_phase intent_conflict intent_mark_conflict success 'phase=mark_conflict report=conflicting'
  run_phase intent_conflict intent_recover_conflict success 'decision=BLOCK_CONFLICTING_REPORT new_submissions=0'
}

if [[ "${TL001A_COST_FILL_ONLY:-0}" == 1 ]]; then
  run_phase cost_fill cost_fill success 'decision=HOLD_OPTIMISTIC_FULL_FILL'
  exit 0
fi

if [[ "${TL001A_CONSERVATIVE_ONLY:-0}" == 1 ]]; then
  run_phase conservative_historical conservative_historical success 'fill=0.4@100.21 fee=0.040084 remaining=0.6'
  run_phase conservative_forward conservative_forward_seed forced_exit 'execution=committed fill=0.4@100.21 remaining=0.6 cash=959.875916 holding=0.4 new_submissions=0'
  run_phase conservative_forward conservative_forward_restore success 'decision=HOLD_REMAINING_OPEN cash=959.875916 holding=0.4 open_orders=1 new_submissions=0'
  run_phase conservative_forward conservative_forward_repeat success 'decision=HOLD_REMAINING_OPEN cash=959.875916 holding=0.4 open_orders=1 new_submissions=0'
  run_phase conservative_forward conservative_forward_mismatch success 'decision=BLOCK_FILL_OR_ACCOUNT_MISMATCH new_submissions=0'
  exit 0
fi

if [[ "${TL001A_JOINED_ONLY:-0}" == 1 ]]; then
  run_phase joined joined_intent_seed success 'client=stable status=durable new_submissions=0'
  run_phase joined submit_seed forced_exit 'broker_id=TL001A-BROKER-ORDER-1 quantity=1 new_submissions=1'
  run_phase joined joined_partial_crash forced_exit 'fill=0.4@89.91 fee=0.035964 remaining=0.6 missed=HOLD rejected=REJECT ledger=absent new_submissions=0'
  run_phase joined joined_reconcile_partial success 'ledger=one_execution cash=9964.000036 holding=0.4 open_orders=1 next=BLOCK_FIRST_ORDER_OPEN new_submissions=0'
  run_phase joined joined_reconcile_repeat success 'execution=verified_once open_orders=1 new_submissions=0'
  run_phase joined joined_correct_hold success 'report=3 ledger=2 next=BLOCK_STALE_REVISION or_BLOCK_LEDGER_BEHIND new_submissions=0'
  run_phase joined joined_reconcile_correction success 'execution=corrected cash=9963.996032 holding=0.4 open_orders=1 new_submissions=0'
  run_phase joined joined_cancel_remaining success 'report=4 first_order=closed cash=9963.996032 holding=0.4 open_orders=0 new_submissions=0'
  run_phase joined joined_next_submit success 'decision=SUBMITTED_AFTER_RECONCILIATION new_submissions=1'
  run_phase joined joined_next_repeat success 'decision=ADOPT_EXISTING_NEXT_ORDER open_orders=1 new_submissions=0'
  run_phase joined joined_bad_account success 'decision=BLOCK_EXECUTION_ACCOUNT_MISMATCH new_submissions=0'
  exit 0
fi

if [[ "${TL002_JOIN_ONLY:-0}" == 1 ]]; then
  bridge="$source_dir/../tl002_lean_join.py"
  database="$report_dir/tl002.sqlite3"
  report="$report_dir/tl002.json"
  export TL002_BRIDGE_PYTHON=python3 TL002_BRIDGE_SCRIPT="$bridge" \
    TL002_BRIDGE_DATABASE="$database"
  run_phase tl002 joined_intent_seed success 'client=stable status=durable new_submissions=0'
  python3 "$bridge" prepare "$database" "$report"
  run_phase tl002 submit_seed forced_exit 'broker_id=TL001A-BROKER-ORDER-1 quantity=1 new_submissions=1'
  python3 "$bridge" reconcile "$database" "$report"
  run_phase tl002 joined_partial_crash forced_exit 'fill=0.4@89.91 fee=0.035964 remaining=0.6'
  python3 "$bridge" reconcile "$database" "$report"
  run_phase tl002 joined_reconcile_partial success 'ledger=one_execution cash=9964.000036 holding=0.4'
  python3 "$bridge" reconcile "$database" "$report"
  run_phase tl002 joined_correct_hold success 'report=3 ledger=2 next=BLOCK_STALE_REVISION'
  python3 "$bridge" reconcile "$database" "$report"
  run_phase tl002 joined_reconcile_correction success 'execution=corrected cash=9963.996032 holding=0.4'
  run_phase tl002 joined_cancel_remaining success 'report=4 first_order=closed cash=9963.996032'
  python3 "$bridge" reconcile "$database" "$report"
  python3 "$bridge" reconcile "$database" "$report"
  run_phase tl002 joined_selection_policy success 'sell=FILLED realized=-0.123884 stale=HOLD missed=HOLD invalid=REJECT new_submissions=0'
  python3 "$bridge" prepare-sell "$database" "$report"
  run_phase tl002 joined_tl002_sell_submit forced_exit 'quantity=-0.4 limit=89.79 state=submitted new_submissions=1'
  python3 "$bridge" reconcile-sell "$database" "$report"
  run_phase tl002 joined_tl002_sell_restore_pending success 'cash=9963.996032 holding=0.4 open_orders=1 new_submissions=0'
  run_phase tl002 joined_tl002_sell_fill_crash forced_exit 'execution=local_report cash=9999.876116 holding=0 journal=behind new_submissions=0'
  python3 "$bridge" reconcile-sell "$database" "$report"
  run_phase tl002 joined_tl002_sell_reconcile success 'cash=9999.876116 holding=0 realized=-0.123884 open_orders=0 new_submissions=0'
  run_phase tl002 joined_tl002_sell_repeat success 'cash=9999.876116 holding=0 realized=-0.123884 open_orders=0 new_submissions=0'
  python3 "$bridge" reconcile-sell "$database" "$report"
  exit 0
fi

if [[ "${TL001A_SELECTION_ONLY:-0}" == 1 ]]; then
  export TL001A_SELECTION_RULES="$source_dir/fixtures/selection_rules_v1.json"
  export TL001A_SELECTION_QUOTE="$source_dir/fixtures/selection_quote_v1.json"
  seed_selection() {
    local name=$1
    run_phase "$name" joined_intent_seed success 'client=stable status=durable new_submissions=0'
    run_phase "$name" submit_seed forced_exit 'broker_id=TL001A-BROKER-ORDER-1 quantity=1 new_submissions=1'
    run_phase "$name" joined_partial_crash forced_exit 'fill=0.4@89.91 fee=0.035964 remaining=0.6'
    run_phase "$name" joined_reconcile_partial success 'ledger=one_execution cash=9964.000036 holding=0.4'
    run_phase "$name" joined_correct_hold success 'report=3 ledger=2 next=BLOCK_STALE_REVISION'
    run_phase "$name" joined_reconcile_correction success 'execution=corrected cash=9963.996032 holding=0.4'
    run_phase "$name" joined_cancel_remaining success 'report=4 first_order=closed cash=9963.996032'
  }
  seed_selection selection_correction_first
  run_phase selection_correction_first joined_selection_policy success 'sell=FILLED realized=-0.123884 stale=HOLD missed=HOLD invalid=REJECT'
  run_phase selection_correction_first joined_selection_correction_first success 'decision=BLOCK_CORRECTION_PENDING new_submissions=0'
  seed_selection selection_submission_first
  run_phase selection_submission_first joined_selection_submission_first success 'decision=SERIALIZED_AFTER_SUBMISSION new_submissions=1 later_decision=BLOCK_CORRECTION_PENDING'
  seed_selection selection_unknown
  run_phase selection_unknown joined_selection_unknown success 'decision=BLOCK_SUBMISSION_UNKNOWN initial_calls=1 retry_submissions=0'
  exit 0
fi

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
if [[ "${TL001A_PAPER_ONLY:-0}" == 1 ]]; then
  run_paper_probe
  exit 0
fi
if [[ "${TL001A_INTENT_ONLY:-0}" == 1 ]]; then
  run_intent_probe
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
run_paper_probe
run_intent_probe
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
