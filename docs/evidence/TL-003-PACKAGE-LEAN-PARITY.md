# Synthetic normalized-package / LEAN execution parity

Owner: [issue #95](https://github.com/Loothore907/tidelab/issues/95). Scope and expectations were fixed in [the pre-code contract](../decisions/TL-003-PACKAGE-LEAN-PARITY.md). This is reusable foundation integration, not a strategy selection or historical-data trial.

## Reproduce

Use Python 3.12, .NET SDK 10.0.401 and a clean LEAN checkout at `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`. No QuantConnect account, LEAN CLI, market-data acquisition or upstream source patch is involved. The runner builds against LEAN's public projects; use an isolated checkout so generated build files do not interfere with another experiment. Run one invocation at a time against the shared build directory.

From the repository root on Linux (also exercised locally through WSL):

```bash
python scripts/package_lean_parity.py \
  --package research/examples/strategy-batch-packages/synthetic-sma-3-v1.json \
  --record research/examples/strategy-batch-synthetic-record-v1.json \
  --fixture research/examples/strategy-parity-gap-bars-v1.json \
  --lean-root /path/to/pinned-clean-lean \
  --dotnet /path/to/dotnet \
  --output data/package_lean/unique-attempt
```

Exit zero means the full comparison matched. An unsupported input, runtime failure or mismatch exits nonzero and retains its reason. Reusing an output directory is rejected. The result is `result.json`; inspect `python.json`, `lean.json`, `build.log` and `engine.log` for the evidence. `attempt.json` binds the contract, TideLab head/dirty state, actual runtime-source hashes and cost identity; `identities.json` binds retained exact input bytes, and `runtime.json` records the SDK and LEAN pin. A started directory without a result is an incomplete attempt, not a passing run. These are synthetic attempt artifacts, not the real research trial registry. Do not delete failed attempts to obtain a clean result.

Use the same command with `research/examples/strategy-parity-logic-v1.json` and `research/examples/strategy-parity-logic-record-v1.json` to exercise a different expression tree without C# edits. The separately attributed synthetic example exercises Boolean operators, a constant and lagged close in addition to the moving average. No external candidate is selected.

## What is exercised

The current Python replay loop emits optional per-bar predicates/actions, fills and account traces. The C# interpreter reads the package's expression tree and independently computes predicates. At the next synthetic open it sizes the pending cash budget, submits a LEAN market order, and lets `BacktestingTransactionHandler`, `BacktestingBrokerage`, the declared full-fill/fee models and LEAN portfolio accounting process the result. Cash and holdings are never copied from Python or overwritten after fills.

The harness supplies invented open/close observations and their UTC clock. A signal-close and following-open event share a UTC boundary but have different bar indices/phases. The harness updates the synthetic asset's currency conversion quote when its price changes, as required to value LEAN's crypto cashbook; it does not change the asset balance. `NullDataFeed` throws if asked to acquire/subscribe to data. Static engine market-hours and symbol-property files are used for initialization, with explicit synthetic instrument rules.

This is an actual LEAN execution-components check, not Launcher/AlgorithmManager dispatch, asynchronous recovery, a real brokerage or forward-feed acceptance. Full fills and costs are intentionally controlled assumptions. The cross-runtime numeric domain is narrower than the general package parser; outside-domain values are rejected. Money comparisons allow at most 1e-18 absolute decimal difference; quantities, times, sequence and structure are exact.

## Acceptance evidence

Local verification on 2026-09-26: the focused Python 3.12.13 / .NET 10.0.401 WSL run passed all 13 tests, including all five real LEAN integration cases. The Windows suite passed 123 tests, with the optional Nautilus test and five explicitly environment-gated LEAN cases skipped; context tests passed 2/2. The LEAN acceptance comes from the separate runtime run, not those skips. Exact-head CI and review results are recorded in the owning PR.

`tests/test_package_lean_parity.py` checks a worked five-bar example independently: the signal close is 102, the next open is 200, and a 2,500 cash budget buys 12.45637155 units at 200.2 with a 6.234413960775 fee. Selling at the next open of 50 yields a modeled price of 49.95 and final cash 8120.64027125441875. These invented values expose same-close execution and incorrect fee handling. The suite also checks a second expression package, repeated execution, warmup/no trades, open terminal holdings, unsupported inputs, invalid input retention, and mutations of fill time/fee/quantity that must be detected.

Set `TIDELAB_LEAN_ROOT` and optionally `TIDELAB_DOTNET`, then run:

```bash
python -m pytest tests/test_package_lean_parity.py --basetemp=artifacts/package-parity-new-run
```

Choose a new basetemp path per local run to preserve prior attempts. The dedicated `lean-package-parity` CI job supplies the pinned checkout and SDK, runs the real integration cases on Python 3.12, and retains synthetic attempts/logs even on failure. Without the environment variable, the five runtime cases skip explicitly; Python unit checks alone are not LEAN evidence. Consult the PR's exact-head CI for the actual remote result rather than treating this job definition as proof.

Early local attempts are retained under ignored `data/package_lean/`: one exposed the missing synthetic base-currency conversion quote; a follow-up compile rejected an internal setter; the correction uses LEAN's public currency-conversion interface. These were adapter errors, not a change to the frozen timing or accounting contract. The pinned upstream build emits dependency vulnerability and missing-ruleset warnings; they are retained in build logs, not suppressed or resolved by this slice. This harness does not establish that the dependency bundle is suitable for production/distribution.
