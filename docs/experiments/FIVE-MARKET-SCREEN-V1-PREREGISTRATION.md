# TL-003 five-market candidate screen v1

Status: preregistered before reading price payloads for this screen. Owner: [issue #86](https://github.com/Loothore907/tidelab/issues/86). This is a small private historical screen, not an H1 v1 continuation, an execution-venue selection, a paper-order permission, or evidence of profit.

## Input and partition gate

Use only the existing ignored `data/okx/research.sqlite3` and the exact `okx.historical_archive.candlesticks.1m` source. The fixed [universe plan](../../research/first-pass-universe-v1.json) names OKX spot BTC-USDT, ETH-USDT, BNB-USDT, XRP-USDT, and SOL-USDT. The comparison input is complete closed UTC hourly bars from `2023-07-01T00:00:00Z` inclusive through `2026-08-31T16:00:00Z` exclusive. No other source fills a missing hour. Re-run the metadata-only coverage gate and verify plan hash, exact source, closure, provenance and shared continuity before opening prices. A market failing any check is excluded, recorded, and **not replaced**; fewer than five eligible markets abort v1 rather than changing the universe. The last shared bar supplies an exit open, so the final scored hour ends one hour earlier.

| Partition | Scored UTC start, inclusive | Scored UTC end, exclusive | Purpose |
| --- | --- | --- | --- |
| Development | 2023-07-31 00:00 | 2025-01-01 00:00 | Ten fixed market-rule combinations; selection only here |
| Validation | 2025-01-01 00:00 | 2026-01-01 00:00 | One development-selected combination, once |
| Untouched | 2026-01-01 00:00 | 2026-08-31 15:00 | Same frozen combination, once if validation passes |

Each partition reads the preceding 720 closed hourly bars for indicators only, starts with 10,000 hypothetical USDT in cash, and has no carried position. Its final position is liquidated at the next bar's open at the partition end, with normal costs. Suppress a new entry at the final scored close; no signal can use the liquidation bar's close. A missing warmup, scored, or liquidation bar aborts that attempt. The archived 2026 period is historical even if it was untouched by this screen; it is not a forward test. Do not open or rerun H1 v1's untouched evaluation.

## Two fixed strategy families

Both are long-or-cash on one spot market at a time, with no shorting, leverage, averaging down, model calls or intrabar signal. At the close of hour `t`, use only complete bars through `t`. Submit a simulated marketable intent no earlier than the open of hour `t+1`. Hold the position without rebalancing until an exit signal. Both require at least 720 prior closed hours at a scored signal.

1. `momentum-720-v1`: enter when the just-closed price is strictly greater than the close 720 hours earlier. Exit when it is less than or equal to that older close. Rationale: sustained price direction may persist beyond short noise.
2. `reversal-24-v1`: while flat, enter when the just-closed price is at most 95% of the close 24 hours earlier. After entry, exit on the first close at or above the entry-signal close, or after 48 complete hours in position, whichever occurs first. Rationale: a sharp daily decline may partly reverse. The entry-signal close and fill hour are immutable state; no trailing threshold or parameter search.

An entry targets 25% of then-current marked equity. Buy quantity is rounded down to eight decimal places after reserving the entry fee. Exits sell the full modeled quantity. No new entry may be made if marked account equity has fallen 20% from its partition peak; an existing position exits at the next open and entries remain paused for that partition. This independent research risk gate is a scenario, not a live risk control. Missing, nonpositive, unordered, duplicate, unclosed, or non-OHLC-consistent bars fail closed. Orders are assumed fully filled at the next hourly open after adverse costs; hourly candles cannot demonstrate actual liquidity, fill probability, queue position or real spread.

## Costs, benchmarks, and metrics

The base cost on **each side** is a 0.25% fee, 0.05% adverse half-spread and 0.05% adverse slippage. The stress case doubles each component: 0.50%, 0.10% and 0.10%. For buys, increase the next open by spread plus slippage; for sells, decrease it. Fees apply to executed notional. These are hypothetical conservative screen assumptions, not a verified OKX fee or future execution venue. A touched limit is never a fill in this model; only the declared full-fill marketable scenario is tested. Any later candidate needs quote/trade evidence, missed-fill sensitivity, venue rules and current execution costs.

Start every strategy and benchmark at 10,000 USDT. Compare cash at zero interest, a 25%-allocation buy-and-hold position (primary), and a fully allocated buy-and-hold context position over identical partition dates. Both buy-and-hold positions buy at the first scored hour's open and sell at the liquidation hour's open, paying the same costs. Report base and stress net return, maximum marked drawdown, time underwater, turnover, fees, average exposure, closed round trips, largest trade contribution, and the result without that trade. Record the difference from the 25% benchmark; a higher return with substantially higher exposure is not automatically a better strategy. Price and all derived results stay private.

## Trial budget and selection rule

The budget is **ten development combinations**: two fixed rules times five fixed markets, one parameter setting each. Every combination and any failed or aborted attempt counts and receives an append-only private registry entry before strategy execution. No second parameter, market replacement, extra family, or manual rerank belongs to v1. A code correction after an opened result must be recorded as a new version and cannot silently erase that attempt.

A development combination survives only if its base net return is strictly above cash and its costed 25% buy-and-hold benchmark, stress net return is positive, maximum marked drawdown is at most 15%, and it closes at least ten round trips. Fewer trades is **inconclusive**. If none survives, stop and record rejection/inconclusive status without opening validation or untouched data. Among survivors, choose the largest base return margin over 25% buy-and-hold, then lower maximum drawdown, then the universe-plan order and the family order above. Selection is based on development alone. Evaluate only that one selected combination in validation. Apply the same gates there; failure ends v1. If it passes, freeze the integrated code/configuration/data/cost identity and open the untouched partition **once** for that same combination. Apply the same gates there. An untouched pass nominates only a candidate for a separately registered deeper historical and eventual forward-paper investigation, not an edge, income, order, or live-trading claim. An untouched failure rejects v1. Do not substitute the development runner-up after seeing validation or untouched results.

Keep an append-only private ledger with attempt ID, phase, strategy/market, code and configuration hashes, exact-source data/provenance hash, terms review date, cost identity, UTC start/end, outcome, warnings, metrics artifact hash and parent selection. Preserve all ten outcomes and any failure. A selected winner from ten correlated trials is exploratory; do not turn one pass into a statistical confidence claim. A later deeper test must examine dependence, regimes, small rule changes, execution uncertainty and the selection count.

## Rights and integration gates

The [OKX U.S. historical-data terms](https://www.okx.com/en-us/help/historicaldata-terms-and-conditions) were checked on 2026-09-25 for personal possession, retention and own-strategy development. Recheck the current terms on the run date. No new data acquisition, public real-data artifact, provider outreach, account access, subscription, paper submission or live trading follows from this experiment. The delayed archive does not settle [#3](https://github.com/Loothore907/tidelab/issues/3)'s timely-feed rights/continuity/cost gate. [#48](https://github.com/Loothore907/tidelab/issues/48)'s external broker snapshot, finality, correction and hold-release gates remain separate.

Implement and test against synthetic invented bars first. Inspect the exact diff and required checks; run real-data trials only from the integrated reviewed source with a clean `main`, fresh matching `origin/main`, and exact-head CI. Keep local results under ignored `data/`; public PRs may contain the rules, synthetic fixtures, tests and sanitized implementation evidence only.

The first pass may use a narrow deterministic offline accounting estimate for cheap screening. It is not a replacement paper broker or a LEAN engine integration claim. A survivor must reproduce its strategy, risk, and cost semantics on the selected pinned LEAN boundary before any forward-paper consideration.
