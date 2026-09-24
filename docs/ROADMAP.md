# Roadmap

Milestones advance on evidence, not a promised return or fixed calendar. TL identifiers are local backlog labels, not existing GitHub issues.

Current state: TL-001 is integrated, and [TL-001A selected pinned LEAN](decisions/TL-001A-INITIAL-ENGINE-SELECTION.md) for the first synthetic historical/local-paper integration. TL-001B remains an open data-rights gate. TL-002 began with a [durable synthetic paper-intent barrier](evidence/TL-002-PAPER-INTENT-BARRIER.md); the LEAN join and reconciliation remain open under issue #48.

Data-depth and rights finding: a 2026-09-16 public 30-day probe admitted only the latest 349 of 720 requested hourly bars after rejecting responses outside each requested window. Coinbase's Market Data Terms reviewed 2026-09-21 also create material automated-analysis and publication-rights questions for market data and derived artifacts. Pending TL-001B, pause new Coinbase acquisition for strategy development or automated analysis. Establish a sufficiently long, rights-cleared historical and forward source before TL-003; never treat endpoint access or the current depth as adequate public-research coverage.

Open-source direction: TideLab-authored work is Apache-2.0. Use pinned LEAN's public interfaces for the first bounded engine integration and keep TideLab policy, data, paper authority, and evidence replaceable. The engine choice does not finish the local paper controls or a distribution review. Capture lightweight publication-safe evidence during development and produce any polished video later from versioned results.

Publication standard approved 2026-09-21 and priority clarified 2026-09-22: publish TideLab code and synthetic fixtures; prioritize a deep, usable dataset for local research and forward-paper testing. Public raw datasets and real-data-derived charts/results/video are optional and require separate artifact-specific rights. Prefer a reproducible acquisition recipe where allowed. Initial data-source spend is $0; Coinbase and BTC-USD may be replaced if rights or technical coverage fail. See the [TL-001B preflight](evidence/TL-001B-DATA-RIGHTS-PREFLIGHT.md) and [source option map](evidence/TL-001B-DATA-OPTIONS-20260924.md). No real-data source has yet passed the local research gate.

| ID | Slice | Deliverable and exit criteria |
|---|---|---|
| TL-000 | Project foundation | Plan and venue-agnostic research decisions saved; establish repository owner/visibility and integration authority before remote setup |
| TL-001 | Canonical public-data foundation | Versioned instrument/event contracts plus a Coinbase BTC-USD reference adapter; restart-safe metadata, historical bars and live feed capture; gap/duplicate/freshness report; no credentials, strategies, or orders |
| TL-001A | Engine adoption bakeoff | Completed bounded comparison of pinned NautilusTrader and LEAN using synthetic replay, historical/forward decisions, costs/fills, recovery, dependency boundaries, and evidence export; selected pinned LEAN for initial integration without an upstream fork |
| TL-001B | Research-data gate | Select historical and forward sources with adequate depth and supportable research, retention, and automated-analysis use; separately record rights for any optional public dataset, chart, report, or video; keep Coinbase a local technical fixture unless its proposed use is cleared |
| TL-002 | Strategy, execution, and ledger integration | Implement TideLab-owned manifest, target-position/trade-intent, risk, and execution-mode boundaries on the adopted engine; prove cash/inventory accounting, costs, partial/missed fills, reconciliation, and failure behavior; build custom engine components only for documented critical gaps |
| TL-003 | Reproducible research harness | Immutable experiment registry, deterministic replay/backtester, trial accounting, chronological partitions, benchmarks, cost stress, and registered baseline strategy family including frozen H1 |
| TL-004 | Forward paper and advisory runner | Unmodified strategy versions on newly arriving data; simulated mode first; optional separately authorized advisory proposals with actual-fill reconciliation; daily report and incident record |
| TL-005 | Portability proof | Implement one structurally different public/read-only or paper adapter, such as an event-contract or on-chain market; pass core contract tests while preserving native costs, lifecycle, expiry/settlement or transaction semantics |
| TL-006 | Tiny live pilot | Separate user authorization and capital/loss limits; chosen venue/account eligibility, terms, fees and permissions verified; recovery and risk controls tested; actual fills compared with simulation |
| TL-007 | Controlled expansion | Adequate live evidence and cost justification; slow capped sizing changes at review intervals; rollback criteria recorded; no automatic scaling from recent wins |
| TL-008 | Optional advanced research and reporting | Separately registered multi-asset, higher-turnover, event-contract, Solana/DeFi or MCP reporting work only where evidence shows a measured need and its own budget/gates are approved |

## TL-001 implementation acceptance

- Document data provenance, endpoint/channel requirements, limits, achievable historical depth, and local interruptions.
- Define minimal versioned `Instrument`, `CapabilityProfile`, and `MarketEvent` contracts without implementing speculative future adapters.
- Keep Coinbase identifiers and rules in the reference adapter/configuration, not in canonical storage or future strategy code. Preserve native source evidence needed to audit normalization.
- Capture at least one complete hourly bar and demonstrate an interrupted/restarted recording without silent duplication or fabricated observations.
- Ingest closed bars only into strategy-ready data; identify incomplete bars, missing periods, and stale responses.
- Verify product increments/minimums are data, not constants embedded in strategy code.
- Test timestamp normalization, duplicate processing, gap detection, and retry behavior with bounded fixtures. Run one read-only integration smoke test; do not claim it validates unattended uptime.
- Provide documented start/stop/report commands, dependency lock, configuration example with no secrets, and a short evidence report.

## TL-001A engine bakeoff acceptance

- Pin one released NautilusTrader version and record its source revision, license, supported Python/runtime, and migration risks.
- Feed permitted TL-001 or synthetic fixtures through the candidate without credentials and reproduce closure, ordering, gap, duplicate, freshness, and provenance assertions.
- Implement one H1 skeleton once and demonstrate identical strategy semantics under deterministic historical and forward-paper clocks.
- Exercise fees, spread/slippage, rounding, partial/missed/rejected fills, restart/reconciliation, and ambiguous state without claiming that simulation proves live behavior.
- Export a TideLab experiment identity containing engine, code, configuration, data, cost, and trial provenance.
- Document every TideLab requirement not met by public extension points. Reject a permanent fork as the default; if a critical gap remains, run the same bounded evaluation against LEAN before proposing custom engine work.
- Before distribution, define third-party notices, corresponding-source/replacement handling for bundled artifacts, and the independent-project trademark disclaimer.

## TL-001B data and publication acceptance

- Inventory the exact historical and forward artifacts needed for research, charts, reports, demonstrations, and reproducibility.
- For each candidate source, record provenance, access date, depth/completeness, costs, retention, redistribution, derived-work, charting/video, and automated-analysis terms.
- Select a local research source only when technical coverage and the intended research, retention, and automated-analysis rights are supportable. Unknown rights for that use fail closed and require clarification or another source. Public derived artifacts have a separate publication gate and may be omitted.
- Keep restricted raw data and derived artifacts out of Git and public releases. Provide synthetic or expressly redistributable public fixtures plus acquisition instructions and hashes where permitted.
- Re-run validation when a provider changes terms or the proposed public artifact changes materially.

## TL-002 implementation acceptance

- Use the [TL-001A selected LEAN pin](decisions/TL-001A-INITIAL-ENGINE-SELECTION.md); complete TL-001B before real-data strategy work. Record data-source rights/provenance and every approved exception.
- Define strategy requirements, target positions/trade intents, independent risk decisions, order/fill states, cashflows, settlement extensions, and execution-mode boundaries.
- Run identical strategy semantics against deterministic replay and forward-paper clocks; environment-specific code may supply data and fills but may not change the strategy rule.
- Reconcile cash, inventory, fees, realized/unrealized P&L, and all modeled order states. Test duplicate, partial, missed, rejected, interrupted, and ambiguous outcomes.
- Keep simulated, advisory, and automated configuration and storage fail-closed and visibly distinct. Automated submission remains absent.
- Keep TideLab-owned policy and experiment records exportable independently of the engine. Do not copy or silently patch dependency internals to pass acceptance.

## Evaluation design for TL-003 and later

Partition data chronologically into development and untouched evaluation periods. Select dates before inspecting evaluation performance and record all experiments. Seek rising, falling, and sideways conditions where available. Quantify data omissions; never claim a regime was tested if it was not.

Use conservative execution: next available tradable price after signal plus fees/spread/slippage. Historical candles do not reconstruct order queues; use pessimistic assumptions or restrict conclusions. A touched limit is not an automatic fill. Avoid same-bar lookahead, survivor-only token datasets, and treating correlated trades as independent samples.

Freeze numeric criteria for net expectancy, drawdown, cost stress, and uncertainty before the untouched test. Proposed drawdown settings are in PLAN.md; final research criteria need to be selected before results, not retrofitted afterward.

Every public, open-source, or model-generated strategy and every tested parameter variant counts as a trial. Preserve failures and sources. Limit the search budget per hypothesis, and use search-aware/selection-aware statistics when the trial count warrants them. Do not repeatedly mine the untouched interval or promote the historical winner merely because it ranked first.

When designing TL-003/TL-004, consider the optional Jev runtime judgment experiment in [issue #21](https://github.com/Loothore907/tidelab/issues/21) under the [strategy research protocol](STRATEGY_RESEARCH.md#optional-runtime-decision-model-evaluation). It must beat a frozen code-only baseline on relevant evidence before any runtime role; this note does not advance TL-001A/TL-001B or authorize model calls or trading.

Every experiment also records whether its data and derived artifacts may be retained, shared, charted, demonstrated, or used for automated analysis. Reproducibility claims may not depend on publishing material that TideLab has no right to publish.

## TL-005 portability acceptance

- Select the second target for structural difference and research value, not because its live use is already approved.
- Verify public-data rights/availability, product lifecycle, current user eligibility assumptions, automation terms, and all material cost components before implementation.
- Reuse canonical research and experiment contracts while adding native extensions for material behavior such as event expiry/settlement or on-chain routing/confirmation/fees.
- Pass shared contract and replay tests. Document every abstraction that changed after encountering the second venue; portability is not considered proven merely because an interface exists.
- Remain read-only, simulated, or separately approved advisory. TL-005 grants no live trading authority.

## Promotion evidence

- Positive net expectancy estimate under baseline costs, acceptable drawdown, and useful benchmark comparison. Report uncertainty using dependence-aware methods such as block resampling when appropriate; insufficient evidence means remain in paper mode.
- Show sensitivity to worse costs and small parameter changes. Report the effect of the largest wins and distinct market periods.
- Initial forward observation floor: at least 8 weeks AND 50 closed trades, extending as necessary without forcing extra trades. This is a review floor, not statistical proof or an automatic live gate. Hourly trend trading may need substantially longer.
- No unresolved accounting discrepancy or critical recovery defect. Validate behavior during disconnect and restart.
- Complete TL-005 and demonstrate that the core did not hide material lifecycle or cost behavior before promoting any adapter to live consideration.
- Before live: user supplies a stake they can lose, maximum dollar loss, exposure cap, and operating budget. Account eligibility, current fees, key permissions, and precise emergency position policy must be verified.

If a strategy fails, close its experiment with the evidence. A new hypothesis gets a new version and evaluation; infrastructure spending is not the default response.

Positive expectancy is not regular income. After a strategy survives forward testing, separately estimate income capacity from capital, return variability, drawdown duration, turnover, capacity, taxes, and full operating cost. Do not force trade frequency, leverage, or strategy changes to satisfy a monthly-income target.

## Integration plan for implementation

The public repository is [Loothore907/tidelab](https://github.com/Loothore907/tidelab), with `main` as the default branch. The planning baseline and the two feature branches are pushed. Public source publication has begun; no market-data archive, strategy result, recording, or video has been published. Merge authority and gates remain separate from branch publication.

Use `main` as the integration base and an issue-linked focused branch/PR for each coherent slice. Issues #1-#4 and PRs #5-#6 record the foundation and open-source decision. Run required local checks and exact-head CI and integrate only within granted authority. Follow the user's global Git hygiene instructions. Do not invent remote evidence or bypass checks.

TL-001A and TL-001B are separate reviewable slices after TL-001 integration. Evidence capture is ongoing and sanitized; selecting video software, purchasing services, recording private account activity, or publishing a video requires separate later scope.
