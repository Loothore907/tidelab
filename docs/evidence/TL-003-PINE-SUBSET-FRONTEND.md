# TL-003 Pine v5 subset frontend

Issue [#95](https://github.com/Loothore907/tidelab/issues/95). This is intake foundation using only TideLab-authored source and invented hourly bars. It selects no external candidate and performs no market-data trial.

## Accepted source grammar

`tidelab-pine-v5-subset-1` accepts UTF-8 without BOM, LF line endings and exactly these eight lines with a final LF. Text in angle brackets is a bounded token; all other spaces, punctuation and indentation are literal.

```text
//@version=5
strategy("<ASCII title>", overlay=false, pyramiding=0, process_orders_on_close=false, calc_on_every_tick=false, default_qty_type=strategy.percent_of_equity, default_qty_value=<percent>)
entrySignal = close > ta.sma(close, <window>)
exitSignal = close < ta.sma(close, <same window>)
if entrySignal
    strategy.entry("L", strategy.long)
if exitSignal
    strategy.close("L")
```

The title is 1–64 ASCII letters, digits, spaces, underscores or hyphens. `percent` is an integer 1–100; `window` is an integer 2–10000. Source size is at most 16 KiB. The normalized package is version 1, spot/long-cash/hourly only, with one fixed fraction and close/SMA comparisons. Source bytes are SHA-256 bound to a `synthetic_example` intake record; the package binds that exact record digest. The CLI accepts only records and fixtures under `research/examples/`, and writes a new result file under ignored `data/`.

The parser does not execute Pine. Other versions, options, expressions, order forms, comments, extra lines, alternate sizing, intrabar behavior, alerts, security calls, multiple instruments, shorts and dynamic state get a named unsupported outcome. Missing or mismatched source records fail before compilation. This is a TideLab normalized signal and next-open synthetic execution contract, not a claim of full TradingView broker-emulator or order-sizing parity. The static long/cash rule is a deliberately bounded parser fixture, not a sourced trading hypothesis.

## Conformance and retained outcomes

Each `.pine` file has an independently specified `.trace.json` beside it. Its exact source hash and each closed-bar entry/exit predicate are compared with the compiled package on the synthetic fixture, from warmup through the penultimate bar. A missing or drifting trace is `conformance_failed`; the package is not evaluated. Successful packages use the existing normalized parser and `evaluate_batch` next-open costed contract path. The output records one indexed result and source hash per `.pine` file, including `unsupported_pine`, `rejected_before_test` and `conformance_failed`. A new output path is required for every run, so an earlier failure cannot be overwritten.

From the repo root with the pinned Python environment:

```powershell
.\.venv\Scripts\python.exe scripts/pine_subset_batch.py `
  --sources research/examples/pine-subset-v1 `
  --record research/examples/pine-subset-v1/synthetic-sma-2.record.json `
  --record research/examples/pine-subset-v1/synthetic-sma-3.record.json `
  --record research/examples/pine-subset-v1/synthetic-unsupported-ema.record.json `
  --fixture research/examples/strategy-batch-synthetic-bars-v1.json `
  --output data/strategy_batch/pine-subset-run-001.json
```

The authored examples contain two supported windows and one captured EMA source. The EMA source must report `unsupported_pine` with `unsupported_signal_expression`; it has no conformance trace or runnable package.

This path is only a source frontend and synthetic contract check. Raw papers, repositories, general Pine syntax, historical batch evaluation, durable cross-run trial accounting, search-aware ranking and pinned LEAN parity remain future #95 slices. Issues #3 and #48 retain separate data and external execution gates.
