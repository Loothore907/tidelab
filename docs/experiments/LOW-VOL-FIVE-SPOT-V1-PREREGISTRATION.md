# TL-003 low-volatility five-spot v1: frozen exploratory study

Owner: [issue #93](https://github.com/Loothore907/tidelab/issues/93). Candidate: private intake record `paper-pyo-jang-low-volatility` v3, canonical JSON SHA-256 `8203e8fc6996ec04a4d6898fe301e5d93af93ed22040dc406b48da9574ed37b9`. The owner approved this named synthetic implementation and private exploratory comparison on 2026-09-25 Alaska time. This plan was written before opening prices for this candidate. It is a five-market TideLab adaptation of [Pyo and Jang (2026)](https://doi.org/10.1016/j.frl.2026.109851), not a replication of their 432-asset finding.

## One fixed rule and one data identity

The five OKX USDT spot markets and their order are pinned by `research/first-pass-universe-v1.json` (SHA-256 `684cc9cabdd6854a2decd2d580fda08a399a7364ad6c95b0a6e1ac26a0354393`). Use only the existing private `okx.historical_archive.candlesticks.1m` hourly store. The source/provenance reader must require one closed, complete, contiguous, same-source hourly bar per market through each partition, reject invalid/duplicate/corrected rows, and bind every row to a private SHA-256. Any input failure aborts the partition; it does not remove a market or silently fill a gap.

At the first day of each month, 00:00 UTC, rank the five assets by the sample standard deviation of the preceding 60 fully closed UTC daily log returns (61 consecutive daily closes). Exact ties use plan order. Target 25% of signal-time marked equity in the lowest-volatility asset, 75% USDT cash. The first hypothetical full fill is at 01:00 UTC hourly open, sells before buys, with no same-close fill, leverage, short, stop, profit target or intramonth switch. Rebalance even if the same asset remains lowest. Any nonfinal sale blocks its replacement buy. Quantity floors to `0.00000001` coin, and buying is capped by modeled cash including fee. These are **research-unit assumptions**, not verified OKX product minimums or executable orders.

## Trial clock and budget

The common source window from the private metadata audit was `2023-07-01T00:00:00Z` through `2026-08-31T16:00:00Z`. The study uses 35 complete monthly holds from the September 1, 2023 signal through August 1, 2026 terminal mark. Freeze these partitions now:

| Partition | First signal | Terminal mark | Holds | Opening gate |
| --- | --- | --- | ---: | --- |
| Development | 2023-09-01 00:00 UTC | 2025-01-01 01:00 UTC | 16 | Integrated exact-head CI and same-day data-rights check |
| Validation | 2025-01-01 00:00 UTC | 2026-01-01 01:00 UTC | 12 | Development review meets every rule below |
| Untouched | 2026-01-01 00:00 UTC | 2026-08-01 01:00 UTC | 7 | Validation review meets every rule below |

One attempt per partition for this strategy version, including an aborted or failed attempt. Record its identity, code commit, plan hash, input hashes, cost version, start/status and result hash in ignored local storage **before** and after execution. No retry on the same identity; a corrected implementation or changed input is a new disclosed version. Do not open later partitions when a preceding gate fails. The paper's underlying sample ended November 2025, so only eight of these holds begin after that endpoint, and none is a long independent forward test.

## Comparisons and hypothetical execution

Start each partition independently with 10,000 USDT modeled cash. At its first 01:00 open, acquire and hold: (1) 25% BTC, or (2) 5% in each of the five markets, both with 75% modeled cash before costs. Also report cash unchanged. These fixed passive comparators have the same initial exposure budget and are marked at the same terminal open. They do not rebalance monthly. The strategy uses monthly 25% targets and consequently may incur more turnover. No terminal sale is charged for any path; terminal value is a mark.

Base per-side cost is 0.25% fee plus 0.05% half spread plus 0.05% adverse slippage. Stress doubles all three components (0.70% total adverse reference). Apply adverse price and fee on every hypothetical buy and sell. Also report a missed/repriced-fill sensitivity as a scenario bound, not a fill probability: delay all planned fills one additional hour and add another 0.10% adverse price. If the data or engine cannot compute that sensitivity exactly, flag the study incomplete rather than infer robustness. Hourly OHLCV cannot establish fill probability or broker finality. Issue #48 owns that separate evidence.

Privately retain each monthly selected market, changes, marks, fills, fees, turnover, net return and maximum marked drawdown for each candidate and comparator at base and stress costs. Do not commit prices, selections, metrics or real-data-derived charts. A source hash and nonperformance status may be committed if publication rights support the artifact.

## Decision matrix fixed before prices

Review each opened partition against the same criteria. `Survived for further observation` requires all: strategy base net return above cash, equal-weight and BTC comparators; stress net return above cash; base maximum drawdown no worse than the equal-weight comparator; at least two distinct selected assets and at least three month-to-month selection changes. Any failed requirement is `rejected for this fixed rule`. Missing data, invalid provenance, unavailable sensitivity or an accounting discrepancy is `incomplete`, with no next partition opened. There is no parameter adjustment based on results. A survival across historical partitions would still only nominate prospective observation; this five-market archive alone cannot establish a broad volatility anomaly, profit expectancy, or paper readiness.

The selected [OKX historical terms](https://www.okx.com/en-us/help/historicaldata-terms-and-conditions) allow personal possession, retention and own-strategy development under a revocable license. Check them on the day of each private run. Rights for publication of real-data-derived results remain separate. Issue #3 owns timely forward data and publication rights; issue #48 owns execution and reconciliation. No account access, download, real order or live operation is part of this study.
