# TideLab development loop

Owner: [issue #95](https://github.com/Loothore907/tidelab/issues/95). Adopted from the owner's 2026-09-26 request to prevent drift and make the development loop usable across agents and models. This is the working agreement; `HANDOFF.md` carries the current slice. It does not authorize a new strategy, real-data trial, account operation, purchase or merge.

## Product anchor

TideLab should ingest supported strategy sources and evaluate approved candidates through a reusable, deterministic research workflow. The long-term economic question is whether a candidate survives realistic costs and subsequent forward evidence. Infrastructure is useful when it advances that workflow or removes a demonstrated blocker. A bespoke study, more passing tests, or a larger package count does not by itself advance the platform.

The owner's "fish wheel" goal is a continuing flow of ideas through a repeatable filter. The working standard is **how much effort the next idea takes from source to an honest result**. Distinguish unreadable/unsupported/ambiguous input from an evaluated research rejection and from a candidate nominated for further evaluation. Do not count parser rejection as evidence against a strategy, or a nomination as a proven edge.

The agent owns technical judgment: challenge a proposed approach when evidence suggests a simpler or better route, name assumptions, and explain consequences in plain language. The owner decides goals, tradeoffs, candidate/trial scope and material authority; the owner should not have to detect semantic or architectural errors unaided. These rules apply regardless of model. Model choice is not a substitute for evidence or review.

An approved bounded sequence carries through its named implementation, tests, required review, CI, integration and any explicitly included research stages. Separate candidate/data/trial boundaries must be satisfied by the scope of that approval; they do not require repeatedly requesting the same approval at each stage. A later handoff preserves the scope and consumed stages. Ask only for missing material authority or a material change; a failed gate stops dependent work and is never bypassed.

## 1. Make one brief before implementation

After one bounded repository/remote pickup, write the brief in the session and carry it into the issue or PR. Reuse it across turns; do not create another planning document per session. Include only the relevant facts:

- **Outcome and classification:** what a user or downstream caller can do afterward; foundation, selected strategy implementation, research evaluation, defect repair, or documentation. For supporting work, name the next consumer and the exact blocker it removes.
- **Scope and reuse:** owning issue, branch/base, affected interfaces, existing code to reuse, explicit exclusions. Explain why any new abstraction or evaluator is needed.
- **Acceptance:** a reproducible command or demonstration, observable expected behavior, at least one relevant failure case for behavioral changes, and what would falsify the approach. Declare synthetic versus real inputs, supported semantics, and the limits of the resulting claim. For documentation, use a consistency/link review rather than invented behavioral tests.
- **Effort:** for import/workflow changes, name one representative new input inside the declared supported contract and the preparation step being removed or simplified. Record the existing baseline or mark it unmeasured; other work should name its correctness benefit or concrete downstream blocker without inventing an import metric.
- **Authority and integration:** existing approval and its limits; intended commit/push/PR/merge actions; required local checks, remote checks, and review. Obtain only missing material authority, after preparing a concrete proposal.

Choose acceptance before implementation. If a technical discovery requires changing it, preserve the original, explain the discrepancy, and record the revision before continuing. Never quietly weaken an expected result to match the code. Reconfirm with the owner only when the revision materially changes the approved outcome, scope or risk.

## 2. Finish a useful path

Keep one active outcome. Complete a reviewable slice of the source-to-result path before opening adjacent work. Normal repairs, tests, documentation and Git integration belong to that slice; unrelated cleanup does not. Classify inherited debt as blocking or non-blocking and record the disposition without recursively cleaning the repository.

Batch related usability changes into that outcome instead of creating a new proposal, handoff and approval cycle for each syntax detail. Keep commits and reviews coherent; batching does not relax semantic review or authorize new trading rules. Choose the smallest useful supported language from observed inputs, state its limits, and avoid waiting for a universal parser. A new supported strategy should enter through source/record/configuration files without per-strategy runtime code.

Before adding a parser feature, adapter, replay loop, ledger or abstraction, identify its concrete consumer and compare reuse with extension. New candidates should normally supply packages and source records to shared evaluation code. A specialized runner needs a stated semantic reason and an integration or retirement disposition. Preserve frozen studies and their reproducibility; do not rewrite their history to consolidate code.

For a probe, name the uncertainty, bounded experiment, pass/fail decision, and where successful code will be integrated. A failed probe is a valid result. Do not automatically turn a failed probe into a larger infrastructure project. If a second consecutive supporting-only slice is proposed without demonstrating the consuming workflow, review the sequence before coding: combine work, reduce scope, or explain the concrete dependency. This is a reasoning checkpoint, not an automatic permission request.

Stop expanding when the brief's acceptance is met. Put additional ideas in the owning issue; they are not implicitly the next task. A blocked forward feed or external broker does not block independently authorized synthetic or historical work unless the brief demonstrates that dependency.

## 3. Interrupt drift when it starts

| Observable trigger | Required response |
| --- | --- |
| Foundation work starts choosing entry/exit rules, thresholds or market rankings | Apply the strategy-intake checkpoint before rule code; name the candidate and existing authority or prepare a selection proposal. |
| Another evaluator, accounting path, frontend or generic framework appears | Explain why the existing path cannot serve the approved outcome and identify the consumer. Prefer integration; obtain a scope decision if this materially changes the brief. |
| A test requires silently changing timing, fees, rounding, sizing or the expected trace | Treat it as a semantic discrepancy. Preserve the failure and resolve the contract before claiming parity. |
| The slice depends on a new source, account, spend, real-data partition or execution mode | Finish independent authorized preparation, then obtain the specific missing authority before the dependent action. |
| An established engine/architecture choice is being reopened | Cite the new blocking evidence, available workaround and cost of change. Existing limitations already accepted in the decision are not new evidence. |
| The PR proves a narrower capability than its title or brief claims | Narrow the claim explicitly and report unmet acceptance. Do not relabel a contract test as product completion. |
| A one-command claim excludes source preparation, expected traces or agent intervention | Include those steps in the effort comparison; remove or explicitly retain the bottleneck. |
| Another document or supporting slice is proposed without a new user capability or durable decision | Update/link the existing home, combine the consuming work, or explain the dependency in the current brief; do not start another planning cycle. |

Ask the owner with a recommendation, evidence, practical consequence and the exact decision needed. Do not transfer an unexplained technical choice to them. Existing authorization persists within its bounds; elapsed time, successful CI and a handoff recommendation do not expand it.

## 4. Review the result against the brief

The implementer first reviews the exact diff for product alignment, semantic correctness, duplicated responsibilities and unsupported claims. Run the checks that exercise the affected behavior, including the selected runtime where applicable. A test should distinguish correct behavior from a plausible wrong implementation, such as a same-close fill instead of the next open. Include independently specified expected traces or invariants; two implementations agreeing with each other can share a mistake.

For import/workflow work, the reviewer must answer from the demonstration: can another input within the supported contract use the shared path without runtime edits; what manual preparation remains; and are unsupported inputs clearly separated from tested failures? Include varied representative inputs and a relevant rejection case, not only the author's preferred template. If effort did not improve, say so and justify the correctness/coverage tradeoff against the original brief. Missing evidence means the efficiency claim is unverified, even when CI passes.

Before merge, changes to shared strategy semantics, execution/accounting, strategy-package contracts, or research/authority boundaries require a distinct reviewer: a human or a separately tasked reviewer with access to the brief, exact diff/head and evidence. The reviewer must inspect those sources rather than endorse the author's summary. Review both whether this is the right work and whether it works. Record reviewer/method, reviewed SHA, findings and their disposition. Do not call the author's second pass independent review. Relevant follow-up changes require review of the new head; if the reviewer is unavailable, finish authorized preparation and leave a draft with the owning issue and next action. These rules do not authorize agent delegation or messaging another chat without the required user authority.

Routine documentation and fixes outside those boundaries use focused self-review. A higher-capability reviewer can be reserved for architectural/semantic boundaries and drift triggers rather than every edit. The evidence requirements remain the same regardless of which model implements or reviews the work.

## 5. Report capability, not activity

Close out with the outcome demonstrated versus the brief, evidence and its limits, review/findings, exact head and CI, integration state, remaining changes, and one recommended next action. A correct partial slice can be integrated when authorized, but must not be called a completed platform. Preserve failures and unmet acceptance in the owning issue or PR.

Use measures matched to the claim:

| Claim | Relevant evidence |
| --- | --- |
| Source support | Named representative corpus and supported/unsupported outcomes; manually specified trace agreement. |
| Scale | Fixed workload, bars/markets/strategy diversity, runtime and memory; identify repeated-template variants. |
| Research usefulness | Before/after preparation and execution effort per new input, reproducibility, complete trial counts, consistent costs and search-aware evaluation. |
| Engine parity | Signal and fill timestamps, quantities, fees, cash and holdings under the same identified inputs and policy. |
| Operational readiness | Actual supported runtime and failure/recovery route, not only a mock or fixture. |

Do not gather all metrics for every slice. Select the measure that tests the current claim. In particular, the existing 1,000 sizing variants on twelve invented bars establish batch-path behavior, not broad strategy coverage or historical throughput; the eight-line Pine frontend establishes a narrow translation contract, not general TradingView compatibility.

For import/workflow claims, put a compact before/after comparison in the existing PR: manual steps, hand-authored files (including records and expected traces), commands/interventions, and runtime code edits required per new supported input. Separate one-time environment setup, per-input preparation and batch execution. Record active preparation time and machine runtime when measured; use "unmeasured" otherwise and never infer human time from runtime. Use existing artifacts for observed counts. No new telemetry system or benchmark suite is required just to report these measures.

Keep one authoritative home for each fact: this document for the loop, decision documents for accepted architecture, the owning issue/PR for scope and review, versioned artifacts for evidence, and `HANDOFF.md` for the current continuation. Default documentation for a routine slice is the PR plus an update to existing operating instructions only when behavior changes. Create a separate document only for a durable decision, required rights/research record, or reproducibility information that has no suitable existing home; explain that need in the PR. Generate run identities, counts, failures and traces through existing tools instead of transcribing logs. Keep private evidence private. Update the handoff only when continuation changes; it should identify remaining work and link evidence, not retell the session. Do not open a cleanup-only PR merely to restate ordinary post-merge facts.

## Enforcement and limits

`AGENTS.md` routes agents here, and the PR template makes alignment/evidence visible during review. Both are guidance; neither proves compliance. Validators check structure and CI checks executable assertions, not product judgment, source rights or real user authority. A completed checklist is not review evidence.

At the 2026-09-26 refresh, GitHub required the `test` check with admin enforcement and zero required approving reviews. CI also ran `engine-bakeoff` and actual `lean-package-parity`; those additional jobs were not listed as required branch checks. The distinct-review and effort-review rules are process requirements, not GitHub enforcement. No branch protection or CI settings change here. Recheck live settings when integrating and inspect all relevant exact-head jobs. Tests can enforce supported-input behavior and rejection semantics; neither green CI nor a completed PR template proves low operator effort or model compliance. Assess that from the next actual delivery, record a concrete deviation in its PR, and fix the violated behavior without automatically adding another policy layer.
