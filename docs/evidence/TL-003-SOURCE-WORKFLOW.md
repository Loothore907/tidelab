# Repeatable authored source-to-results workflow

Owner: [#95](https://github.com/Loothore907/tidelab/issues/95). Classification:
foundation integration. Base `bc1ae9b8fb574958489c89a9276de1fae2bc38b1`;
branch `codex/95-source-results`. The consumer supplies supported source files,
intake records and independent traces through one manifest, then receives a
finite, fully accounted synthetic historical batch. No new evaluator or parser
grammar, external strategy, private admission or real-data trial is introduced.

## Reproduce

Use Python with the repository dependencies installed, the existing clean LEAN
checkout pinned to `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, and .NET 10.0.401:

```sh
python scripts/source_workflow.py run \
  --manifest research/examples/source-workflow-v1/manifest.json \
  --output data/source_workflow/run-01 \
  --lean-root /path/to/pinned/Lean \
  --dotnet /path/to/dotnet
```

The output must be a new directory under `data/source_workflow/`. There is no
database or private-policy argument. The command creates isolated synthetic
stores there and never accesses the canonical real-trial registry, private
archives, consumed grants or RSI store anchor. `TIDELAB_LEAN_ROOT` and
`TIDELAB_DOTNET` can supply the two runtime paths. The command requires the
pinned comparison; Python-only unit checks explicitly report parity `not_run`.

The [frozen corpus](../../research/examples/source-workflow-v1/README.md) describes
the independent truth tables and exact supported subset. All source files and
intake records are captured before each input is compiled; the entire declared
input inventory is recorded before the first source read. Missing/changed files,
invalid records, unsupported semantics and conformance discrepancies retain
numbered outcomes. Prose is never guessed or executed. Only conformance-matched,
capability-supported packages become historical jobs.

### Importing named SMA expressions (grammar 3)

For Pine inputs, explicitly select `"grammar_version": "tidelab-pine-v5-subset-3"`
in the manifest. The [import corpus](../../research/examples/pine-import-v3/manifest.json)
uses the same command above with that manifest and a fresh output directory.
Versions 1 and 2 retain their original outcomes; omitting the choice still selects 1.

Grammar 3 accepts blank lines, horizontal token spacing, full-line/inline `//`
comments, and up to 64 top-level declarations before the two order blocks.
Names can refer to previously declared names, `close`, integer window constants,
`ta.sma(close-or-alias, integer-or-alias)`, and close-above/below-SMA comparisons.
Declarations are evaluated per bar: persistent `var`/`varip`, reassignment,
forward/unknown references and reserved names are rejected. Both conditions must
resolve to the existing entry-above/exit-below rule with the same SMA window.
The two order blocks remain entry-long then close, with ID `L`; bodies require
four spaces or one tab. Strategy options and their order remain fixed, including
next-open timing. No new indicator, trading rule or evaluator is introduced.

The first line remains exactly `//@version=5`. UTF-8 without BOM, LF, final
newline and 16 KiB maximum still apply. Directives after the first line, block
comments, wrapped statements, general expressions and other order forms remain
unsupported. Original bytes are hashed before parsing; formatting changes never
silently overwrite a source identity. This is a bounded normalization contract,
not general TradingView compatibility. See the official v5
[declaration](https://www.tradingview.com/pine-script-docs/v5/language/variable-declarations/)
and [structure](https://www.tradingview.com/pine-script-docs/v5/language/script-structure/)
references for the distinction between per-bar declarations, reassignment and blocks.

The six authored inputs include the unchanged formerly rejected alias source,
two formatting/name/window variations and three rejected semantic changes.
Expected results are three compiled inputs, three unsupported, eight completed
jobs and two semantic duplicates, with four LEAN comparisons. Frozen truth sets
are independently checked by rational SMA arithmetic. This remains one rule
structure. Adding an input still needs source, intake record, independent trace
and manifest references; grammar 3 removes source rewriting for this subset, not
those preparation requirements. Per-input runtime edits remain zero. Preparation
time is unmeasured; run timing and complete outcomes are generated in the output.

## Artifacts and accounting

- `sources/`: original manifest, exact source/record/trace/history bytes, generated
  packages, compilation outcomes and a verified manifest. The immutable source
  ledger completion binds the captured-file hashes as well as every input outcome.
- `sources.sqlite3`: existing `SyntheticBatchLedger`, with a compilation-only
  outcome kind. `compiled` means trace agreement, never historical success. Its
  legacy fixed cost tag is not the historical cost policy; no evaluation happens
  in this ledger. Actual common baseline/stress costs are frozen in the batch plan.
- `plan.json`, `snapshot.json`, `history.sqlite3`: generated finite job inventory
  and invented historical snapshot. Job order is input order, then baseline/stress,
  followed by the shared cash and passive benchmarks.
- `trials.sqlite3`, `attempt/`: existing historical backend and `TrialRegistry`;
  complete admission, duplicate links, traces, metrics, retained failures and
  artifact manifests. Rejected sources have no jobs; this is distinct from a
  duplicate historical configuration or an execution failure.
- `parity/`: the existing pinned LEAN harness compares every completed,
  non-benchmark configuration/cost. Its Python trace must also equal the actual
  historical job trace. Duplicate and failed jobs are not retried for comparison.
- `results.json`: consolidated source-to-package-to-job mappings, admission
  decisions, all job outcomes, common costs, coverage, trace hashes and parity.
  `semantic_sha256` excludes run IDs, timestamps, runtime and artifact locations;
  it includes the outcomes, metrics and retained full/partial trace digests.

`accounted` means all submitted jobs have terminal outcomes; it does **not** mean
every strategy succeeded. The command exits zero only with complete accounting
and matched parity. This corpus deliberately retains two execution failures.
Unexpected failed jobs remain visible and must be assessed by the caller.

## Acceptance and measurement

The fixed corpus has ten submissions: seven JSON, two Pine and one prose; nine
distinct source byte strings; six compiled inputs; one malformed input; two
unsupported inputs (Pine EMA and futures capabilities); one `needs_source_parser`.
There are three operator structures: SMA, Boolean/lag and UTC calendar. The tiny
sizing variant, exact duplicate and equivalent Pine do not increase that count.

The one-market history has 30 invented hourly bars, three preceding warmup bars
and 27 scored bars. Six compiled inputs times two common costs plus four shared
benchmarks yield 16 ordered jobs: ten completed, four duplicates and two retained
below-unit failures. Twelve attempts are reserved and terminal, including the
two failures; six completed strategy/cost traces match actual pinned LEAN.

The initial WSL/Python 3.12.13/.NET 10.0.401 demonstration took 58.37 seconds,
including six LEAN build/run comparisons, on the Windows-mounted checkout.
This is one small-workload observation, not a throughput claim. One submitted
command needed zero per-candidate interventions. Corpus authoring and independent
trace preparation remain manual before submission. Timings and run IDs are not
determinism evidence; repeated semantic outcomes and trace digests are.

Tests cover exact input/record/history/trace mismatches, independently specified
signals and next-open arithmetic, all rejected/failed/duplicate accounting,
configuration-only addition of another existing Pine input, identical-input
semantic/trace equality, dedicated output isolation, actual LEAN comparisons and
recovery after interruption. The dedicated LEAN CI job runs this workflow test
alongside the established parity suites and retains its comparison artifacts.

## Existing recovery, without replay

```sh
python scripts/source_workflow.py recover --output data/source_workflow/run-01
```

Recovery verifies captured sources and the immutable source ledger, then invokes
the historical backend's existing artifact recovery. It does not read the source
files again, query history, recompile or rerun Python/LEAN. Completed recovery
returns the same consolidated report. If execution stopped before every job had
a complete artifact, the existing fail-closed route requires explicit `--abort`;
it preserves partial artifacts and marks unfinished jobs aborted. If all job
artifacts exist, their metadata can be completed without replay.

An interrupted run without completed LEAN comparison reports `not_run`, not a
parity pass. Source capture interruptions before a complete source manifest, or
interruptions before historical admission, remain incomplete submissions; they
are not automatically resumed. Their input-ledger rows/artifacts remain retained.
No scheduler, automatic retry or new recovery framework is claimed.

## Limits and next action

This demonstrates only a small, authored corpus under existing normalized JSON
semantics and the narrow eight-line Pine grammar. It does not establish arbitrary
TradingView, paper, repository or natural-language support, statistical promotion,
profitability, a timely feed or unattended operation. Stores, paths and source
tags enforce this synthetic route; metadata cannot prove external rights.

Distinct review, reviewed SHA, findings and exact-head CI are recorded on the
implementation PR. The next concrete action is to use this same command and a
configuration-only corpus extension to measure which unsupported source needs
justify a separately bounded next parser slice. Keep #3, #48 and #21 independent;
all previous private-study grants remain consumed.
