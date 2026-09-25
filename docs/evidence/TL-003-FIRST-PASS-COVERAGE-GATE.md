# TL-003: first-pass universe coverage gate

Owner: [issue #82](https://github.com/Loothore907/tidelab/issues/82). This is a synthetic implementation checkpoint for the previously fixed five-asset USDT spot universe. It does not select a market or strategy, establish data rights, acquire data, run H1, or permit paper orders. Data spend remains $0.

The versioned [plan](../../research/first-pass-universe-v1.json) fixes BTC, ETH, BNB, XRP and SOL, the exact OKX archive source, a common UTC window from 2023-07-01 to 2026-09-01, and a minimum of 24 contiguous calendar months. The local `audit-universe-coverage` command reads an **existing** SQLite database in read-only mode. It checks only hourly timestamps, closed flags and archive provenance metadata; it reads no price or volume payload. It records missing intervals and excludes a pair with no exact-source bars, short continuity or invalid source rows. Bars from another source cannot fill a gap. The report also requires two or more individually eligible markets to share one continuous 24-month window before it marks the set comparable.

Use only with a locally held, rights-supported database. Output is private coverage metadata; keep it under ignored `data/` and do not commit or publish a real-data-derived report. An example invocation for a future permitted local audit is:

```powershell
.\.venv\Scripts\python.exe -m tidelab audit-universe-coverage `
  --database data\okx\research.sqlite3 `
  --plan research\first-pass-universe-v1.json `
  > data\okx\first-pass-coverage-private.json
```

The synthetic checks create invented hourly rows and cover a complete month, a missing market, a one-hour gap hidden by another source, invalid archive provenance, and two individually complete markets with no shared month. Local verification: 74 Python tests passed, one optional Nautilus import skipped; two context tests and Python compilation passed. No real-market coverage report was generated for this checkpoint. The known #3 state remains: BTC has validated historical depth; exact archive availability and continuity for ETH, BNB, XRP and SOL remain unverified. The delayed archive cannot supply on-time decisions, and timely-feed rights, continuity and effective cost are unresolved.

This gate establishes **coverage readiness only**. Before any market-strategy ranking, issue #3 must settle the intended data use and validate exact-pair coverage; TL-003 must freeze a shared comparison interval, costs, benchmarks, strategy variants and trial budget. A backtest on hourly candles cannot infer spread, queue position or fill certainty. Issue #48 independently owns execution and reconciliation.
