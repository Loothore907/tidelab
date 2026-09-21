# Roadmap

Milestones advance on evidence, not a promised return or fixed calendar. TL identifiers are local backlog labels, not existing GitHub issues.

Current state: TL-001 is implemented and locally validated on `feat/tl-001-market-data`. It remains pending remote issue/PR review and exact-head CI; TL-002 has not started.

Data-depth finding: a 2026-09-16 public 30-day probe admitted only the latest 349 of 720 requested hourly bars after rejecting responses outside each requested window. Establish a sufficiently long historical source or accumulated archive before TL-003; never treat the current public depth as adequate backtest coverage.

| ID | Slice | Deliverable and exit criteria |
|---|---|---|
| TL-000 | Project foundation | Plan and venue-agnostic research decisions saved; establish repository owner/visibility and integration authority before remote setup |
| TL-001 | Canonical public-data foundation | Versioned instrument/event contracts plus a Coinbase BTC-USD reference adapter; restart-safe metadata, historical bars and live feed capture; gap/duplicate/freshness report; no credentials, strategies, or orders |
| TL-002 | Strategy, execution, and ledger contracts | Capability-aware strategy manifest; shared target-position/trade-intent and risk contracts; realistic Coinbase paper broker; cash/inventory accounting, costs, partial/missed fills, reconciliation, and failure tests |
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

## TL-002 implementation acceptance

- Define strategy requirements, target positions/trade intents, independent risk decisions, order/fill states, cashflows, settlement extensions, and execution-mode boundaries.
- Run identical strategy semantics against deterministic replay and forward-paper clocks; environment-specific code may supply data and fills but may not change the strategy rule.
- Reconcile cash, inventory, fees, realized/unrealized P&L, and all modeled order states. Test duplicate, partial, missed, rejected, interrupted, and ambiguous outcomes.
- Keep simulated, advisory, and automated configuration and storage fail-closed and visibly distinct. Automated submission remains absent.

## Evaluation design for TL-003 and later

Partition data chronologically into development and untouched evaluation periods. Select dates before inspecting evaluation performance and record all experiments. Seek rising, falling, and sideways conditions where available. Quantify data omissions; never claim a regime was tested if it was not.

Use conservative execution: next available tradable price after signal plus fees/spread/slippage. Historical candles do not reconstruct order queues; use pessimistic assumptions or restrict conclusions. A touched limit is not an automatic fill. Avoid same-bar lookahead, survivor-only token datasets, and treating correlated trades as independent samples.

Freeze numeric criteria for net expectancy, drawdown, cost stress, and uncertainty before the untouched test. Proposed drawdown settings are in PLAN.md; final research criteria need to be selected before results, not retrofitted afterward.

Every public, open-source, or model-generated strategy and every tested parameter variant counts as a trial. Preserve failures and sources. Limit the search budget per hypothesis, and use search-aware/selection-aware statistics when the trial count warrants them. Do not repeatedly mine the untouched interval or promote the historical winner merely because it ranked first.

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

Repository name proposal: tidelab. Owner, visibility, remote, default branch, and push/PR/merge authority are not yet selected. No external publication has been performed.

Once established, use main as the proposed protected base and an issue-linked branch for each coherent slice, beginning with feat/tl-001-market-data. Create actual owning issues, reference them from Conventional commits and draft PRs, run required local checks and exact-head CI, and integrate passing slices within granted authority. Follow the user's global Git hygiene instructions. Do not invent remote evidence or bypass checks.
