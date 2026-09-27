# BTC Monday: one bounded private workflow

Owner: [#95](https://github.com/Loothore907/tidelab/issues/95). The owner approved carrying the same bounded flow through admission implementation, synthetic tests, distinct review, CI, gated integration, one snapshot, one six-job batch and private accounting/independent audit. These are stages of one approval, not separate permission requests. Stop for a failed gate or material scope change; ordinary supporting steps continue autonomously.

The [selected implementation](TL-003-BTC-MONDAY-SYNTHETIC.md) is integrated in PR #108. The frozen private proposal and selected v2 record remain unchanged. `data/strategy_intake/BTC-MONDAY-V1-TRIAL-AUTHORITY.json` records the later end-to-end approval; its exact hash is bound in `monday_private.py`. Older implementation-only receipts remain historical evidence rather than the current scope.

## Exact admission

Only existing `okx:BTC-USDT` hourly starts in `[2024-01-01T00:00:00Z, 2025-01-01T00:00:00Z)` are permitted: 8,784 rows and zero preceding warmup. No pre-window or 2025 opening price, other market, replacement archive or new acquisition. This period is already exposed; no holdout or statistical-discovery claim follows.

The shared workflow reads the job count from each frozen binding. RSI and channel remain exactly 30; Monday is exactly six. Inventory construction rejects disagreement with the binding. There is no user-supplied budget, market, window, package, registry or retry flag. The six ordered jobs are the fixed strategy, cash and 25%-initial-allocation passive benchmark, each at the existing baseline/stress costs. Passive is an opportunity-cost comparison, not exposure-matched. The original store and RSI anchor remain canonical; old grants are not renewed or recreated.

Admission requires clean synchronized main with fresh successful exact-head CI, the exact authority/proposal/selected-record identities, latest intake selection and current-day terms review. Authorization appends to the canonical store. Snapshot reservation precedes any source query; continuity, OHLC and archive identities must pass. Batch reservation precedes snapshot verification and replay. Failures and timeouts retain consumed stages and artifacts. The run subprocess has a hard 1,800-second ceiling and never retries. The synthetic module's old unapproved entry points remain closed; only the exact private binding is admitted.

Review first requires all six completed scenarios with 8,784 scored bars. Both strategy scenarios must have exactly 52 closed trips and zero terminal holdings. Failure is `incomplete`, never nomination. Otherwise the frozen common gates require positive baseline and stress returns, baseline above passive and baseline drawdown at most 15%; failure is `not_nominated`. No automatic promotion, tuning or follow-on trial. Retain accounting, fees, turnover, exposure, benchmarks and trade diagnostics privately; independently audit the retained input and traces without replay before accepting the disposition.

## Verification and continuation

`tests/test_monday_private.py` exercises the complete route on invented archives in a temporary canonical store, the six-job count and zero warmup, exact timestamp query bounds, fixed-plan tampering, missing authority/store, failed-snapshot consumption, spent-grant refusal, stale terms, hard timeout, strict calendar conformance and retained-artifact recovery. Previous RSI/channel tests verify their 30-job inventories and consumed grants still behave as before. Review and exact-head CI are recorded in the PR.

After integration and exact-main CI pass, use the fixed CLI in order, once:

```powershell
.venv/Scripts/python.exe scripts/monday_private_batch.py authorize --terms-reviewed-utc-date YYYY-MM-DD
.venv/Scripts/python.exe scripts/monday_private_batch.py prepare --terms-reviewed-utc-date YYYY-MM-DD
.venv/Scripts/python.exe scripts/monday_private_batch.py run --terms-reviewed-utc-date YYYY-MM-DD
```

The date must reflect an actual current-day review of the [OKX historical terms](https://www.okx.com/en-us/help/historicaldata-terms-and-conditions). The official text reviewed on 2026-09-27 permits personal retention and own-strategy use under a revocable license; no redistribution is approved. Research output stays in ignored `data/research_program/monday-v1/`. Inspect grant events and retained receipts before continuation: an already attempted stage is not permission to retry it. Finish the private report and accounting/independent audit, then close the fixed version if it is not nominated. Keep #3 timely data and #48 execution independent. No new acquisition, account, order, spend or public real-data output.
