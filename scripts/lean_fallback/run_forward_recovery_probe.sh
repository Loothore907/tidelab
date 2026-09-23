#!/usr/bin/env bash
# Run only against a separate, pinned LEAN checkout with a local .NET 10 SDK.
set -euo pipefail

lean_root=$(realpath "$1")
dotnet_bin=$(realpath "$2")
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)

test "$(git -C "$lean_root" rev-parse HEAD)" = \
  "88bce0fc6fe282378ee73c54cef1090d0d7a73ee"
mkdir -p "$lean_root/TideLabForwardProbe"
cp "$source_dir/TideLabForwardRecoveryProbe.cs" \
  "$lean_root/Tests/Engine/Setup/"
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
  grep 'TL001A_LEAN_FORWARD' "$report_dir/$report-$phase.log"
  if [[ -n "$required" ]]; then
    grep -q "$required" "$report_dir/$report-$phase.log"
  fi
  if [[ "$expected" == "success" ]]; then
    test "$rc" -eq 0
  else
    test "$rc" -ne 0
  fi
}

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
run_phase event submit_fill success
run_phase event restore_filled success 'record=created'
run_phase conflict seed forced_exit
run_phase conflict settle_conflict success
run_phase conflict restore_conflict blocked
run_phase missing restore_missing blocked
