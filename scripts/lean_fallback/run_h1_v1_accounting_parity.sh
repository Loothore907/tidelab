#!/usr/bin/env bash
# Compare invented-bar accounting across pinned LEAN historical and forward paths.
set -euo pipefail

source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
report_dir=$(mktemp -d)
trap 'rm -f "$report_dir"/*.log; rmdir "$report_dir"' EXIT

TL_H1_V1_ACCOUNTING_ONLY=1 bash "$source_dir/run_h1_historical_probe.sh" \
  "$1" "$2" >"$report_dir/historical.log" 2>&1 || {
    tail -n 40 "$report_dir/historical.log" >&2
    exit 1
  }
TL_H1_V1_ACCOUNTING_ONLY=1 bash "$source_dir/run_forward_recovery_probe.sh" \
  "$1" "$2" >"$report_dir/forward.log" 2>&1 || {
    tail -n 40 "$report_dir/forward.log" >&2
    exit 1
  }

historical=$(grep 'H1V1_ACCOUNTING clock=historical' \
  "$report_dir/historical.log" | tail -n 1 || true)
forward=$(grep 'H1V1_ACCOUNTING clock=forward' \
  "$report_dir/forward.log" | tail -n 1 || true)
[[ -n "$historical" && -n "$forward" ]] || {
  echo 'H1 v1 accounting marker missing' >&2
  exit 1
}
historical_balances=${historical#* cash=}
forward_balances=${forward#* cash=}
[[ "$historical_balances" == "$forward_balances" ]] || {
  echo "historical: $historical_balances" >&2
  echo "forward: $forward_balances" >&2
  exit 1
}
echo "H1V1_ACCOUNTING_PARITY $historical_balances"
