# Source coverage corpus v2

This is a configuration-only extension of the [v1 corpus](../source-workflow-v1/README.md)
under issue #95. It reuses all ten v1 source/record pairs unchanged, replaces their
conformance history/traces for this corpus, and adds eight authored input cases.
No runtime, compiler grammar, strategy rule or private-study configuration changes.
`manifest.json` freezes every source, record, trace and history digest;
`expected.json` fixes expected accounting and rejection reasons before execution.
The reused SMA(2) intake record is copied from its committed LF bytes into this
directory's LF-pinned fixtures; its canonical contents are unchanged. This avoids
binding the manifest to Windows checkout line-ending conversion in the older folder.

## Composition

| Inputs | Format | Expected outcome |
| --- | --- | --- |
| Original v1 ten submissions | Seven JSON, two Pine, one prose | Six compiled, one malformed, two unsupported, one needs_source_parser |
| Existing SMA(2) fixture | Pine | Compiled; parameter variation, not a new operator structure |
| Existing fixed RSI14 and 480/240 channel rules | Two normalized JSON | Compiled; two additional existing operator structures |
| Authored RSI and channel syntax probes | Two Pine | unsupported_signal_expression |
| Existing SMA with a variable alias or a comment line | Two Pine | unsupported_extra_statement |
| Existing SMA with process_orders_on_close=true | Pine | unsupported_strategy_options |

Totals: 18 submissions (9 JSON, 8 Pine, 1 prose), 17 distinct source byte strings;
9 compile, 1 is malformed, 7 are unsupported and 1 needs a source parser. The
compiled inputs contain five operator structures: SMA, Boolean/lag, calendar,
RSI and prior-window channel. SMA(2), tiny sizing and duplicate inputs do not
increase structural coverage. Unsupported Pine files are parser probes only;
no TradingView execution, conformance or cross-platform equivalence is asserted.
Their intake records remain captured with unresolved interpretation.

## Independent history and truth tables

540 invented hourly OHLC bars begin 2026-01-04 at 20:00 UTC. Bars 0–479 are
`open=close=100, high=101, low=99`. Bars 480–487 are:

| Index | Open | Close | High | Low |
| --- | --- | --- | --- | --- |
| 480 | 100 | 110 | 120 | 99 |
| 481 | 110 | 115 | 115 | 100 |
| 482 | 115 | 90 | 115 | 80 |
| 483 | 90 | 79 | 90 | 79 |
| 484 | 79 | 100 | 100 | 79 |
| 485 | 100 | 200 | 201 | 99 |
| 486 | 200 | 50 | 200 | 50 |
| 487 | 50 | 100 | 100 | 50 |

Bars 488–539 return to the original flat OHLC values. Scoring begins at 480;
the preceding 480 observations satisfy the existing channel contract. Signal
conformance also checks preceding observations, but they cannot submit trades.
Bar 539 has no final signal. The independently specified true-index sets are:

| Structure | First evaluated index | Entry true | Exit true |
| --- | --- | --- | --- |
| SMA(3) | 2 | 480, 481, 484, 485, 488 | 482, 483, 486, 487 |
| SMA(2) | 1 | 480, 481, 484, 485, 487 | 482, 483, 486 |
| Boolean/lag | 2 | 480, 481, 484, 485 | 2–479, 482, 483, 486–538 |
| Calendar | 0 | 3, 171, 339, 507 | 27, 195, 363, 531 |
| RSI14 | 14 | 483 | 14–481, 485 |
| Channel | 480 | 480, 485 | 482, 483, 486 |

All unspecified predicates are false through index 538. The test audits these
stored expectations using rational arithmetic, direct prior-window extrema and
UTC arithmetic without calling the package evaluator. Flat zero-loss RSI is 100
under the existing pinned-LEAN contract. After the authored changes, RSI falls
below 30 at 483 and rises above 70 at 485. Channel entry at 480 uses prior high
101, not that bar's current wick of 120; that wick then prevents entry at 481.

RSI fills are independently expected at indices 484 and 486. Channel fills occur
at 481, 483, 486 and 487. These next-open expectations detect timing and prior-
window mistakes; no performance interpretation or new hypothesis is involved.

## Expected workload and boundaries

Nine compiled submissions times baseline/stress costs plus four shared cash/
passive benchmarks yield 22 jobs: 16 complete, 4 duplicate and 2 retain the tiny-
allocation failure. Eighteen attempts are terminal. Twelve completed strategy/
cost cases must match pinned LEAN. Every rejected input retains a reason and zero
jobs. The existing reporting, registry and recovery code serve this corpus as-is.

Run the unchanged `scripts/source_workflow.py run` command with this manifest and
a new isolated `data/source_workflow/` output. All prior private studies, grants,
stores and v1 artifacts remain untouched. Measured results and the next parser
recommendation belong in [the coverage evidence](../../../docs/evidence/TL-003-SOURCE-COVERAGE-V2.md).
