# TL-001B research-data and publication preflight

Status: research preflight updated 2026-09-22; [issue #3](https://github.com/Loothore907/tidelab/issues/3) remains open. No real-data source is approved, selected, downloaded, or published by this document. This is a product/licensing risk inventory, not legal advice.

## Owner-approved operating rule

- Publish TideLab code, methods, failed trials, and project-authored synthetic fixtures under the project's Apache-2.0 license.
- Seek permission to publish real-data-derived charts and results, but do **not** require TideLab to host downloadable raw real-market data. A reproducible acquisition recipe plus permitted provenance/hashes is acceptable.
- Spend $0 now; return with a specific, capped proposal before any paid provider or service. BTC-USD and Coinbase are replaceable if depth or rights fail.
- Keep the published software independently usable with synthetic fixtures. Neither a data license nor a software license implies the other.
- The owner's 2026-09-22 priority is a sound dataset for local historical and forward-paper testing. Public raw datasets, real-data charts, reports, and video are optional outputs, not prerequisites for local research. Select and validate research use, automated analysis, retention, and technical coverage first; assess each public artifact independently before publishing it.

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

The statuses below describe only the cited terms and published access descriptions; they are **not** a blanket legal determination. No candidate yet passes the local research selection gate. Public presentation rights remain a separate decision.

| Source | Historical/forward technical evidence | Research/automated analysis | Retention and public chart/report/video rights | Cost | Disposition |
| --- | --- | --- | --- | --- | --- |
| Coinbase public candles | TL-001's 30-day request admitted only 349 of 720 hourly bars; the recent feed works as a bounded fixture. | The [Market Data Terms](https://www.coinbase.com/legal/market_data) give limited personal/research permission but also restrict use to develop/validate/improve algorithms or other automated systems. Application to TideLab needs clarification. | The same terms restrict dissemination of market data and derived charts, analytics, and research absent prior express written consent. Retention and proposed video rights are not established. | Public endpoint needs no paid account for the existing fixture. | **No-go for new strategy-data acquisition or public derived artifacts** pending clarification/permission. |
| Kraken downloadable OHLCVT/trades and spot feed | [Kraken says](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data) its downloadable OHLCVT spans pairs from their first trade through 2026-06-30; the archive includes 60-minute intervals, manifest, and checksums. The complete archive is split into five roughly 2 GB parts; per-pair extraction has not been tried. Its [time-and-sales archive](https://support.kraken.com/articles/360047543791-downloadable-historical-market-data-time-and-sales-) is another lead, but its current coverage needs verification. The [public OHLC endpoint](https://docs.kraken.com/api-reference/market-data/get-ohlc-data) returns at most 720 recent entries and includes an open final bar; continuity for our exact pair is unverified. | The [Kraken API guide](https://docs-legacy.kraken.com/api/docs/guides/global-intro/) calls out prior permission for some uses, including non-personal commercial use. [Global terms](https://www.kraken.com/legal/global-terms) permit content use for one's own benefit but also contain broad automation restrictions. How these apply to TideLab's scripted personal research and archive retention needs a substantive answer. | Specific public derived-chart/report/video rights are not established. They may be omitted without blocking a private research dataset. | Downloads are described as publicly available; ongoing access or permission costs are unknown. | **Lead for local research, not yet selected.** Resolve scripted research/retention scope, then validate a bounded sample; do not publish derived artifacts absent separate clearance. |
| Binance public-data archive | Binance's [own archive guide](https://github.com/binance/binance-public-data) describes daily/monthly downloadable market-data files. Exact BTC pair, depth, data quality, and forward-feed continuity are unverified. | Access to a public archive is not an affirmative license for automated strategy research; no applicable grant was verified in this preflight. | The archive guide did not supply a verified grant to republish raw data, derived charts/reports, or video. The GitHub repository's software/license metadata must not be treated as a data license. | Published archive access appears free; no paid service authorized. | **Unresolved rights.** No strategy acquisition or public artifact from it yet. |
| Third-party CC0-labeled crypto candles | One [community repository](https://github.com/Speirsy11/crypto-dataset/blob/main/DATA_LICENSE) declares its candle files CC0 and describes Binance-origin data. Coverage, corrections, and a forward source are unverified. | The uploader's declaration does not establish that upstream exchange rights permit the license grant or the proposed automated use. | Redistribution claim exists, but chain of rights and chart/video use are unverified. | No spend indicated. | **Not cleared by the uploader label alone.** Require provenance/rights review before any use. |

## Selection gate and next bounded checks

Two decisions are independent. **Local research selection** requires a supportable basis for scripted research, retention, and automated analysis plus adequate historical depth, data quality, forward continuity, and zero current spend. **Public presentation** is checked only for each proposed raw or derived artifact; an unclear or denied publication right means omit that artifact, not discard an otherwise usable private research source. Unknown rights for the actual use still fail closed.

Kraken's [archive notes](https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data) say only intervals with trades appear; gaps must not be silently filled. The published complete archive currently ends at 2026-06-30 and quarterly increments lag forward operation, so an API/feed would be needed for newly arriving data. The archives provide bars and trades, not a demonstrated historical bid/ask-quote series. TideLab's synthetic execution probe showed that assuming executable liquidity from bars alone can misstate fills; spread and quote-depth validation remain separate technical questions even if Kraken grants the required rights.

1. Choose a historical and forward source only after verifying the **specific** instrument, UTC timestamps, interval boundaries, gaps/revisions, depth across market regimes, and continued access. The published Kraken archive depth is a lead, not a validated TideLab dataset.
2. Save dated copies or stable references to the exact provider terms and any written permission. Resolve research, algorithmic use, retention, and re-acquisition for the local workflow. Track public derived charts/reports/video and commercial presentation separately; unknown publication rights prohibit those outputs, not private research.
3. If permission is needed, send a precise provider inquiry that names TideLab's local research, open-source code, possible public charts/reports, monetized case-study video, and lack of raw-data redistribution. Do not presume silence means consent.
4. Once local research use and retention have a supportable basis, acquire only a bounded sample, record provenance/hashes privately, and validate coverage/quality before implementing an adapter. A change of source or material terms creates a new experiment input.
5. If no zero-cost source clears local research rights and technical coverage, keep TL-001B open and return with a concrete source pivot or capped paid-license proposal. Do not turn optional public presentation rights into the dataset selection criterion.

## Provider clarification request — sent, substantive reply pending

Kraken is the first provider asked because its published archives address the historical-depth problem. The owner approved outreach on 2026-09-21. A clarification request was sent that day to `marketdata@kraken.com`, the contact identified in [Kraken's API guidance](https://docs-legacy.kraken.com/api/docs/guides/global-intro/). It describes TideLab as an independent Apache-2.0 research-software project that may later publish a monetized educational process video, with **no raw Kraken data redistributed by TideLab**. It asks for written answers covering historical archives and public forward feeds:

1. May a personal researcher download, retain, and use the archives and forward feed in scripted algorithmic backtests and forward-paper evaluation, including automated analysis?
2. May TideLab publish derived price charts, trade plots, performance tables, experiment reports, screenshots, and monetized video segments? Specify attribution, delay, display, and volume limits.
3. May TideLab publish acquisition scripts, source URLs, checksums, schemas, and reproduction instructions so each user obtains data directly from Kraken, without TideLab hosting raw files?
4. Would later automated live trading using Kraken data require separate permission or a commercial agreement? That use would have its own approval gate.
5. Are historical top-of-book bid/ask quotes available, with coverage and terms sufficient for spread and fill research?

An answer that only confirms public download access would **not** clear algorithmic research or public derived artifacts. Preserve the reply and applicable terms as dated evidence before changing this gate.

Kraken's automated intake reply on 2026-09-21 asked for a company, partnership rationale, and operating country before routing the request. We replied that TideLab is an independent US-based open-source project, not a registered company or proposed business partnership, and asked for routing to the market-data licensing or legal team. This is an intake acknowledgment, not a substantive rights answer or permission. Do not infer approval from the automated response or silence.

Full raw-dataset publication is optional. The intended public story is the documented research and build process, with any real-data-derived artifact separately cleared or replaced by a permissible illustration. A permission denial would trigger another source or a different public artifact, not a silent waiver of the research-use gate.

No Kraken account was accessed, no market-data file was downloaded, and no data-derived result was published for this preflight. The substantive rights inquiry is pending; it is not permission.
