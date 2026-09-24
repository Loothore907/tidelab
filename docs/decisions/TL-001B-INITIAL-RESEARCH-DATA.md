# TL-001B initial research data decision

Decision date: 2026-09-24. Owner issue: [#3](https://github.com/Loothore907/tidelab/issues/3).

## Decision and scope

Use Bitstamp's **public BTC/USD hourly OHLCV API** as TideLab's first real-data source for **local, noncommercial, scripted historical research and forward-paper observation**. Do not wait for Kraken's unanswered rights inquiry. Keep Bitstamp-specific data provenance and execution assumptions explicit; this is a first research instrument, not a permanent venue boundary or a trading-venue selection.

The rights basis is deliberately narrow. [Bitstamp's official API documentation](https://www.bitstamp.net/api/) calls this a public API, documents an unauthenticated OHLC endpoint with historical `start`/`end` parameters and a 1,000-row request limit, and says companies seeking commercial use of its exchange data must obtain a commercial Data License Agreement. We infer that local personal, noncommercial use of the public endpoint, including a retained private research copy and scripted analysis, is within the intended free use. The page does **not** explicitly grant retention or automated research rights. If this interpretation is challenged or TideLab's use becomes commercial, stop new acquisition and resolve the license before continuing. No Bitstamp market data or derived real-data charts, results, screenshots, or video may be committed, redistributed, or published under this decision. Any public artifact needs its own rights review. No account, fee, provider contact, or trade was involved.

The [CryptoDataDownload free archive](https://www.cryptodatadownload.com/data/) has a noncommercial license and deep advertised coverage, but its [terms](https://www.cryptodatadownload.com/terms-of-use/) expressly say it has not verified the data and cannot warrant third-party intellectual-property restrictions. It is not the source of this sample. [Gemini's agreement](https://www.gemini.com/legal/market-data-agreement) expressly permits personal analysis and storage, but acceptance of its linked market-data fee schedule is mandatory; that linked page was unavailable/404 in this review, and exact candle depth was not established. Neither was selected. Kraken remains an optional later comparison, not a dependency.

## Bounded technical verification

The official endpoint returned BTC/USD hourly rows for small probes around 2018-01-01, 2021-01-01, and 2026-09-23. `scripts/bitstamp_ohlc_sample.py` then acquired a private, Git-ignored UTC hourly sample from **2022-01-01 inclusive through 2026-09-01 exclusive**: 40,896 rows, exactly the expected hourly count, with no missing/duplicate interval or invalid OHLCV under the script's checks. SHA-256 of the local CSV: `4221d75f23a5ae2b13afd7903244b8df410b796cff9543c4bf563540055b86da`.

A separate **2026-09-01 through 2026-09-23 exclusive** bridge returned 528 of 528 expected hours with the same checks. This demonstrates that the same public REST source can bridge historical and recent closed hours; it does not prove an unattended forward collector or immutable forward trial. The files and manifests live only under ignored `data/`. No prices or raw rows are in this decision record.

The checks establish interval continuity and basic internal consistency, not independent price accuracy, correction policy, execution quality, spread, fee history, or depth of book. The source may revise past bars. Preserve the local sample hash and acquisition timestamp for experiment identity, use conservative cost/fill assumptions, and compare later snapshots before relying on corrections. A historical candle cannot establish a limit-order fill. No strategy was evaluated and no profitability evidence follows from this data acquisition.

## Next gate

TL-003 may prepare a frozen H1 protocol against the private Bitstamp sample, with an untouched period, trial budget, cost model, and benchmark fixed **before** opening strategy results. TL-002 still owns the incomplete general LEAN paper runtime. The first forward-paper experiment requires a durable closed-hour collector and reconciliation from this source; it is not supplied by this selection. Venue eligibility and real-account fees remain unverified and are irrelevant to this paper-only selection.
