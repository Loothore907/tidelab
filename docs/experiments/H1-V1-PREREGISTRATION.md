# H1 v1 research preregistration

Status: rules and evaluation plan frozen before viewing H1 performance on real data. Owner: [TL-002 issue #48](https://github.com/Loothore907/tidelab/issues/48), with the independent [TL-001B forward-data gate #3](https://github.com/Loothore907/tidelab/issues/3). This is a research specification, not a run record, strategy result, paper-order authorization, or claim of feasible execution. Any substantive change creates H1 v2 and counts as another trial.

## Hypothesis and fixed rule

H1 v1 asks whether a simple hourly trend filter on liquid spot Bitcoin improves the return/drawdown tradeoff after modeled costs. The research instrument is OKX BTC-USDT spot; the rule itself uses only a sequence of complete UTC hourly bars and long/cash state. No shorting, leverage, averaging down, model judgment, or manual override.

- Indicator: the arithmetic mean of the latest **168 closed hourly closes**, including the just-closed hour. Require all 168 bars before the first signal. Do not use the next bar's price or any later observation in the decision.
- At each hour close, when in cash, propose one long entry if that close is strictly above the mean. When long, propose an exit to cash if that close is less than or equal to the mean. Otherwise hold the existing state. No periodic rebalance while long.
- One entry targets **25% of account equity** at the next available hour's open. Exit sells the full modeled position. Round acquired units down to 8 decimal places. Keep the remainder in non-interest-bearing USDT cash. Missing or unclosed bars invalidate the run rather than prompting interpolation or a catch-up fill.
- Independent risk policy: no borrowing and no gross exposure above 25% at entry. At a closed-hour mark, a **20% account-equity drawdown** from the prior peak requests an exit at the next feasible open and bars further entries for the rest of that partition. An exit is never blocked by an entry pause. This is a simulated research limit, not a live account control.

## Data and timing

Use only the [locally validated OKX archive](../evidence/TL-001B-OKX-HISTORICAL-20260924.md), exact source `okx.historical_archive.candlesticks.1m`, instrument `okx:BTC-USDT`, and complete 3600-second bars. The observed local coverage is `2023-06-30T16:00:00Z` through exclusive `2026-09-23T16:00:00Z`. Verify that coverage, source identity, stored hashes, and zero missing hours again at execution. The archive's delay prevents calling any archived interval an on-time forward test.

| Partition | UTC start, inclusive | UTC end, exclusive | Use |
| --- | --- | --- | --- |
| Warmup | 2023-06-30 16:00 | 2023-07-07 16:00 | Indicators only; no scored trades |
| Development | 2023-07-07 16:00 | 2025-01-01 00:00 | Implementation/debugging and data-quality checks |
| Validation | 2025-01-01 00:00 | 2026-01-01 00:00 | One fixed-rule check, no parameter selection |
| Untouched evaluation | 2026-01-01 00:00 | 2026-09-01 00:00 | Open once after all gates below pass |
| Reserved | 2026-09-01 00:00 | 2026-09-23 16:00 | No H1 v1 evaluation; may support a separately registered later question |

Each scored partition starts with **10,000 hypothetical USDT**, cash, and no open order. Its 168-hour warmup may read preceding bars only to form the first indicator; positions and performance do not carry over. Signals use the closed hour; fills occur no earlier than the following hour's open. The final position is liquidated at the next feasible open after the partition's last signal, with the same cost model. If that open is unavailable, the partition is incomplete.

## Cost model and comparisons

The base case charges an adverse **0.10% execution-price adjustment** plus a **0.25% fee** on each buy and sell. A predeclared stress case doubles both to 0.20% and 0.50%. These are hypothetical research assumptions, not a verified OKX or future execution-venue fee schedule, spread, or fill. There is no assumption of intrabar queue position, passive fills, USDT yield, or slippage inferred from OHLCV. The run must report both cases; a later venue-specific claim needs observed rules, fees and quote/trade evidence.

Compare identical partitions and starting capital with (1) cash at zero interest, (2) a 25%-allocation buy-and-hold Bitcoin position, and (3) a fully invested buy-and-hold context benchmark. Benchmarks buy at the first feasible open, liquidate at the final feasible open, and pay the same modeled costs. Report total and net return, maximum drawdown and time underwater, exposure, turnover, fees, closed round trips, and dependence on the largest trade. The 25% benchmark is the primary comparison; the full-allocation benchmark supplies market context.

## Trial budget and predeclared decision

**One candidate, one parameter value, and one untouched evaluation.** There is no search over moving-average length, threshold, sizing, or stop level in H1 v1. Development debugging must use synthetic fixtures or the development partition only. Code/configuration/cost/data identities and every failed or aborted run must be recorded before opening validation or untouched output. An implementation correction after validation requires a new trial identity and a disclosed prior result. After opening untouched results, H1 v1 cannot be tuned and retested on that period.

H1 v1 is *eligible for a separate forward-paper decision* only if validation and untouched evaluation each have positive net return above cash and the primary 25% buy-and-hold benchmark at base costs; maximum account drawdown in each is at most 15%; the untouched stress case remains positive after costs; and validation plus untouched contain at least 20 closed round trips. Fewer trades means **inconclusive**, not a pass. Any failed performance condition rejects this candidate under these declared conditions. Passing these conditions would nominate a paper candidate, not establish an investable edge, income capacity, realistic fills, or permission for orders.

## Gates before local historical evaluation

1. Implement this exact rule and independent risk policy once behind the selected LEAN/TideLab boundary; test identical historical/forward decisions on synthetic bars, including warmup, next-hour timing, missing data, drawdown exit, and partition reset.
2. Complete the relevant [TL-002 accounting and recovery work](https://github.com/Loothore907/tidelab/issues/48): deterministic cash/inventory/fee reconciliation, no same-bar fill, and no new submission on ambiguity. Replay the same synthetic input twice with identical decisions and balances. No external broker or account is required.
3. Record the pinned engine, TideLab code revision, configuration and cost hashes, local archive hashes, terms reference, experiment identity, and all trial attempts. Keep actual data and data-derived results in ignored local storage.
4. Recheck the historical source's local research and retention terms at run time. Its selected personal-use basis allows a **local historical research run** after the preceding checks. The absence of an on-time forward source does not change a past bar's research rights. Keep real-data output local and out of Git.

An on-time paper run remains a separate gate under issue #3: select and validate a timely source with supportable scripted research/retention rights, exact-pair continuity, and effective cost. Then demonstrate that the frozen strategy and risk rules operate unchanged on newly arriving bars. Neither a historical pass nor a delayed archive authorizes paper orders, advisory proposals, live trading, or public real-data results.
