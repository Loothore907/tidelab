# TL-003 shared historical batch backend contract

Owner: [issue #95](https://github.com/Loothore907/tidelab/issues/95). Date: 2026-09-26. Classification: foundation specification. The owner approved specifying the next shared backend after [PR #101](https://github.com/Loothore907/tidelab/pull/101). This document defines the next implementation; it does not claim that implementation exists or authorize external candidate selection or a real-data experiment.

## Outcome and implementation brief

One offline command will evaluate a frozen list of normalized packages against a declared hourly history, using common costs and complete trial accounting. Its first acceptance uses only TideLab-authored synthetic history stored in the existing market-event SQLite schema. It must exercise the whole plan-to-results path without per-strategy code, model calls, network access or an operator interpreting each result.

Use `main` after merged package parity (`4af818f1b11b0bbb19b2fa37cca09a558a09f5ad`) as the base, a focused `codex/95-...` branch, and the [development loop](../DEVELOPMENT_LOOP.md). This specification's acceptance is source/interface consistency, explicit failure and authority boundaries, and distinct review before gated integration. The next implementation's acceptance is below. No new parser, engine selection, broker integration, real archive read or frozen-study migration belongs to either slice.

## Reuse and ownership

| Responsibility | Existing source and intended change |
| --- | --- |
| Rules and source binding | Reuse `src/tidelab/strategy_batch.py` package parsing and typed expressions. Real intake still requires independently verified implementation selection and rights; a validator is not that verification. |
| Screening replay | Extract the existing `evaluate_synthetic` loop into a source-neutral internal replay function with explicit costs and scoring boundaries. Preserve its synthetic wrapper and outputs. Do not copy the loop from `candidate_screen.py` or create a third evaluator. |
| Execution comparison | Keep `package_lean_parity.py` and `scripts/package_lean/` as the independent pinned LEAN comparison. Extend both only for the cost/partition inputs needed here. Python is the bounded screening implementation; LEAN remains the selected engine reference. |
| Trial identity and audit | Reuse `build_experiment_identity` and `TrialRegistry`. Add narrowly scoped batch admissions in the same research registry, with transactional reservation and links to existing trial attempts. The separate synthetic CLI ledger does not become the research registry. |
| Historical input | Extract a parameterized read-only hourly reader using the validation/provenance rules in `candidate_screen.read_bars`. Its hardcoded market, family, dates and 720-hour warmup cannot be reused as the new API. Preserve all old study entrypoints and identities. |
| Results | Derive metrics from the common replay trace. Retain inputs, failures and output digests locally; source-specific runners remain frozen historical evidence, not templates for new studies. |

No distributed scheduler, database service, plug-in framework or automatic strategy generator is needed. Start single-process and serial. Read and validate an authorized partition once per market, then reuse its immutable bars across jobs. Stream each trace to its own artifact; do not retain every job's trace in RAM. Record wall time and peak memory before proposing parallelism or feature caching.

## Frozen input contract

The proposed `historical_batch.py` entrypoint accepts a plan, a local snapshot descriptor, a registry and a new output directory. These are planned interfaces, not runnable commands today. The first implementation accepts only synthetic plans and synthetic data; third-party mode must return `real_data_not_enabled` before opening price payloads.

The immutable plan binds:

- schema/version, experiment family and generation, parent experiment if any, phase, owning issue and exact authority reference;
- exact package bytes and intake-record versions/digests; a finite ordered list of jobs, each selecting a package, market and cost scenario; no implicit parameter expansion;
- ordered market list, snapshot descriptor/hash, UTC interval, and disjoint development/validation/untouched intervals expressed as half-open **bar-start** ranges `[start, end)`;
- initial cash, fee/adverse rates, quantity unit and supported product rules; baseline and stress policies are separate declared scenarios, shared across every comparable job;
- a finite search budget, comparison benchmark, metrics and selection criteria; synthetic demonstrations use no profitability pass threshold;
- maximum bars/jobs, output retention policy and exact code/runtime identity. A real trial must use reviewed, integrated code with successful exact-head CI.

The descriptor names source/venue/instrument, interval, data kind, provenance and rights reference, and a pre-existing digest for each permitted partition including its declared warmup. Paths remain private local configuration. The digest identifies a stable exported snapshot, not a mutable SQLite pathname. Verify the requested rows under one read transaction against that digest after reservation; any mismatch fails the attempt. A third-party snapshot without a previously authorized creation/verification receipt cannot be invented by scanning unapproved prices during preflight. Snapshot preparation is a separate authorized operation and records which intervals it accessed.

Freeze raw plan, package, record, cost and descriptor bytes before execution. Hash the evaluated canonical configuration and record its relationship to those raw bytes. `configuration.sha256` binds the whole plan plus selected job, scoring/warmup and all policies; `data.sha256` binds the partition snapshot; `cost.sha256` binds the chosen policy. Keep `trial_id`, sequence and origin in the existing identity. Distinguish an immutable planned trial from an execution attempt; do not use a random attempt ID as the only experiment identity.

## Admission and complete accounting

1. Metadata-only preflight checks source/authority references, intake state, supported capabilities, declared snapshot receipt, phase eligibility and budget. No SQL payload read, chart or metric computation occurs here. Missing authority, snapshot identity or an unsupported product fails closed.
2. In one `BEGIN IMMEDIATE` transaction, reserve the batch and its entire ordered job inventory before any prices are read. Store raw input digests even for malformed/unsupported packages. Enforce a unique experiment-generation/phase reservation and a single active writer. Concurrent launches must yield one admitted batch. This needs an additive registry extension: current `TrialRegistry.start` reserves one attempt and cannot atomically admit a batch.
3. Preserve one admission outcome per planned job: `invalid`, `unsupported`, `duplicate`, `blocked` or `admitted`, with a stable reason code. Retain duplicate entries and their original job references. Budget admission counts every planned variant; report both submitted and distinct configurations. Cost scenarios, markets, benchmarks and repeated execution attempts have separate explicit counts so none disappears or masquerades as an independent strategy.
4. For each admitted executable trial, append its existing `TrialRegistry.start` record **before** reading its partition. The batch reservation covers not-yet-started jobs. Use the predeclared data digest, then verify actual rows against it. On failure, preserve the failed attempt and block affected jobs; never fill gaps or silently shorten the common interval.
5. Write artifacts exclusively, flush them and atomically finalize a manifest binding every retained file. Only then append `TrialRegistry.finish` with its manifest digest. Batch completion requires a terminal inventory disposition for every job. Registry/artifact disagreement is an explicit incomplete state, not success.

Existing registry protections are limited: validation uniqueness includes the whole identity (including trial identifiers), and untouched uniqueness uses strategy ID/version. Renaming or changing those fields is not permission to open a holdout again. The added batch gate binds phase access to the frozen experiment family/generation and snapshot intervals; prior exposure is carried into new generations. It must not infer that changed bytes, new names or a new registry path restore untouched status. Local SQLite guards are audit/control mechanisms, not tamper-proof proof of authority or universal detection of prior exposure.

For the first implementation, only the synthetic development phase runs. Synthetic tests exercise rejection of later phases and repeated admission. A later real-data enablement must define and review the owner-authorized candidate set, finite budget, prior-exposure record and explicit phase decisions. Do not implement a permissive approval Boolean or automatically advance a ranked winner into validation.

## Replay, partition and metric semantics

Retain [package parity's timing/accounting contract](TL-003-PACKAGE-LEAN-PARITY.md): hourly spot long/cash, supported v1 expression subset, closed-bar predicates, cash budget at signal close, quantity at next open, adverse price plus fee, unit floor, no pyramiding/rebalance, no terminal forced liquidation. Each package/market/scenario starts an independent cash account. This is not a combined multi-asset portfolio, realistic liquidity model or deployable strategy simulator.

The initial supported bound stays at 10,000 total bars including warmup per job, with the existing eight-place/1e9 numeric bounds. Reject longer requests; never truncate. Costs become explicit inputs to the same loop and LEAN comparator, with validated finite nonnegative rates below one, positive starting cash and positive decimal quantity unit within the supported precision. Test decimal-domain limits and numerical overflow. Do not assert that all real venue minimums or fee tiers fit these parameters. Unsupported requirements remain named outcomes.

For a score range `[S, E)`, load exactly the declared contiguous warmup preceding S and scored bars with starts S through E minus one hour. Warmup length is at least the package's computed requirement. Warmup updates indicators only: no orders, holdings, equity observations or scored returns. Start flat at S; first possible decision is at the close of the bar starting S and first possible fill is the following scored open. The last scored close is valued at E; no signal there and no open at E is read. Close and next open may share a timestamp but retain ordered event phases. Do not carry positions or pending orders between partitions. That limitation is part of the experiment, not invisible leakage prevention.

For initial acceptance, report net return `(final_equity / initial_cash) - 1`, maximum close-marked drawdown including initial cash, fill and completed round-trip counts, total fees, turnover (sum of absolute fill notionals / initial cash), and the fraction of scored closes with holdings. Report open terminal inventory separately. These are descriptive scenario metrics, not expectancy or income evidence; no-trade and insufficient-trade outcomes are valid.

Cash is an explicit zero-return benchmark. The passive benchmark buys at the open of S with the plan's declared allocation and the same costs/unit, then marks at the same final close; record its earlier entry opportunity relative to the strategy. A stress policy repeats both strategy and benchmark under its declared costs. Benchmark artifacts are separate linked jobs and cannot be silently substituted for a same-risk portfolio. Stable job order controls presentation; no top-k filtering, winner promotion, p-values or profitability verdict is part of the first backend. Later research review must add protocol-required uncertainty, dependence/search adjustment and sensitivity before making an edge claim.

## Interruption and recovery

An interrupted batch remains open with its original inventory, reservations and partial artifacts. Default rerun refuses it. A recovery command may verify an already finalized artifact manifest and finish missing metadata without executing prices again, using the recorded original terms. Otherwise explicitly append an aborted disposition for affected attempts/jobs, preserving all partial files. No in-place result overwrite or automatic retry is allowed. A new development attempt needs a linked retry admission and consumes an attempt count; a failed/aborted validation or untouched launch never automatically restores phase access. Do not release a reservation because of elapsed time alone.

## Next implementation acceptance

The next slice implements this full synthetic development path, not another specification-only slice. Its synthetic SQLite fixture and plan contain at least two markets, two materially different supported packages, baseline/stress and cash/passive comparisons, plus malformed, unsupported and duplicate inputs. No real archive or external strategy is needed.

| Demonstration | Required observation |
| --- | --- |
| One command, complete inventory | Every planned job has a stable status and input identity; valid jobs share declared data/cost policies and need no strategy-specific source edits. |
| Independent arithmetic and partition cases | Hand-calculated gap entry/exit, fees, warmup, final open position and no-trade metrics; changing pre-S prices cannot create a warmup fill; rows at/after E are never requested. |
| Actual pinned LEAN comparison | Both supported packages match signals/fills/cash/holdings over the same score range under baseline and stress, using LEAN order/portfolio processing. Preserve synthetic-wrapper regressions and existing comparison tolerance. |
| Fail closed | Missing authority or third-party mode opens no price payload; duplicate/gap/changed digest, out-of-domain cost/product or over-limit input has a retained failure. |
| Crash/concurrency | Kill after reservation, after trial start and after artifact finalize; recovery never replays a completed result. Concurrent identical admission yields one winner and accounts for the other request. |
| Scale claim bounded by evidence | Run a fixed synthetic workload of 100 distinct packages x two markets x two cost scenarios over 2,000 bars per market, plus declared benchmarks. Report elapsed time, peak memory, complete counts and replay determinism; no arbitrary speed target or claim of source diversity. |

Falsification: bespoke strategy code, a second research ledger, reading prices before admission, changing partition semantics to get parity, hiding failed jobs, or needing real data to demonstrate the backend means this brief is unmet. Keep any discrepancy and resolve it openly before expanding scope.

Run focused backend/registry and actual LEAN tests, existing regressions affected by the extraction, and context checks. Obtain distinct product/correctness review at the final head, all remote CI jobs, gated merge within authority, and exact-main CI verification. Close out with demonstrated capability and remaining limits. Subsequent real use requires its own concrete experiment proposal and authorization; this contract supplies neither a selected dataset snapshot nor a research budget.
