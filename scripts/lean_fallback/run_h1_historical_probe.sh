#!/usr/bin/env bash
# Use with run_forward_recovery_probe.sh to compare the shared synthetic H1 rule.
set -euo pipefail

lean_root=$(realpath "$1")
dotnet_bin=$(realpath "$2")
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
test "$(git -C "$lean_root" rev-parse HEAD)" = \
  "88bce0fc6fe282378ee73c54cef1090d0d7a73ee"

cp "$source_dir/TideLabH1Skeleton.cs" \
  "$source_dir/TideLabH1V1Policy.cs" \
  "$source_dir/TideLabH1V1ResearchReplay.cs" \
  "$source_dir/TideLabH1ConservativeExecution.cs" \
  "$source_dir/TideLabH1V1TrialAccounting.cs" \
  "$source_dir/TideLabH1ProbeAlgorithm.cs" \
  "$lean_root/Algorithm.CSharp/"
mkdir -p "$lean_root/Data/tidelab_h1"
cp "$source_dir/fixtures/h1_20260101.csv" \
  "$lean_root/Data/tidelab_h1/20260101.csv"
if [[ ${TL_H1_V1_ONLY:-0} == 1 || ${TL_H1_V1_ACCOUNTING_ONLY:-0} == 1 ]]; then
  python3 "$source_dir/h1_v1_check/generate_fixture.py" \
    "$lean_root/Data/tidelab_h1_v1"
fi

"$dotnet_bin" build "$lean_root/Launcher/QuantConnect.Lean.Launcher.csproj" \
  -c Release -p:RunAnalyzers=false -p:WarningLevel=0 -v quiet

release_dir="$lean_root/Launcher/bin/Release"
config="$release_dir/config.json"
backup=$(mktemp)
report_dir=$(mktemp -d)
cp "$config" "$backup"
trap 'cp "$backup" "$config"; rm -f "$backup" "$report_dir"/*.log; rmdir "$report_dir"' EXIT
sed -E -i 's/("algorithm-type-name": ")[^"]+(".*)/\1TideLabH1ProbeAlgorithm\2/' "$config"
grep -q '"algorithm-type-name": "TideLabH1ProbeAlgorithm"' "$config"

cd "$release_dir"
if [[ ${TL_H1_V1_ACCOUNTING_ONLY:-0} == 1 ]]; then
  TL_H1_V1_PROBE=1 TL_H1_V1_ACCOUNTING=1 \
    "$dotnet_bin" QuantConnect.Lean.Launcher.dll \
    >"$report_dir/accounting.log" 2>&1 || {
      grep -Ei 'H1V1_|ERROR::|EXCEPTION|Exception|runtime error' \
        "$report_dir/accounting.log" | tail -n 40 >&2 || true
      exit 1
    }
  marker=$(grep 'H1V1_ACCOUNTING clock=historical' \
    "$report_dir/accounting.log" | tail -n 1 || true)
  [[ -n "$marker" ]] || {
    tail -n 40 "$report_dir/accounting.log" >&2
    exit 1
  }
  echo "$marker"
  exit 0
fi
if [[ ${TL_H1_V1_ONLY:-0} == 1 ]]; then
  for scenario in baseline drawdown; do
    drawdown=0
    [[ "$scenario" == drawdown ]] && drawdown=1
    TL_H1_V1_PROBE=1 TL_H1_V1_DRAWDOWN="$drawdown" \
      "$dotnet_bin" QuantConnect.Lean.Launcher.dll \
      >"$report_dir/$scenario.log" 2>&1 || {
        tail -n 35 "$report_dir/$scenario.log" >&2
        exit 1
      }
    marker=$(grep 'H1V1_PARITY clock=historical' \
      "$report_dir/$scenario.log" | tail -n 1 || true)
    [[ -n "$marker" ]] || {
      grep -Ei 'H1V1_|ERROR::|EXCEPTION|Exception|runtime error' \
        "$report_dir/$scenario.log" | tail -n 40 >&2 || true
      tail -n 35 "$report_dir/$scenario.log" >&2
      exit 1
    }
    echo "$marker"
  done
  exit 0
fi
for scenario in baseline drawdown; do
  TL001A_H1_SCENARIO="$scenario" "$dotnet_bin" \
    QuantConnect.Lean.Launcher.dll >"$report_dir/$scenario.log" 2>&1 || {
      tail -n 35 "$report_dir/$scenario.log" >&2
      exit 1
    }
  if ! grep -q 'TL001A_H1_PARITY clock=historical' \
    "$report_dir/$scenario.log"; then
    tail -n 35 "$report_dir/$scenario.log" >&2
    exit 1
  fi
  marker=$(grep 'TL001A_H1_PARITY clock=historical' \
    "$report_dir/$scenario.log" | tail -n 1)
  if [[ "$scenario" == baseline ]]; then
    expected='decisions=3:EnterLong:Approve|4:ExitToCash:Approve'
  else
    expected='decisions=3:EnterLong:BlockDrawdown|4:ExitToCash:Approve'
  fi
  utc_times='utc_times=2026-01-01T06:00:00,2026-01-01T07:00:00,2026-01-01T08:00:00,2026-01-01T09:00:00'
  [[ "$marker" == *"scenario=$scenario bars=4 $expected $utc_times"* ]] || {
    tail -n 35 "$report_dir/$scenario.log" >&2
    exit 1
  }
  echo "$marker"
done
