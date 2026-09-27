# TL-003 bounded Pine full-line comments

Issue [#95](https://github.com/Loothore907/tidelab/issues/95). Foundation change for the existing source workflow, based on main `1aa55bfa4a0973e3706e1848bcaba47b282cf3a3`. The owner approved the handoff's bounded comment-handling continuation. No strategy rule, source acquisition, evaluator, private admission or real-data trial is added.

## Contract

The default `tidelab-pine-v5-subset-1` remains unchanged. A Pine input in a source workflow manifest can explicitly set `"grammar_version": "tidelab-pine-v5-subset-2"`. The original eight executable/directive lines, literal indentation, options and semantic restrictions still apply. Version 2 additionally accepts ordinary full-line `//` comments, optionally preceded by ASCII spaces or tabs, after the required first `//@version=5` line, between statements or at the end. Comments between an `if` and its body do not change that body's required indentation.

An additional directive/annotation (`//` followed by optional spaces/tabs and `@`) is rejected, including a repeated version directive. Preambles, blank lines, inline/block comments, aliases, other expressions, timing options and order forms remain unsupported. Version 2 rejects non-LF control/Unicode line separators. Both versions require UTF-8 without BOM, LF, a final newline and at most 16 KiB, including comments. No Pine is executed and there is no general TradingView compatibility claim.

Hashing and source-record validation occur on the complete original bytes before comment removal. Package identity still derives from raw source and exact intake-record identity. The manifest and compilation outcome retain an explicit grammar choice. Omitted choices preserve all v1/v2 historical corpus outcomes; unknown choices have a named unsupported outcome and no jobs. Non-Pine inputs cannot select a Pine grammar. The older `pine_subset_batch.py` CLI remains pinned to grammar 1; the integrated source workflow is the consumer of grammar 2.

## Frozen corpus and acceptance

[`pine-comments-v2/manifest.json`](../../research/examples/pine-comments-v2/manifest.json) contains six source inputs:

- The exact formerly rejected comment source from the v2 coverage corpus, with a new specified record and expected trace.
- Its uncommented original, selecting the default grammar.
- The same rule with comments between all statements, including indented comments and a trailing comment.
- A directive, changed same-close option and inline-comment probe, each rejected with no jobs.

The two accepted commented sources and original have three distinct source/package identities but one rule structure. Existing semantic duplicate accounting reserves only the first strategy's two cost jobs; four equivalent jobs remain linked as duplicates. Four common cash/passive benchmark jobs complete. Total: three compiled, three unsupported; ten ordered jobs, six completed and four duplicates, six terminal attempts. There are no execution failures in this corpus; the unchanged source-workflow-v1/v2 corpora retain their deliberate failures. This extends syntax coverage, not rule coverage.

Expected traces reuse the existing independent SMA(3) truth table, rebound to each exact source. Tests independently check every row by rational arithmetic, verify raw comment mutation invalidates identity, compare deterministic results across runs, and recover retained artifacts with compilation/replay disabled. Tests also exercise every comment boundary and execution-option/order/indicator rejection. Existing interruption and failure recovery tests remain required.

## Reproduce

From the repository root with the pinned LEAN checkout and .NET available:

```powershell
.venv/Scripts/python.exe scripts/source_workflow.py run --manifest research/examples/pine-comments-v2/manifest.json --output data/source_workflow/pine-comments-new --lean-root <pinned-LEAN-directory> --dotnet <dotnet-executable>
.venv/Scripts/python.exe scripts/source_workflow.py recover --output data/source_workflow/pine-comments-new
```

Use a new output directory each time. LEAN pin: `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`; local measured runtime used WSL Python 3.12.13 and .NET 10.0.401. The six-input command completed in **23.91 seconds**, one command and zero per-candidate manual steps after submission. Both executed strategy/cost comparisons matched actual pinned LEAN orders/fills/portfolio and historical traces. Semantic digest: `9cba7979021d917c0c07d2d065ee771b64ee3f1d66fa5320b33db0f911b4bbf9`. Runtime is environment-specific, not a throughput guarantee.

Local evidence stays in ignored `data/source_workflow/pine-comments-01/`; committed inputs contain invented data only. Review and exact-head CI are recorded in the implementation PR. Existing RSI/channel/Monday studies, consumed grants and private stores are untouched. Keep #3, #48 and #21 independent.

Next action: assess a bounded alias-reference extension against the retained alias rejection probe, with an explicit grammar and independent conformance acceptance before implementation. This document does not authorize that extension.
