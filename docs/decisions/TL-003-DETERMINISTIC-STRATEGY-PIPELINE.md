# TL-003 deterministic strategy pipeline

Owner: [issue #95](https://github.com/Loothore907/tidelab/issues/95). Date: 2026-09-26 UTC. The owner clarified that TideLab's product is a platform that ingests, parses and tests strategies at scale. An agent manually selecting, interpreting, coding and judging one strategy at a time is not that platform. AI may assist a source translation, but it is not the primary evaluator and its proposed rule has no authority until deterministic validation and source review pass.

## Intended flow

`Source bytes + rights/provenance -> source-specific parser -> typed, versioned strategy package -> capability check -> deterministic batch screen -> recorded trials and search-aware review -> deeper pinned LEAN/forward evaluation`.

Every stage emits a machine-readable status. Unparseable text, unsupported operators or product capabilities, missing implementation rights, incomplete data and failed tests remain visible outcomes. They never become guessed rules or silently disappear from the denominator. No third-party program is executed during intake. The platform records all attempted variants, including failures, before ranking any survivor; real-data selection needs a preregistered budget, common cost/data identities, chronological partitions and adjustment for searching many related rules.

The first implementation handles **normalized TideLab JSON packages**. Each binds an exact intake-record version and digest, declares spot/long-cash/hourly requirements, and contains a typed close/SMA/constant expression tree with comparisons and Boolean combinations. The parser bounds size, depth, node count, lags and windows. Non-synthetic records must already be `implementation_selected` with documented implementation use and be the latest registered version. The initial batch CLI uses only TideLab-authored synthetic hourly fixtures and writes one status per package to ignored `data/`, including malformed and duplicate packages. It cannot read local market history. A synthetic next-open, costed full-fill check tests rule timing and cash arithmetic, not profitability or venue execution. One test passes 1,000 distinct packages through the same code path without per-strategy source edits or model calls.

This is a **supported subset**, not an assertion that arbitrary papers, repositories or Pine scripts have been parsed. A source with no normalized package reports `needs_source_parser`. Dedicated deterministic frontends should target source formats with stable grammars and sufficient semantics, starting with a bounded Pine subset or an explicit repository manifest. A paper's prose may lack executable entry, exit, sizing, time and cost definitions. Such a paper remains `captured` or `specified` with named ambiguities until a reviewed package can be made; optional AI extraction can produce a draft with source spans, never a hidden automatic promotion. Parser conformance cases must compare the normalized rule with the source's own examples or independently specified traces.

Historical batch evaluation is a later slice: use common rights-cleared data snapshots, one execution/cost model, persistent trial accounting, benchmark and uncertainty metrics, and a back end that can prove parity with the selected pinned LEAN path for shortlisted rules. Keep source parsing, target generation, risk, fills and accounting separate. The current synthetic checker is a contract test, not a second production engine. Issue #3 still owns timely data and publication rights; issue #48 still owns external execution and recovery. This decision grants no real-data batch trial, account access, order, spend or live authority.

## Reproducible synthetic example

After integration, run from the repository root with the pinned Python environment:

```powershell
.\.venv\Scripts\python.exe scripts/strategy_batch.py `
  --packages research/examples/strategy-batch-packages `
  --record research/examples/strategy-batch-synthetic-record-v1.json `
  --fixture research/examples/strategy-batch-synthetic-bars-v1.json `
  --output data/strategy_batch/example-v1.json
```

The output file is created once and never overwritten. `synthetic_contract_tested` means only that this supported package parsed and ran against invented bars. The returned hash binds the private output; it is not an investment verdict. Supply a new output path for another run and retain every variant's outcome.
