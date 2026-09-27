# TideLab handoff

Updated 2026-09-26 Alaska time. Verified pickup: main `1aa55bfa4a0973e3706e1848bcaba47b282cf3a3`, clean and synchronized, no open PRs; [PR #112](https://github.com/Loothore907/tidelab/pull/112) merged and all three [exact-main CI jobs](https://github.com/Loothore907/tidelab/actions/runs/36289447068) passed. The bounded comment extension follows that checkpoint; resolve current HEAD and recheck live Git/GitHub instead of treating this recorded SHA as forever current.

## Product outcome delivered

The [repeatable source workflow](docs/evidence/TL-003-SOURCE-WORKFLOW.md) connects the existing intake/compiler, conformance, capability checks, synthetic ledger and historical backend through one manifest/command. The authored ten-input corpus covers JSON and the existing Pine subset, three rule structures, malformed/unsupported/prose inputs, duplicates and retained execution failures. Six compiled inputs yield 16 jobs: ten completed, four duplicates, two deliberate below-unit failures; six completed strategy/cost comparisons use pinned LEAN.

This is foundation integration under #95, not another strategy study. Supported additions require source/record/trace/configuration files only. Existing recovery completes artifact metadata without replay; incomplete execution needs explicit abort and never creates a parity pass. General prose/Pine/repository interpretation, private admission and economic evidence remain outside this capability.

## First action next session

Read the repository guidance and the [workflow evidence and reproducible command](docs/evidence/TL-003-SOURCE-WORKFLOW.md). Use one bounded context pickup, then verify live branch, GitHub, reviews and exact-head CI. The implementation PR carries its exact reviewed SHA and integration evidence; the historical checkpoint above is not a claim about a future HEAD.

The approved [configuration-only corpus extension](docs/evidence/TL-003-SOURCE-COVERAGE-V2.md) now covers 18 inputs and five existing rule structures with the unchanged runtime. Its 22 jobs retain 16 completions, four duplicates and two deliberate failures. Normalized RSI/channel inputs work; authored Pine probes expose translation and strict-syntax gaps.

The [bounded Pine comment extension](docs/evidence/TL-003-PINE-COMMENTS.md) now accepts ordinary full-line comments through an explicit grammar-2 manifest choice, preserving original hashes, legacy grammar-1 outcomes and execution-option rejections. Its six-input corpus yields three compiled inputs, three rejections, six completed jobs and four duplicates; both executed strategy/cost cases match pinned LEAN. It adds syntax coverage, not another rule structure.

The follow-on [#116](https://github.com/Loothore907/tidelab/issues/116) import improvement adds explicit grammar 3 for named SMA expressions, ordinary token spacing, blank lines and inline comments through the existing source workflow. See [operating instructions and preparation limits](docs/evidence/TL-003-SOURCE-WORKFLOW.md#importing-named-sma-expressions-grammar-3) and the implementation PR for review/CI. Original source bytes and grammar-1/2 outcomes are preserved; no strategy semantics, evaluator or private study changes. The formerly rejected alias source now needs no rewriting under grammar 3.

Apply the [development loop](docs/DEVELOPMENT_LOOP.md) to the next observed import bottleneck. Source records, independent expected traces and manifest references still require preparation; do not claim zero-effort onboarding. Broader source formats and indicator translation remain unsupported. Choose further work from measured operator friction rather than automatically adding another parser feature, study or framework.

## Built and reusable

- Source/intake metadata, exact revision/digest and implementation-rights records: `strategy_intake.py`, `pine_source.py`. They do not automatically resolve rights or prose ambiguities.
- Typed versioned packages and shared deterministic closed-bar/next-open replay: `strategy_batch.py`. Existing semantics cover close/SMA/constants/logic, fixed Wilder RSI, prior-window channel bounds and UTC weekday/hour predicates; they are explicit subsets, not arbitrary strategy support.
- Bounded Pine frontend and hand-specified conformance traces: `pine_subset.py`, `scripts/pine_subset_batch.py`. General Pine, repository code and papers remain unsupported unless translated through a separately reviewed contract.
- Synthetic input/outcome ledger: `synthetic_batch_ledger.py`; registered historical jobs, shared costs/benchmarks, metrics, manifests and artifact recovery: `historical_batch.py`, `historical_input.py`, `trial_registry.py`.
- Actual pinned LEAN order/fill/portfolio comparisons: `package_lean_parity.py`, `scripts/package_lean/`, dedicated CI. Engine pin remains `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`. This is a controlled harness, not a production feed or unattended trading system.
- Shared bounded private snapshot/admission helpers exist, with separately frozen RSI/channel/Monday bindings. Their completed studies do not create a general private-plan authorization API.

The previous 1,000-package synthetic check and repeated-template historical workload demonstrate bounded throughput, not diverse external-source coverage. No durable trading opportunity or income capability has been demonstrated. See [CONTEXT_MAP.md](docs/CONTEXT_MAP.md) for exact navigation rather than rereading all evidence.

## Closed private studies: preserve, never repeat

RSI v1, channel v1 and Monday v1 are complete. Their finite batches, accounting audits and independent audits are finished; grants are consumed. Authoritative private artifacts are under `data/research_program/rsi-v1/`, `channel-v1/` and `monday-v1/`. Monday's `closeout.json` binds its report and audit receipts from the completed private-study checkpoint. Inspect receipts privately only when necessary; do not publish outcomes or metrics in public documentation.

Preserve `data/research_program/trials.sqlite3`, the original `data/strategy_intake/RSI-BATCH-V1-STORE.json` anchor, every prior row and all retained failures/receipts. Do not initialize a replacement store, renew a grant, invoke old authorize/prepare/run commands, retune, rerun or open later partitions. The next foundation slice uses isolated invented-data stores and has no real-price authority.

The #86 screen, H1 and private low-volatility work remain separately auditable. Do not revive them or open H1/low-volatility untouched partitions as routine continuation.

## Independent boundaries

- **#3 data:** existing historical archives and their prior bounded use are not authority for new acquisition, publication or a timely forward feed. No provider response or current terms check is implied by this handoff. Resolve timely-source rights/coverage/cost separately when needed.
- **#48 execution:** external coherent account/order snapshots, finality, correction reversal and safe unattended operation remain unproved. Existing synthetic recovery/hold evidence is not live authority.
- **#21 model work:** optional, outside this slice. Deterministic computation remains the evaluator.
- No accounts, credentials, orders, deposits, spend, outreach, new data acquisition or public real-data outputs. TideLab-authored work remains Apache-2.0; preserve third-party licenses. Keep engine selection settled unless new blocking evidence warrants reopening it.

The bounded authored source-to-results workflow is implemented. Expand only when its measured coverage gaps justify another bounded slice.
