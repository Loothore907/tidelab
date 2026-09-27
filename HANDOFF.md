# TideLab handoff

Updated 2026-09-26 Alaska time. Verified research checkpoint: main `2b8783cbe5b58296638104009557c32d66c573b6`, clean and synchronized, no open PRs; [PR #109](https://github.com/Loothore907/tidelab/pull/109) merged and all three [exact-main CI jobs](https://github.com/Loothore907/tidelab/actions/runs/36284533727) passed. This documentation update follows that checkpoint; resolve current HEAD and recheck live Git/GitHub rather than treating the recorded SHA as forever current.

## Product outcome delivered

The [repeatable source workflow](docs/evidence/TL-003-SOURCE-WORKFLOW.md) connects the existing intake/compiler, conformance, capability checks, synthetic ledger and historical backend through one manifest/command. The authored ten-input corpus covers JSON and the existing Pine subset, three rule structures, malformed/unsupported/prose inputs, duplicates and retained execution failures. Six compiled inputs yield 16 jobs: ten completed, four duplicates, two deliberate below-unit failures; six completed strategy/cost comparisons use pinned LEAN.

This is foundation integration under #95, not another strategy study. Supported additions require source/record/trace/configuration files only. Existing recovery completes artifact metadata without replay; incomplete execution needs explicit abort and never creates a parity pass. General prose/Pine/repository interpretation, private admission and economic evidence remain outside this capability.

## First action next session

Read the repository guidance and the [workflow evidence and reproducible command](docs/evidence/TL-003-SOURCE-WORKFLOW.md). Use one bounded context pickup, then verify live branch, GitHub, reviews and exact-head CI. The implementation PR carries its exact reviewed SHA and integration evidence; the historical checkpoint above is not a claim about a future HEAD.

Recommended next action: extend the corpus through files/configuration to measure actual unsupported-source needs before proposing a separately bounded parser extension. Do not automatically add a strategy study, evaluator, real-data trial or generalized private-admission framework. Preserve all completed studies below.

## Built and reusable

- Source/intake metadata, exact revision/digest and implementation-rights records: `strategy_intake.py`, `pine_source.py`. They do not automatically resolve rights or prose ambiguities.
- Typed versioned packages and shared deterministic closed-bar/next-open replay: `strategy_batch.py`. Existing semantics cover close/SMA/constants/logic, fixed Wilder RSI, prior-window channel bounds and UTC weekday/hour predicates; they are explicit subsets, not arbitrary strategy support.
- Bounded Pine frontend and hand-specified conformance traces: `pine_subset.py`, `scripts/pine_subset_batch.py`. General Pine, repository code and papers remain unsupported unless translated through a separately reviewed contract.
- Synthetic input/outcome ledger: `synthetic_batch_ledger.py`; registered historical jobs, shared costs/benchmarks, metrics, manifests and artifact recovery: `historical_batch.py`, `historical_input.py`, `trial_registry.py`.
- Actual pinned LEAN order/fill/portfolio comparisons: `package_lean_parity.py`, `scripts/package_lean/`, dedicated CI. Engine pin remains `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`. This is a controlled harness, not a production feed or unattended trading system.
- Shared bounded private snapshot/admission helpers exist, with separately frozen RSI/channel/Monday bindings. Their completed studies do not create a general private-plan authorization API.

The previous 1,000-package synthetic check and repeated-template historical workload demonstrate bounded throughput, not diverse external-source coverage. No durable trading opportunity or income capability has been demonstrated. See [CONTEXT_MAP.md](docs/CONTEXT_MAP.md) for exact navigation rather than rereading all evidence.

## Closed private studies: preserve, never repeat

RSI v1, channel v1 and Monday v1 are complete. Their finite batches, accounting audits and independent audits are finished; grants are consumed. Authoritative private artifacts are under `data/research_program/rsi-v1/`, `channel-v1/` and `monday-v1/`. Monday's `closeout.json` binds its report and audit receipts at the checkpoint above. Inspect receipts privately only when necessary; do not publish outcomes or metrics in public documentation.

Preserve `data/research_program/trials.sqlite3`, the original `data/strategy_intake/RSI-BATCH-V1-STORE.json` anchor, every prior row and all retained failures/receipts. Do not initialize a replacement store, renew a grant, invoke old authorize/prepare/run commands, retune, rerun or open later partitions. The next foundation slice uses isolated invented-data stores and has no real-price authority.

The #86 screen, H1 and private low-volatility work remain separately auditable. Do not revive them or open H1/low-volatility untouched partitions as routine continuation.

## Independent boundaries

- **#3 data:** existing historical archives and their prior bounded use are not authority for new acquisition, publication or a timely forward feed. No provider response or current terms check is implied by this handoff. Resolve timely-source rights/coverage/cost separately when needed.
- **#48 execution:** external coherent account/order snapshots, finality, correction reversal and safe unattended operation remain unproved. Existing synthetic recovery/hold evidence is not live authority.
- **#21 model work:** optional, outside this slice. Deterministic computation remains the evaluator.
- No accounts, credentials, orders, deposits, spend, outreach, new data acquisition or public real-data outputs. TideLab-authored work remains Apache-2.0; preserve third-party licenses. Keep engine selection settled unless new blocking evidence warrants reopening it.

The bounded authored source-to-results workflow is implemented. Expand only when its measured coverage gaps justify another bounded slice.
