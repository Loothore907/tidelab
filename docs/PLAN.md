# Core plan and assumptions

## Purpose

Build a persistent, understandable research system that can express, backtest, compare, and forward-test versioned strategies across eligible venues without changing their economic rules between environments. The economic objective is to determine whether a strategy plus a feasible execution environment can earn positive expectancy after costs and, only after that, whether the edge and available capital could support useful income.

The user lives in Alaska, has prior Coinbase and Solana DeFi experience, and wants mock trades before any small live trades. Engineering knowledge and deployment experience are expected benefits of the work. They do not turn simulation into trading evidence, and automating execution does not establish an investment edge.

## Scope decisions

- The core is venue- and product-agnostic. It models instruments, market events, strategy requirements, target exposure, trade intents, risk decisions, orders/transactions, fills, cashflows, settlement, and experiments through explicit versioned contracts.
- Coinbase Advanced Trade BTC-USD is the first reference fixture, conditional on later account eligibility, cost, data-depth, research-use, retention, automated-analysis, and publication-rights verification. The implemented adapter is a technical characterization fixture, not a commitment to use Coinbase data for strategy research or demonstrations. Pending TL-001B, do not acquire new Coinbase data for strategy development or automated analysis.
- TideLab adopts before it builds. Evaluate a pinned NautilusTrader release against TideLab's determinism, accounting, recovery, experiment, and capability requirements before implementing a custom backtest, paper-broker, portfolio, or ledger engine. If a critical requirement fails without an upstream fork, evaluate LEAN before authorizing custom engine work.
- TideLab-authored work is Apache-2.0. Third-party code, data, trademarks, and artifacts retain their own terms. Prefer separately installed, replaceable dependencies; do not copy engine source into TideLab or maintain a permanent fork by default.
- Each experiment is deliberately narrow even though the platform is extensible. The first experiment uses hourly closed BTC-USD bars and one transparent trend-following hypothesis, long or cash.
- Later adapters may cover other centralized spot products, regulated event contracts, or on-chain markets. Every new venue/product requires a declared capability profile, native execution/cost model, data-quality evidence, current eligibility and API-terms review, and its own paper gate.
- Historical, forward-paper, and any future live environment share strategy and risk semantics. The clock, market-data source, and execution adapter change; strategy rules do not silently diverge.
- Execution modes are `simulated`, `advisory`, and `automated`. Advisory mode produces a time-limited recommendation for user execution and reconciles the actual fill. Automated mode is deferred and separately authorized.
- No leverage, derivatives, presales, meme launches, market making, sniping, or averaging down are included in the first strategy. Higher-turnover or latency-sensitive ideas are separate hypotheses with explicit unit economics and infrastructure requirements.
- Venue APIs remain the external execution boundary, whether reached by an adopted engine adapter or a narrowly justified TideLab adapter. Optional read-only MCP reporting is deferred and never participates in deterministic risk or execution decisions.
- Local Windows development and paper operation come first; use a portable Python application with SQLite storage. Linux cloud deployment occurs only when forward operation needs it and a budget is approved.
- Capture lightweight, publication-safe decisions, experiment identities, failures, reports, and selected milestone visuals as work proceeds. Select recording/editing software and assemble any video only after the technical stack is clearer and evidence worth presenting exists.

## Success ladder

1. Trustworthy data and deterministic replay.
2. Reconciled simulation and realistic venue-specific costs.
3. Reproducible historical evidence without leakage or hidden trials.
4. Immutable forward-paper behavior on newly arriving data.
5. A defensible estimate of net edge and drawdown.
6. A separate determination of income capacity from edge, capital, turnover, and costs.
7. Only with new authority: a tiny live pilot whose actual fills are compared with simulation.

## First research hypothesis

Hypothesis H1: a simple trend filter and explicit exit rule can provide a useful return/drawdown tradeoff after trading costs on liquid spot crypto. This is unproven.

Before evaluation, select and record exact indicator definitions, lookback periods, entries, exits, warmup length, execution assumptions, sizing rules, dataset dates, and benchmarks. Use only closed bars available at decision time; simulate execution after the signal, not retroactively at the signal's closing price.

Start with one baseline implementation and a small, declared sensitivity check. Do not search thousands of parameters. Changes after examining evaluation results create a new experiment; maintain a register of all attempted versions, including failures.

Public papers, public strategies, open-source implementations, and new model-generated ideas are hypothesis sources, not evidence. Re-express each candidate through TideLab's strategy contract. Record its source, rationale, required data/capabilities, exact rules, allowed parameter budget, and test count before promotion. See [STRATEGY_RESEARCH.md](STRATEGY_RESEARCH.md).

## Economic accounting

Report cash, inventory marked to market, realized and unrealized P&L, trading fees, spread, slippage, turnover, exposure, maximum drawdown, time underwater, and infrastructure costs. Separate deposits/withdrawals from investment performance. Maintain fill records suitable for later tax accounting; pre-tax performance is not after-tax profit.

Compare with cash and buy-and-hold over identical dates and starting capital, including benchmark costs. Also compare exposure/risk so lower exposure is not mistaken for superior selection. Show dependence on the largest winner; do not automatically disqualify trend following merely because returns are uneven.

## Assumption register

| Assumption | Status and resolution |
|---|---|
| User trades only their own funds | Working assumption; third-party money or commercial services require a new scope review |
| Alaska residence permits intended Coinbase service | Not account-verified; verify current eligibility before private/live operation |
| Existing Coinbase account can be recovered | Unknown; user handles login, identity verification, and MFA directly |
| Coinbase public data is suitable for strategy research and open publication | Not established; the recorder works, but observed depth is short and current terms create broad automated-analysis, redistribution, and derived-work concerns; pause new strategy-data acquisition and select a rights-cleared source in TL-001B |
| NautilusTrader can supply the execution/replay core | Plausible, not adopted; prove required behavior in TL-001A with an exact pinned version and no permanent fork |
| Apache-2.0 can govern TideLab-authored work | Approved; dependency licenses, source availability, and trademark obligations remain separate release gates |
| A future process video can be reproduced honestly | Design target; capture lightweight evidence now, then script and edit from versioned records after a meaningful result exists |
| Low-frequency trend trading can survive costs | Unproven; reject strategies that fail realistic and stressed cost tests |
| One research core can support different markets | Design target only; prove it with a second structurally different read-only/paper adapter before any live pilot |
| Public or model-generated strategies offer exploitable edge | Unproven; register every trial and correct conclusions for selection and overfitting risk |
| Microtrades improve income regularity | Unproven; fixed and variable costs, adverse selection, latency, failures, and operational burden may overwhelm gross edge |
| A home computer can provide adequate initial uptime | Acceptable for research; record gaps explicitly and pause on stale data |
| Live capital and acceptable loss | Unspecified; mandatory inputs before a live pilot |
| Positive expectancy can produce regular income | Unproven and separate; quantify capital requirements, return variability, drawdowns, taxes, and infrastructure cost after an edge survives forward testing |
| Growth through scaling is feasible | Unproven; re-evaluate liquidity, costs, and statistical uncertainty at each size |

## Budget

Current authorized incremental service spend: $0. Existing hardware, electricity, and existing Codex subscription are not economically free; report incremental cash expenses separately from full operating costs.

The discussed $25/month cloud ceiling is a proposal, not an approved purchase. The user's possible $500-$1,000/month future budget is conditional interest, not spend authority. Trading capital is separate from operating budget. Any paid service needs a concrete purpose, current price, cap, and authorization.

## Risk proposals for paper testing only

Use a clearly labeled $1,000 simulated account, 25% maximum gross spot exposure, and a 5% portfolio drawdown entry-pause threshold as provisional engineering defaults. These are not optimized settings or live risk approvals. Freeze them before evaluation; parameter changes start a new run.

Drawdown pauses block entries and invoke a separately specified existing-position policy. Stops cannot guarantee a maximum loss during gaps, outages, or poor liquidity. Initial live sizing, loss limits, and handling of existing positions remain undecided.

Scaling is disabled initially. Later, use scheduled reviews of net results, uncertainty, drawdown, and execution quality; no automatic increase merely because recent trades won. Test scaling rules as part of the strategy before deploying them.
