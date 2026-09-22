# Handoff

Updated 2026-09-22. TL-001 was integrated through PR #5, the Apache/open-source decision through PR #6, the context atlas through PR #10, and partial TL-001A/TL-001B checkpoints through PRs #7/#8. Issues #2 and #3 remain separate open gates before TL-002. Use `docs/CONTEXT_MAP.md` and the repo-local `tidelab-context` skill for bounded orientation; they do not replace fresh GitHub and provider checks.

## Decisions carried forward

TideLab is an evidence-controlled, multi-venue strategy research platform. The economic goal is to identify positive expectancy after realistic execution costs and then determine whether any validated edge and available capital could support useful income. Engineering and learning are valuable outcomes but are not substitutes for trading evidence.

Coinbase Advanced Trade BTC-USD remains the first public-data fixture and the initial hourly trend hypothesis remains the first baseline experiment. Neither defines the permanent scope or public research-data source. The core will use canonical research contracts, capability-aware venue/product adapters, versioned strategies, deterministic replay, a complete experiment registry, independent risk decisions, and reconciled accounting. Later candidates may include centralized crypto, event contracts, or Solana markets only through separate research and eligibility gates.

TideLab-authored work is Apache-2.0 and is intended for eventual public release. The project will adopt proven open-source engine infrastructure before building commodity backtest, broker, portfolio, and ledger machinery. NautilusTrader is the first bounded candidate, not yet an adopted dependency; LEAN is the fallback before any custom engine authorization. Prefer a pinned, replaceable dependency and upstream fixes over vendoring or a permanent fork. Third-party licenses, source obligations, contributor agreements, and trademarks remain separate gates.

Coinbase's current market-data terms create a material research-use and public-reproducibility concern in addition to the observed 349-hour depth. Pending TL-001B, do not fetch new Coinbase data for strategy development or automated analysis, and keep existing data and derived artifacts local. The owner's 2026-09-22 priority is a sufficiently deep dataset for local scripted research and forward-paper testing, with supportable research, retention, and automated-analysis rights. Public raw datasets and real-data-derived charts/reports/video are optional and assessed separately before publication.

The owner approved a narrow Kraken market-data rights inquiry on 2026-09-21, and it was sent to the contact in Kraken's API guidance. Kraken's automated intake reply asked for company, partnership rationale, and country; we answered truthfully that TideLab is an independent US-based project seeking rights clarification, not a proposed partnership. The owner supplied that automated reply again on 2026-09-22; no newer mailbox response was verified in this session. Sending these messages does not grant permission, select Kraken, authorize spending, or authorize acquisition of real strategy data.

Capture lightweight, sanitized evidence throughout development and assemble any polished process/results video later from versioned decisions, experiments, failures, and forward reports. Recording/editing software is deliberately unselected and no purchase or publication is authorized.

Execution modes are explicit: simulated, advisory/manual, and automated. Historical and forward evaluation share strategy and risk semantics; venue-specific data, order, transaction, fee, expiry, and settlement behavior remains native behind adapters. No live orders, leverage, paid services, account access, or exchange credentials are authorized. MCP is optional reporting later. No edge is established.

The user lives in Alaska and has a stale Coinbase account and prior Solana DeFi experience. They prefer mock trades then small trades, and spending contingent on evidence. Their potential $500-$1,000 monthly budget is not current authorization. Live capital and loss tolerance remain unknown.

The owner is exploring a broader autonomous research process: candidate discovery, registered tests, paper observation, approved implementation, and explicit stop/retire behavior. This is a product direction under discussion, not authorization for an adaptive live-trading agent. Preset deterministic risk and execution controls remain separate from optional AI assistance.

## Completed and verified

- Created README, plan, architecture decisions, roadmap, and agent guidance.
- Approved and documented the venue-agnostic research core, strategy protocol, execution modes, and second-adapter portability gate.
- Registered this folder as the local Codex project TideLab.
- Created the public Git repository; the TL-001 implementation and subsequent foundation decisions are integrated on protected `main`.
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
- Public remote `Loothore907/tidelab` and owning issues #2/#3 exist. TL-001 passed exact-head CI at `16cf5d4` and merged through PR #5. PR #6 and context-atlas PR #10 are merged. Protected `main` requires strict `test` CI, resolved conversations, and no force push or deletion.
- [PR #7](https://github.com/Loothore907/tidelab/pull/7) merged at `89df27e` after exact-head `test` and `engine-bakeoff` CI passed for `5fa504b`. Local optional-engine suite passed 26/26. Pinned NautilusTrader 2.0.0rc5 handled synthetic replay, later quotes, fees, fills, and cash/inventory reconciliation. A same-process streaming pause retained a `SUBMITTED` order with no premature fill and resumed to the uninterrupted result. This does not prove durable process-loss recovery, realistic fills, or engine adoption; issue #2 remains open.
- [PR #8](https://github.com/Loothore907/tidelab/pull/8) merged at `76d5e2f` after exact-head `test` CI passed for `3ed714a`. It records the owner-prioritized local research gate and the technical lead from Kraken's historical OHLCVT archive through 2026-06-30. The archive has not been downloaded or validated for the exact pair; scripted research/retention scope is unresolved. Public real-data artifacts are optional and separately gated. Issue #3 remains open.

## Next actions and owners

1. In [issue #3](https://github.com/Loothore907/tidelab/issues/3) / TL-001B, check for a substantive Kraken rights reply. Resolve scripted personal research, retention, and automated-analysis use independently of optional publication. Then acquire only a bounded permitted sample and test exact-pair coverage, gaps, revisions, and forward continuity. If no reply, screen other zero-cost sources without acquiring restricted strategy data or contacting another provider without scope.
2. In [issue #2](https://github.com/Loothore907/tidelab/issues/2) / TL-001A, test durable pending-order recovery across process loss or identify a critical public-extension gap in the pinned release. Same-process streaming continuity and full replay of a completed run are insufficient. Do not adopt, fork, or distribute NautilusTrader merely because the current probes pass.
3. Only after TL-001A and TL-001B, implement TL-002 as TideLab integration/policy work on the adopted engine, with custom infrastructure limited to documented critical gaps. Freeze H1's exact rules, cost model, data partitions, benchmarks, variant budget, and pass criteria before evaluating results. Before any private access, the owner handles account recovery directly and verifies eligibility, fees, API terms, and intended permissions. Never paste credentials or identity documents into chat.

No private account was accessed. No trade, paid service, recording software, public dataset, video, or deployment was created. Runtime databases and validation configuration are local ignored artifacts. Kraken's automated intake request was answered; a substantive rights response and grant remain unknown.

## Next-session pickup

Start with `AGENTS.md`, this handoff, and `node scripts/tidelab-context.mjs current` in the active TideLab checkout. Verify the current branch/working tree, fresh `origin/main`, issues #2/#3, reviews, exact-head CI, and any new provider reply. Treat the context output as committed-HEAD navigation only. First pursue a substantive TL-001B local-research source decision if Kraken has answered; otherwise advance the synthetic TL-001A process-loss recovery gate. Keep the gates separate. Do not acquire restricted strategy data, contact another provider, spend, access accounts, or trade without the relevant authority. Report observed facts, unknowns, head/checks, and the next owner decision.
