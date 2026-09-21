# TL-001B research-data and publication preflight

Status: research preflight on 2026-09-21; [issue #3](https://github.com/Loothore907/tidelab/issues/3) remains open. No real-data source is approved, selected, downloaded, or published by this document. This is a product/licensing risk inventory, not legal advice.

## Owner-approved operating rule

- Publish TideLab code, methods, failed trials, and project-authored synthetic fixtures under the project's Apache-2.0 license.
- Seek permission to publish real-data-derived charts and results, but do **not** require TideLab to host downloadable raw real-market data. A reproducible acquisition recipe plus permitted provenance/hashes is acceptable.
- Spend $0 now; return with a specific, capped proposal before any paid provider or service. BTC-USD and Coinbase are replaceable if depth or rights fail.
- Keep the published software independently usable with synthetic fixtures. Neither a data license nor a software license implies the other.

## Exact artifacts requiring rights decisions

| Artifact | Intended use | Current publication rule |
| --- | --- | --- |
| Raw hourly bars and later quote/trade/depth observations | Local historical/forward research | Keep out of Git/public artifacts unless the particular source grants redistribution. Record source, acquisition time, revisions, and local hashes when lawful. |
| Synthetic OHLCV fixtures, simulated fills, and failure cases | Open tests and engine demonstrations | Project-authored; publish with TideLab code. Never imply they are real market observations. |
| Acquisition/normalization code and configuration examples | Reproduction | Publish without credentials, private endpoints, restricted data, or provider-owned documentation copied into the repository. |
| Experiment manifests and parameter/trial registry | Audit of all attempts, including failures | Publish only after checking that no restricted inputs, account information, or provider-controlled derived data are embedded. |
| Equity curves, price charts, trade plots, performance tables, screenshots, and video frames | Public case study | Treat as potentially derived market data; require source-specific permission or a clearly permissible substitute before publication. |
| Forward-paper reports | Evidence of simulated operation | Separate from live results; publication requires a check of underlying data and derived-work terms. |

An hourly trend test might start with bars, but claims about spread, intrabar fill path, liquidity, or queue position require more granular, separately licensed data or conservative assumptions. Source depth and legal scope are independent gates.

## Candidate source screen

The statuses below describe only the cited terms and published access descriptions; they are **not** a blanket legal determination. No candidate yet passes all intended uses.

| Source | Historical/forward technical evidence | Research/automated analysis | Retention and public chart/report/video rights | Cost | Disposition |
| --- | --- | --- | --- | --- | --- |
| Coinbase public candles | TL-001's 30-day request admitted only 349 of 720 hourly bars; the recent feed works as a bounded fixture. | The [Market Data Terms](https://www.coinbase.com/legal/market_data) give limited personal/research permission but also restrict use to develop/validate/improve algorithms or other automated systems. Application to TideLab needs clarification. | The same terms restrict dissemination of market data and derived charts, analytics, and research absent prior express written consent. Retention and proposed video rights are not established. | Public endpoint needs no paid account for the existing fixture. | **No-go for new strategy-data acquisition or public derived artifacts** pending clarification/permission. |
| Kraken downloadable OHLCVT/trades and spot feed | [Kraken says](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data) its downloadable OHLCVT spans pairs from their first trade through 2026-06-30; the archive includes 60-minute intervals, manifest, and checksums. Its [time-and-sales archive](https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales-) has public trades through the same date. [Public spot APIs](https://docs.kraken.com/api/) exist, but completeness/forward continuity for our exact pair are unverified. | The [Kraken API guide](https://docs-legacy.kraken.com/api/docs/guides/global-intro/) says some uses, including non-personal commercial use of public market data, need prior permission. The intended monetizable public research use must be clarified. | [Global terms](https://www.kraken.com/legal/global-terms) reserve rights in content, including pricing data, and direct other uses to prior permission. Specific public derived-chart/video and retention rights are not established. | Downloads are described as publicly available; ongoing access or commercial permission costs are unknown. | **Technically promising, rights not cleared.** Do not acquire for the strategy or publish derived artifacts until permitted scope is documented. |
| Binance public-data archive | Binance's [own archive guide](https://github.com/binance/binance-public-data) describes daily/monthly downloadable market-data files. Exact BTC pair, depth, data quality, and forward-feed continuity are unverified. | Access to a public archive is not an affirmative license for automated strategy research; no applicable grant was verified in this preflight. | The archive guide did not supply a verified grant to republish raw data, derived charts/reports, or video. The GitHub repository's software/license metadata must not be treated as a data license. | Published archive access appears free; no paid service authorized. | **Unresolved rights.** No strategy acquisition or public artifact from it yet. |
| Third-party CC0-labeled crypto candles | One [community repository](https://github.com/Speirsy11/crypto-dataset/blob/main/DATA_LICENSE) declares its candle files CC0 and describes Binance-origin data. Coverage, corrections, and a forward source are unverified. | The uploader's declaration does not establish that upstream exchange rights permit the license grant or the proposed automated use. | Redistribution claim exists, but chain of rights and chart/video use are unverified. | No spend indicated. | **Not cleared by the uploader label alone.** Require provenance/rights review before any use. |

## Selection gate and next bounded checks

Kraken's [archive notes](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data) say only intervals with trades appear; gaps must not be silently filled. The published complete archive currently ends at 2026-06-30 and quarterly increments lag forward operation, so an API/feed would be needed for newly arriving data. The archives provide bars and trades, not a demonstrated historical bid/ask-quote series. TideLab's synthetic execution probe showed that assuming executable liquidity from bars alone can misstate fills; spread and quote-depth validation remain separate technical questions even if Kraken grants the required rights.

1. Choose a historical and forward source only after verifying the **specific** instrument, UTC timestamps, interval boundaries, gaps/revisions, depth across market regimes, and continued access. The published Kraken archive depth is a lead, not a validated TideLab dataset.
2. Save dated copies or stable references to the exact provider terms and any written permission. Evaluate research, algorithmic use, retention, re-acquisition, reproducibility, public derived charts/reports/video, and commercial/monetized presentation separately. An unknown field fails closed.
3. If permission is needed, prepare a precise provider inquiry that names TideLab's local research, open-source code, public charts/reports, monetized case-study video, and lack of raw-data redistribution. Do not presume silence means consent.
4. Once a source passes, acquire only a bounded sample, record provenance/hashes privately, and validate coverage/quality before implementing an adapter. A change of source or material terms creates a new experiment input.
5. If no zero-cost source clears both technical and publication gates, keep TL-001B open and return with a concrete rights/market pivot or capped paid-license proposal. Do not quietly lower the publication standard.

## Provider clarification brief — not sent

Kraken is the first provider worth asking because its published archives address the historical-depth problem. Before any contact, the owner should approve external outreach. A concise inquiry should identify TideLab as a public Apache-2.0 research-software project that may later publish a monetized process/results video, with **no raw Kraken data redistributed by TideLab**. Request written answers for the proposed BTC/USD spot historical OHLCVT and trade archives plus public forward feeds:

1. May a personal researcher download, retain, and use the archives and forward feed in scripted algorithmic backtests and forward-paper evaluation, including automated analysis?
2. May TideLab publish derived price charts, trade plots, performance tables, experiment reports, screenshots, and monetized video segments? Specify attribution, delay, display, and volume limits.
3. May TideLab publish acquisition scripts, source URLs, checksums, schemas, and reproduction instructions so each user obtains data directly from Kraken, without TideLab hosting raw files?
4. Is a separate commercial or market-data agreement required for any of those uses? If so, what scope, price, duration, termination, and redistribution restrictions apply?
5. Do the answers cover both historical archives and newly arriving public API/WebSocket data, and do any third-party rights narrow the grant?

An answer that only confirms public download access would **not** clear algorithmic research or public derived artifacts. Preserve the reply and applicable terms as dated evidence before changing this gate.

No account was accessed, no market-data file was downloaded, and no publication or provider contact was made for this preflight.
