# TL-003 synthetic batch attempt ledger

Issue [#95](https://github.com/Loothore907/tidelab/issues/95). This is pipeline accounting for TideLab-authored synthetic inputs. It does not open a research partition, use market data, select a candidate, or replace the separate research `TrialRegistry`.

The normalized JSON and pinned Pine subset CLIs now share the fixed `tidelab-strategy-batch-v1` engine and one cost identity: initial cash `10000`, fee rate `0.0025`, adverse rate `0.001`, quantity unit `0.00000001`. Their synthetic fixture bytes are SHA-256 bound. Before parsing, each CLI appends a run and every numbered input digest to ignored `data/strategy_batch/synthetic_trials.sqlite3`. A crash leaves an open run and its counted variants. After writing a new, non-overwritable JSON artifact, it appends all outcomes and the artifact digest in one SQLite transaction. Neither the run nor its variants or outcomes can be updated or deleted through ordinary SQL; this local database is not tamper-proof evidence.

Every source or package file has one numbered outcome. `needs_source_parser` is an additional unnumbered record in the normalized package CLI. The ledger rejects missing or duplicate input indexes, changed source/file hashes, mismatched fixture or cost identity, invalid statuses, and a summary that disagrees with the outcomes. Pine outcomes record parse, conformance and test stages; normalized packages record parse and test stages with conformance marked not applicable. All statuses, including unsupported and rejected inputs, count toward the cross-run denominator. Identical artifact bytes written to different output paths are distinct attempts. An identical recovery of one registered artifact is idempotent.

The existing CLI examples in the [pipeline decision](../decisions/TL-003-DETERMINISTIC-STRATEGY-PIPELINE.md) and [Pine subset document](TL-003-PINE-SUBSET-FRONTEND.md) now append to the ledger by default. Choose a new `--output` path for every run. The optional `--ledger` path must remain under ignored `data/`.

```powershell
.\.venv\Scripts\python.exe scripts/synthetic_batch_ledger.py summary

# If a run wrote its output but stopped before ledger completion:
.\.venv\Scripts\python.exe scripts/synthetic_batch_ledger.py recover `
  --artifact data/strategy_batch/<existing-run>.json
```

Recovery checks the original registered output path, input denominator, source digests, fixture, cost and artifact content. It never re-executes a strategy. `summary` lists open output keys and their counted variants; an open run without an output is not claimed complete. The ledger records synthetic contract attempts, not evidence of TradingView broker parity or profitability.

Next #95 slice: compare the same normalized package and synthetic inputs through the pinned LEAN path, with explicit signal, fill timing and cost discrepancies. A rights-gated historical batch evaluator remains later work; #3 data and #48 external execution authority remain independent.
