# Handoff

Updated 2026-09-21. TL-001 implemented and locally validated; public remote, owning issues, and two draft PRs created. Neither PR is merged.

## Decisions carried forward

TideLab is an evidence-controlled, multi-venue strategy research platform. The economic goal is to identify positive expectancy after realistic execution costs and then determine whether any validated edge and available capital could support useful income. Engineering and learning are valuable outcomes but are not substitutes for trading evidence.

Coinbase Advanced Trade BTC-USD remains the first public-data fixture and the initial hourly trend hypothesis remains the first baseline experiment. Neither defines the permanent scope or public research-data source. The core will use canonical research contracts, capability-aware venue/product adapters, versioned strategies, deterministic replay, a complete experiment registry, independent risk decisions, and reconciled accounting. Later candidates may include centralized crypto, event contracts, or Solana markets only through separate research and eligibility gates.

TideLab-authored work is Apache-2.0 and is intended for eventual public release. The project will adopt proven open-source engine infrastructure before building commodity backtest, broker, portfolio, and ledger machinery. NautilusTrader is the first bounded candidate, not yet an adopted dependency; LEAN is the fallback before any custom engine authorization. Prefer a pinned, replaceable dependency and upstream fixes over vendoring or a permanent fork. Third-party licenses, source obligations, contributor agreements, and trademarks remain separate gates.

Coinbase's current market-data terms create a material research-use and public-reproducibility concern in addition to the observed 349-hour depth. Pending TL-001B, do not fetch new Coinbase data for strategy development or automated analysis, and keep existing data and derived artifacts local. TL-001B must select a sufficiently deep source with documented research, retention, redistribution, derived-work, charting/video, and automated-analysis rights.

Capture lightweight, sanitized evidence throughout development and assemble any polished process/results video later from versioned decisions, experiments, failures, and forward reports. Recording/editing software is deliberately unselected and no purchase or publication is authorized.

Execution modes are explicit: simulated, advisory/manual, and automated. Historical and forward evaluation share strategy and risk semantics; venue-specific data, order, transaction, fee, expiry, and settlement behavior remains native behind adapters. No live orders, leverage, paid services, account access, or exchange credentials are authorized. MCP is optional reporting later. No edge is established.

The user lives in Alaska and has a stale Coinbase account and prior Solana DeFi experience. They prefer mock trades then small trades, and spending contingent on evidence. Their potential $500-$1,000 monthly budget is not current authorization. Live capital and loss tolerance remain unknown.

## Completed and verified

- Created README, plan, architecture decisions, roadmap, and agent guidance.
- Approved and documented the venue-agnostic research core, strategy protocol, execution modes, and second-adapter portability gate.
- Registered this folder as the local Codex project TideLab.
- Created a local Git repository with approved planning documents on `main`; TL-001 work is isolated on `feat/tl-001-market-data`.
- Implemented versioned instrument, capability, and market-event contracts; Coinbase public product/hourly-candle parsing; bounded retries; restart-safe SQLite storage; ingestion/stream records; and gap/duplicate/freshness reporting.
- Implemented bounded public WebSocket capture for five-minute candle observations and heartbeats. Live updates remain distinct from closed hourly strategy bars.
- Added pinned Python dependencies, example no-secret configuration, CLI commands, fixture tests, and a GitHub Actions workflow for eventual exact-head CI.
- Passed 15 local tests on Python 3.12.14, including interrupted-ingestion recovery and rejection of out-of-window upstream data.
- Completed a bounded read-only smoke test: 24/24 closed hourly bars with no gaps, a second sync inserted zero and recognized all 24 duplicates, and a 10-second WebSocket session received 14 messages including 10 heartbeats and 101 candle observations with no connection-sequence gaps. See `docs/evidence/TL-001-VALIDATION.md`.
- Probed 30 requested days of public hourly candles. The endpoint returned 1,050 objects across three requests, but after strict per-window admission only the latest 349 of 720 requested bars were valid; 371 earlier hours remained explicitly missing. Longer historical depth is not established.
- Reviewed current official Coinbase API documentation and Codex project documentation.
- Successfully read public BTC-USD metadata without authentication; see ARCHITECTURE.md for evidence and limitations.
- Added the Apache License 2.0 and TideLab notice; documented dependency-license, trademark, data-rights, and public-release gates in `docs/OPEN_SOURCE_AND_PUBLICATION.md`.
- Added TL-001A for a pinned NautilusTrader-first engine bakeoff and TL-001B for a rights-cleared historical/forward data-source decision before TL-002.
- Chose evidence-first process capture with later video assembly; no recording/editing product has been selected or purchased.
- Public remote `Loothore907/tidelab` and owning issues #1-#4 now exist. TL-001 is in draft PR #5 against `main`; the open-source decision is stacked in draft PR #6 against the TL-001 branch. PR #5's exact-head CI passed at `16cf5d4`; PR #6's result must be rechecked after this handoff update. Local success and remote CI are distinct.

## Next actions and owners

1. Review TL-001 in issue #1 and draft PR #5 against its exact head; integrate only when the applicable checks/review and merge authority are satisfied.
2. Retarget stacked draft PR #6 to `main` after #5 integrates, then recheck its exact diff/head, CI, and notices before integration. Issue #4 owns this documentation/licensing slice.
3. In separate issue #2 / TL-001A, evaluate one pinned NautilusTrader release against the recorded acceptance criteria. Do not adopt, fork, or distribute it merely because the initial API fits.
4. In separate issue #3 / TL-001B, inventory required artifacts and compare rights-cleared historical/forward data sources. Do not acquire new Coinbase strategy data or publish Coinbase data/derived artifacts while the relevant rights are unresolved.
5. Only after TL-001A and TL-001B, implement TL-002 as TideLab integration/policy work on the adopted engine, with custom infrastructure limited to documented critical gaps.
6. Before any private access, the user handles account recovery directly and verifies residence, product eligibility, current fees, API terms, and intended permissions. Never paste keys, recovery phrases, passwords, or identity documents into chat.

No private account was accessed. No trade, paid service, recording software, public dataset, video, or deployment was created. Runtime databases and validation configuration are local ignored artifacts. The public remote, four issues, and two draft PRs are the only new external artifacts.
