# TideLab handoff

Updated 2026-09-26 Alaska time. Verified research checkpoint: main `2b8783cbe5b58296638104009557c32d66c573b6`, clean and synchronized, no open PRs; [PR #109](https://github.com/Loothore907/tidelab/pull/109) merged and all three [exact-main CI jobs](https://github.com/Loothore907/tidelab/actions/runs/36284533727) passed. This documentation update follows that checkpoint; resolve current HEAD and recheck live Git/GitHub rather than treating the recorded SHA as forever current.

## Product outcome and current gap

TideLab's goal is a repeatable, automated environment that ingests and tests multiple strategies from multiple sources. Its shared evaluation backend is working; multi-source ingestion and orchestration remain limited. Prepared packages can run through common costs, execution and accounting, but interpreting external sources, assembling plans and admitting private studies still requires too much manual/candidate-specific work. More individually engineered studies are not the next platform milestone.

The authoritative next work brief is [Next outcome: repeatable source-to-results workflow](docs/ROADMAP.md#next-outcome-repeatable-source-to-results-workflow), owned by [#95](https://github.com/Loothore907/tidelab/issues/95). Deliver one manifest/command from a fixed corpus of existing supported source formats and intake records to complete synthetic historical batch results, with no per-strategy Python edits for supported inputs. Reuse existing components; no new backtester, strategy or generalized paper parser.

## First action next session

Read AGENTS.md, this handoff, README.md, docs/ROADMAP.md and docs/DEVELOPMENT_LOOP.md. Use the repo-local `tidelab-context` skill for one bounded pickup, then verify working changes, fresh remote refs, open issues/PRs, review findings and exact-head CI. Resolve inherited integration debt without disturbing unrelated work.

Proceed with the roadmap's bounded foundation integration on a focused #95 branch from current main. Freeze a small authored corpus using normalized JSON and the existing Pine subset, with multiple rule structures and explicit invalid/unsupported/ambiguous/duplicate cases. Connect compilation and plan assembly to the existing historical backend, preserve source-to-result identities and all outcomes, and demonstrate one-command execution, reproducibility, existing recovery and measured manual effort on invented history.

The owner agreed this platform direction and wants the bounded sequence carried through rather than repeated step approvals. Finish concrete implementation, meaningful tests, any required distinct review, CI and authorized integration together. Do not ask again for routine steps already in that scope. Stop for a failed gate or material scope/risk/authority change. The current session updates documentation only; this handoff does not claim the new workflow is implemented.

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

One active outcome: the repeatable supported-source-to-results workflow. Expand only when its measured gaps justify another bounded slice.
