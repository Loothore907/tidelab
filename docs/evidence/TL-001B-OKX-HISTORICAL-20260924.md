# TL-001B: OKX historical-data selection and delayed-feed boundary

Date: 2026-09-24. Owning issue: [#3](https://github.com/Loothore907/tidelab/issues/3). This is a local research-data decision, not a trading or publication approval.

## Recommendation and rights basis

Use OKX's free **BTC-USDT spot candlestick archive** as TideLab's first local historical research source. The [U.S. historical-data terms](https://www.okx.com/en-us/help/historicaldata-terms-and-conditions) expressly allow personal possession, retention, and use of downloaded data to develop one's own strategy, subject to a revocable license. The [U.S. archive page](https://www.okx.com/en-us/historical-data) lists candlesticks from July 2023. No account, key, or payment was used to download the files in this check. Keep the files and all real-data-derived output local and out of Git. Public results, charts, screenshots, video, commercial use, and a later live venue require separate review. This is a documented operating basis for this personal local use, not a determination about every future use.

The [OKX API agreement](https://www.okx.com/en-us/help/okx-api-agreement) treats public endpoints separately and defines a user as a verified account holder. TideLab did not access the OKX API or an account. **The archive is delayed:** the portal says the newest two days are unavailable, with each archive day running from 16:00 UTC to 15:59 UTC the next day. Therefore this source supports historical testing and delayed prospective observation, but not an on-time H1 paper order decision. Issue #3 remains open for a timely forward source and exact execution-market cost/eligibility checks.

## Bounded comparison

| Option | Finding | Decision |
| --- | --- | --- |
| OKX archive | Explicit personal retention and own-strategy development; accountless download; BTC-USDT spot files validated through 2026-09-23; one-to-two-day delay | **Select for local historical research and delayed observation** |
| Gemini public API | [Agreement](https://www.gemini.com/legal/market-data-agreement) expressly allows personal/internal storage and price analysis, but its linked fee schedule was inaccessible and exact hourly depth is unverified | Best next timely-feed candidate; existing inquiry is pending; no acquisition or fee assumed |
| Kraken archive/API | [Deep archive](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data), but API/bot guidance and broad terms leave TideLab's scripted retention scope unresolved | No acquisition; existing rights inquiry remains pending |
| Bitstamp public API | Technically deep, but no documented local retention/analysis grant was found | Previous selection was [reversed](TL-001B-BITSTAMP-RIGHTS-CORRECTION-20260924.md) |
| Coin Metrics Community | Public catalog listed long Kraken BTC/USD coverage; actual community hourly-candle requests returned HTTP 403 on 2026-09-24 | Catalog availability did not equal free data access |
| CryptoDataDownload | [Noncommercial license and backtesting use](https://www.cryptodatadownload.com/data/) are published, but [terms](https://www.cryptodatadownload.com/terms-of-use/) reserve upstream rights concerns and files update daily | No advantage over the first-party OKX archive for this slice |

## Private technical evidence

The OKX portal supplied one January 2024 sample, then monthly BTC-USDT ZIPs for July 2023 through August 2026 and daily ZIPs for September 1–23, 2026. The verified URL shape is the official `static.okx.com/cdn/okex/traderecords/candlesticks/{monthly|daily}/...` archive; use the portal rather than assuming filenames for other products. All 61 files are under ignored `data/okx/`; no price row is committed or published.

The importer validates the exact member name, CSV schema, symbol, UTC minute alignment, archive period, decimal/OHLC range, chronological continuity, and full period coverage before committing hourly bars. It rolls 60 consecutive one-minute rows into a closed UTC hourly bar and records each archive SHA-256 with the bar. It never fills a missing minute. Reimports are idempotent; a changed hourly value under the same identity stops for review instead of silently replacing a research input.

Observed local import: **1,700,640 unique minute rows; 56 field-identical repeated minute rows; 28,344 hourly bars; zero missing hours** from `2023-06-30T16:00:00Z` to `2026-09-23T16:00:00Z` (exclusive end). The duplicates were 11 rows in October 2023 and 45 in June 2024. January 2024 sample ZIP SHA-256: `ad4975aaaf414fc7dd22a71bc9cb0e2bdff7d7fc0026b36df5fd4cd93bbf674c`. The portal's monthly files used `confirm=0` even for old closed intervals, while the daily sample used `confirm=1`; closure is inferred only from the complete, sufficiently aged archive period, not from that flag. These are file/store integrity observations, not a strategy result or a claim that source prices are accurate.

## Integration and remaining gates

`tidelab import-okx --file <local-zip> --symbol BTC-USDT --period YYYY-MM --database data/okx/research.sqlite3` imports a monthly ZIP; `--period YYYY-MM-DD` imports a daily ZIP. The command prints only counts, bounds, and a hash. It does not fetch data, submit an order, run a strategy, or publish any real-data output. The existing local SQLite store now holds the validated sample for later TL-003 work. The importer is a historical source boundary; TL-002's synthetic LEAN/order-recovery work remains separate.

Before the first real-data strategy result, freeze H1's rule, cost assumptions, chronological partitions, benchmark, trial budget, and pass criteria. Do not infer fills, bid/ask spread, or actual executable liquidity from OHLCV bars. Before an on-time forward H1 paper runner, select and validate a timely source with supportable local scripted use, retention, exact-pair continuity, and effective cost. The existing Gemini inquiry is the next narrow check. A later execution venue must be evaluated against its own product rules, eligibility, fees, and prices; OKX BTC-USDT history is not a proof of Coinbase BTC-USD execution.
