# TL-003 registered synthetic historical batch evidence

Owner: [issue #95](https://github.com/Loothore907/tidelab/issues/95). Implements the [backend contract](../decisions/TL-003-HISTORICAL-BATCH-BACKEND.md). Classification: foundation integration. No external candidate was selected and no real price partition was opened.

## Capability and reproduction

The CLI generates invented hourly market-event SQLite history and evaluates a frozen normalized-package plan through one shared replay implementation. It uses the existing research `TrialRegistry` with additive atomic batch admissions, not the synthetic intake ledger. Every input job remains visible, including invalid, unsupported and duplicate packages. Both source examples use the same backend without per-strategy code.

From the repository root, choose a new output path:

```powershell
.\.venv\Scripts\python.exe scripts/historical_batch.py demo --output data/historical_batch/demo-v1
```

The small demo has 19 jobs: eight strategy/market/cost combinations, eight cash/passive comparisons and three retained rejection cases. Baseline and stress share the same invented history. An output directory is never reused. The `fixture/` directory retains the generated database, plan, source records, packages and precomputed snapshot descriptor; `attempt/` holds frozen inputs, runtime source hashes, admission inventory, captured verified source rows, streamed per-job traces, results and manifests. `trials.sqlite3` records research attempts and batch admissions/outcomes. These local artifacts remain ignored by Git.

A caller with its own **synthetic** files can use:

```powershell
.\.venv\Scripts\python.exe scripts/historical_batch.py run `
  --plan data/my-synthetic/plan.json --snapshot data/my-synthetic/snapshot.json `
  --database data/my-synthetic/synthetic.sqlite3 --registry data/my-synthetic/trials.sqlite3 `
  --output data/my-synthetic/attempt-01
```

The generated plan is the concrete schema example. It fixes package/record byte digests, ordered jobs, two cost scenarios, markets, disjoint phase ranges, warmup, finite budget, benchmark allocation and descriptive metrics. Only synthetic development executes; third-party data, validation and untouched modes fail before any price read. An authority field is a synthetic-scope marker, not a mechanism for approving real research. General JSON parsing and source-provenance checks cannot establish external rights or real owner authorization.

## Semantics and failure behavior

The internal `replay_package` function was extracted from `evaluate_synthetic`; the original synthetic wrapper remains. Costs, quantity units and scored boundaries are explicit. Quantities floor to a multiple of the unit, including units such as 0.03. Warmup updates indicators without orders or scored returns. The account starts flat at the first scored bar; signals use completed closes and fills use the next scored open. No terminal forced sale or cross-partition position carry occurs. Cash/passive benchmarks use the same account, cost and marking semantics; passive enters at the first scored open, an explicitly earlier opportunity than the strategy.

Reported metrics are net return, close-marked drawdown, fills, completed round trips, fees, turnover, exposure and terminal inventory. No-trade and remaining inventory are valid results. These are descriptive full-fill scenarios; neither search-aware statistical review nor a profitability verdict is implemented. There is no multi-asset portfolio, liquidity/capacity claim or AlgorithmManager/feed integration.

Admission freezes the complete inventory transactionally before price access and starts all executable trial records before the first partition read. Each market is validated once and reused in memory. Snapshot verification checks exact source, provenance, closed contiguous hourly rows, OHLCV validity and the predeclared digest within one read transaction. The reader requests `[score_start - warmup, score_end)` only. Missing, duplicate or changed rows fail; no truncation or gap filling occurs. Bounds remain 10,000 total bars per market and 10,000 planned jobs; supported decimal costs/prices are checked before evaluation.

A registry permits one open batch. Concurrent requests retain the losing request's rejection. Normal rerun rejects an already reserved phase. Failed/aborted development may be explicitly retried with `--retry-of BATCH_ID`, using the identical plan and retaining previous attempts; it never restores validation/untouched access. This is a local audit/control boundary, not a tamper-proof global registry or a way to detect all prior exposures across renamed experiments and separate databases.

A process crash leaves its inventory and partial files. Recovery holds an OS file lock and never reads prices or replays a job:

```powershell
.\.venv\Scripts\python.exe scripts/historical_batch.py recover `
  --output data/my-synthetic/attempt-01 --registry data/my-synthetic/trials.sqlite3
```

This completes missing metadata only from verified finalized artifacts. If execution was unfinished, it refuses; use the same command with `--abort` to retain partial files, append aborted dispositions and close the batch. Completed artifacts are recovered as completed even during abort. Hash/identity disagreement remains an error. Process-death recovery is tested; power-loss durability across filesystems is not claimed.

## Verification

The acceptance tests exercise the whole SQLite-to-results path, independent gap/fee/drawdown arithmetic, lot multiples, no warmup fills, terminal holdings, missing/duplicate/mutated snapshots, preflight denial without price reads, concurrent admission and actual process deaths after reservation, start and artifact publication. Recovery tests replace the price reader and replay with functions that fail if called. The original synthetic package/parity regressions remain.

`tests/test_historical_batch.py` also compares both supported packages under baseline and stress with the pinned LEAN order/fill/portfolio path, using the same scoring boundary. The CI `lean-package-parity` job runs these actual runtime cases along with the original parity cases and retains their synthetic artifacts. This extends the existing comparator rather than replaying Python fills into LEAN.

Local and remote run evidence is recorded in the implementation PR and #95. The fixed scale demonstration below is a synthetic repeated-template workload, not evidence of broad source-language support.

```powershell
.\.venv\Scripts\python.exe scripts/historical_batch.py demo --scale --output data/historical_batch/scale-v1
```

The workload is 100 distinct package variants (two rule templates with different allocations), two invented markets, two costs and 2,000 bars per market including three warmup bars. It adds eight benchmark jobs and three rejection cases: 411 submitted jobs, 408 executable configurations. Measure elapsed time and process peak memory on the target environment; compare trace digests from a separately retained repeat to establish determinism. Runtime, memory and repeat results are recorded at closeout rather than inferred from the earlier twelve-bar checker.

## Next boundary

This completes the synthetic development foundation when its review and integration gates pass. A real-data enablement proposal must separately bind an approved candidate set, exact snapshot/rights receipt, prior exposure, finite search budget and phase decisions. It also needs the broader uncertainty/search-aware review required by the research protocol before any edge claim. Do not migrate or reopen the frozen H1, five-market screen or low-volatility studies as an implementation shortcut. #3's timely data and #48's external execution remain independent.
