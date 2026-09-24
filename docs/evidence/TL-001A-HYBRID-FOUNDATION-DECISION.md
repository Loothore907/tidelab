# TL-001A hybrid foundation: portable evidence and ownership estimate

Status: selection review for [issue #2](https://github.com/Loothore907/tidelab/issues/2), 2026-09-24. LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` and NautilusTrader `2.0.0rc5` remain candidates. No engine, data source, account, or live mode is adopted by this document. TL-001B remains independent.

## Thesis and scope

The working thesis is that TideLab can use an established engine for replay, scheduling/dispatch, portfolio and public brokerage/fill interfaces while keeping data access, strategy and risk policy, conservative execution assumptions, authoritative local paper reports, and research records replaceable. Its value claim is **honest, repeatable evidence of net strategy behavior** across candidates and later asset classes, not the ability to run a backtest. The thesis fails if a candidate needs a private engine fork, TideLab must recreate general matching or portfolio accounting, or the full integration/maintenance cost is unreasonable relative to research value. Even a good engine cannot establish profitable expectancy or lawful research-data access.

The initial selection covers synthetic historical replay and bounded local forward paper only. A later external broker, real-money pilot, second product class, and strategy-performance claim each require separate evidence and authority. The [working threshold](TL-001A-CONSERVATIVE-PAPER-FILL.md) is the selection test.

## Portable experiment identity checkpoint

`src/tidelab/experiment_identity.py` exports a versioned, engine-independent identity from exactly six sections: pinned engine name/version/source revision; TideLab repository/revision; configuration ID and SHA-256; data source/revision/SHA-256/kind/rights reference; cost policy ID/revision/SHA-256; and strategy/trial ID, sequence, origin and parent. A canonical JSON digest changes if any declared value changes. An export creates a new file and refuses overwrite. The format contains no engine object, raw input, performance result, local path, credential, or unrestricted metadata field. The tests create the same format for LEAN and NautilusTrader, verify changed engine/cost/trial identities, and deny public export for a third-party or unverified synthetic source.

This is an **identity/export seam**, not the TL-003 append-only experiment registry. The caller must hash the actual permitted files, supply truthful rights evidence, preserve every trial (including failures), and keep restricted inputs/results local. A `public_synthetic` switch only enforces the declared TideLab-authored synthetic case; it cannot validate authorship or grant publication rights. Real-data public artifacts still require TL-001B review. Hashes of small or restricted inputs may themselves be sensitive, so a private manifest is the default until that review.

## Responsibility and planning estimate

These are planning ranges for one *synthetic*, single-writer TL-002 historical/forward paper integration by one engineer familiar with the existing probes. They are estimates, **not measured implementation time**. They exclude provider rights work, real data acquisition, external broker guarantees, multi-venue coverage, deployment, and strategy evaluation. A five-day engineering week is assumed; re-estimate after the first integrated slice.

| Work package | TideLab-owned deliverable | LEAN estimate | NautilusTrader estimate / uncertainty |
| --- | --- | ---: | --- |
| Common policy and evidence | Frozen strategy/risk boundary, product/cost policy, portable identity and trial recording | 10-17 days | 10-17 days |
| Data/clock and engine bridge | One synthetic historical and managed-forward route, parity and decision records | 5-8 days | 4-7 days if a backed external-data route exists |
| Paper authority and recovery | Stable intent/execution IDs, durable revisions/corrections, ledger/account join, conditional submission and fail-closed restart | 12-20 days | 12-20 days **plus** the unresolved backed external Python client path |
| Verification and reproducible packaging | Failure tests, both supported host environments, pinned build, notices and upgrade check | 7-13 days | 7-13 days plus any recovery-path redesign |
| **Initial total** | A reviewable paper integration, still not a live broker | **34-58 engineer-days (about 7-12 weeks)** | **33-57 days plus an unbounded recovery-path blocker** |

The common work is necessary with either engine. LEAN's observed public `AlgorithmManager`, `IBrokerage`, fill and setup seams lower *feasibility uncertainty*, not the amount of correctness logic TideLab owns. The [joined paper test](TL-001A-LEAN-JOINED-PAPER-WORKFLOW.md) is 418 nonblank lines of test wiring alone; it is not a production size estimate. NautilusTrader's Python route may reduce bridge work, but the pinned release rejects cache backing with the tested external Python data client; no bounded production estimate is credible until a supported durable route is demonstrated. Neither option justifies copying engine internals.

Maintenance is also TideLab work: on each pinned engine upgrade, rerun parity, cost/fill, correction/restart and ambiguous-submission cases; inspect API and dependency changes; and review platform packaging and notices. Reserve **3-7 engineer-days per candidate upgrade** as an initial planning allowance, with more for broken interfaces or changed behavior. This number is a budget assumption, not a measured release history. Windows execution of the LEAN C# host and cross-platform packaging remain unverified; the probes ran in isolated WSL. CI currently runs Python checks but does not compile the C# probe.

## Distribution and upgrade gates

- A source-only TideLab release can describe a separately installed, exactly pinned engine. It must identify the engine and its license without presenting the engine as TideLab-authored. No engine binary is being distributed now.
- LEAN at the pinned commit carries [Apache-2.0](https://github.com/QuantConnect/Lean/blob/88bce0fc6fe282378ee73c54cef1090d0d7a73ee/LICENSE). A future bundled binary needs the license and applicable attribution/NOTICE material; modified engine files would need change notices. Inventory actual transitive packages and the build's audit warnings before shipping. TideLab should retain its independent-project name and avoid implying QuantConnect endorsement.
- NautilusTrader at the pinned tag includes the [LGPLv3 license text](https://github.com/nautechsystems/nautilus_trader/blob/v2.0.0rc5/LICENSE). A bundled application/container needs a package-specific review of LGPL notices and license texts, dependency source and a suitable replacement/relinking route; the [LGPLv3 combined-work terms](https://github.com/nautechsystems/nautilus_trader/blob/v2.0.0rc5/LICENSE#L624-L697) describe alternative mechanisms and conditional installation information. Its actual package metadata and third-party inventory must be checked at release time. Keep the separate NautilusTrader trademark and contributor-agreement rules in the [publication policy](../OPEN_SOURCE_AND_PUBLICATION.md).
- Before either engine upgrade or release, pin the exact build artifact/source, inspect notices and dependency inventory, rerun the same frozen synthetic scenarios on the exact candidate, and record changed behavior as new evidence. Do not silently advance a dependency or publish market-data-derived artifacts with unknown rights.

These are engineering release gates based on pinned source and license text, not a determination that a specific future package already complies.

## Selection judgment and next decisive evidence

**LEAN is the preferred candidate for an initial hybrid foundation.** It has demonstrated the shared H1 skeleton decision path, a public managed-forward route, conservative partial fill seam, and one sequential file-backed intent-to-next-order recovery path. NautilusTrader remains a viable replay candidate but has no proven backed recovery path with TideLab's tested replaceable external Python data client. The portable identity now closes the narrow TL-001A export item for synthetic evidence.

**Defer formal selection on issue #2** until one bounded integrated test connects the *same* conservative cost/product rule to historical and forward paths and covers sell-side accounting, stale/missed/rejected outcomes and a concurrent correction at the paper-source submission barrier. The test should emit a portable identity using actual hashed synthetic inputs and show zero new submissions under ambiguity. This directly tests the remaining selection threshold; further isolated startup snapshots would add little. If it passes and the scoped ownership estimate remains acceptable, select pinned LEAN for TL-002 with single-writer local paper scope and record the residual implementation tasks there. If the test reveals a need to recreate engine internals or cannot enforce the paper barrier, revisit the engine or defer with that exact blocker. This choice remains independent of TL-001B rights and supplies no profitability evidence.
