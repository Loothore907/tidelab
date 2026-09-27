# Configuration-only source coverage extension

Owner: [#95](https://github.com/Loothore907/tidelab/issues/95). Base:
`cf910015f9f70875cbc232947cb000f91689f80a`; branch `codex/95-corpus-coverage`.
The owner approved the previous closeout's next action: expand the authored corpus
through files/configuration to measure the next ingestion gap before parser
expansion. This slice supplies corpus data, independent expectations, acceptance
tests and evidence. No `src/` or `scripts/` runtime changes are needed.

## Observable capability and reproduction

The operator can submit [corpus v2](../../research/examples/source-workflow-v2/README.md)
to the existing command. It carries nine supported submissions covering five
existing rule structures through compilation/conformance, common costs and
benchmarks, complete historical accounting and actual pinned-LEAN comparison.
Every rejected source also retains an explicit outcome. Sources and intake files
shared with v1 remain exact-byte references; v1 is not edited or re-baselined.

```sh
python scripts/source_workflow.py run \
  --manifest research/examples/source-workflow-v2/manifest.json \
  --output data/source_workflow/coverage-v2 \
  --lean-root /path/to/pinned/Lean \
  --dotnet /path/to/dotnet
```

Use the runtime and recovery instructions in the [workflow evidence](TL-003-SOURCE-WORKFLOW.md).
No store, grant or real-data argument is accepted by this command. Only a new
isolated synthetic output directory is used; completed private studies and their
consumed grants remain untouched.

## Frozen scope and checks

The 18-input inventory and expected outcomes were frozen before evaluation.
It retains v1's ten source/record pairs and adds existing Pine SMA(2), normalized
RSI/channel packages, and five deliberately unsupported Pine probes. The RSI and
channel rule objects equal their already implemented constructors; this does not
select, retune or repeat either private study. No external source was acquired.

The authored 540-hour OHLC fixture provides 480 preceding warmup observations and
60 scored hours. Expected signals were specified as explicit truth sets before
running the workflow. Tests independently audit them using rational arithmetic,
prior-window extrema and UTC clocks, then check RSI/channel next-open fills,
complete outcomes, identical semantic/trace hashes and recovery without replay.
The existing dedicated LEAN CI suite includes the new corpus acceptance test.

## Coverage and interpretation

| Measurement | Corpus v1 | Corpus v2 |
| --- | --- | --- |
| Submissions / distinct source byte strings | 10 / 9 | 18 / 17 |
| JSON / Pine / prose submissions | 7 / 2 / 1 | 9 / 8 / 1 |
| Compiled inputs | 6 | 9 |
| Operator structures | 3 | 5 |
| Invalid / unsupported / needs_source_parser | 1 / 2 / 1 | 1 / 7 / 1 |
| Historical jobs | 16 | 22 |
| Completed / duplicate / failed jobs | 10 / 4 / 2 | 16 / 4 / 2 |
| Terminal executable attempts | 12 | 18 |
| Completed strategy/cost LEAN comparisons required | 6 | 12 |

Observed v2 run `data/source_workflow/coverage-v2-02/`: all counts above matched,
and all twelve actual pinned-LEAN comparisons matched. The unchanged command
took 91.55 seconds on WSL/Python 3.12.13/.NET 10.0.401 with the Windows-mounted
checkout, including LEAN build/run checks. One submitted command required zero
per-candidate interventions; manual corpus/trace authoring occurred beforehand.
This is one bounded workload measurement, not a throughput projection.

Two independent Windows executions and the WSL/LEAN execution shared semantic
SHA-256 `320246cd0eb6f78e7e701af8c39ac48e3454cfdc1778e8bb46d0b75b3ee928af`
and all 18 retained full/partial trace hashes. Source-workflow tests passed 13
cases locally, with two actual-LEAN environment skips; the actual v2 CLI run
exercised twelve LEAN comparisons. The full local suite passed 259 tests with 36 environment-dependent skips; the two context tests also passed. Tests audit
4,346 stored source-signal rows, including intentionally repeated inputs; that
row count does not increase the five-structure coverage denominator.

These are coverage denominators, not a ranking of strategy quality. SMA window
variants, duplicate source bytes and tiny sizing do not count as additional rule
structures. The corpus is deliberately balanced to expose known boundaries;
its unsupported-input frequency does not estimate real-world source prevalence.

The useful distinctions are:

- Existing RSI and channel normalized packages pass the workflow; their Pine
  syntax probes are rejected by the current frontend. This is a translation gap,
  not evidence that another historical evaluator is needed. TradingView indicator
  semantics have not been established as equivalent to TideLab's pinned contracts.
- A comment line and a variable alias each cause `unsupported_extra_statement`
  even though the authored SMA intention is unchanged. The strict grammar has a
  syntax usability gap separate from adding indicators.
- Same-close processing is rejected as an unsupported strategy option. This is
  a protected timing boundary, not a syntax nuisance to normalize away.
- Pine EMA, unsupported product capabilities and ambiguous prose remain explicit
  rejections. This slice provides no new engine semantics or interpretation.

A pre-integration byte audit caught checkout-dependent line endings in the reused
SMA(2) record. The final corpus pins its committed LF bytes locally; all 46
manifest file references match Git index blobs. The earlier run remains retained
as `coverage-v2-01`; the corrected corpus was rerun in a new isolated store.

## Review and next action

The runtime, strategy semantics, package contracts and authority boundaries are
unchanged, so the development loop calls for focused self-review of this fixture/
test slice. The PR records exact-head tests, actual runtime evidence, CI and
integration. It must not call the corpus an implementation of new source support.

Recommended next action: a separately bounded, behavior-preserving Pine comment
handling change, retaining original source-byte identities and all timing/order
option rejections. It removes an observed obstruction without deciding new
indicator semantics. Alias support and RSI/channel translation remain separate
choices; these authored probes alone do not establish their priority or correctness.
Keep #3 data rights, #48 execution and optional #21 independent.
