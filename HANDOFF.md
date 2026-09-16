# Handoff

Updated 2026-09-16. TL-001 implemented and locally validated; remote integration not started.

## Decisions carried forward

TideLab is an evidence-controlled, multi-venue strategy research platform. The economic goal is to identify positive expectancy after realistic execution costs and then determine whether any validated edge and available capital could support useful income. Engineering and learning are valuable outcomes but are not substitutes for trading evidence.

Coinbase Advanced Trade BTC-USD remains the first public-data fixture and the initial hourly trend hypothesis remains the first baseline experiment. Neither defines the permanent scope. The core will use canonical research contracts, capability-aware venue/product adapters, versioned strategies, deterministic replay, a complete experiment registry, independent risk decisions, and reconciled accounting. Later candidates may include centralized crypto, event contracts, or Solana markets only through separate research and eligibility gates.

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
- No Git remote, issue, PR, or remote CI result exists. Local success is not remote CI.

## Next actions and owners

1. User: choose GitHub owner and public/private visibility. The authenticated account is `Loothore907`; no remote was guessed or created.
2. Codex, once that choice is supplied: create the remote and TL-001 issue, push `main` and `feat/tl-001-market-data`, open a draft PR, inspect exact-head CI, and integrate only if authorized gates pass.
3. Codex: create an owning follow-up before TL-003 to establish a sufficiently long historical source or accumulated archive; the current public endpoint evidence is only 349 continuous recent hourly bars.
4. Codex, in a later authorized slice: begin TL-002 shared strategy/execution contracts and paper ledger. Do not fold it into the TL-001 integration.
5. User, before any private access: recover or establish the chosen account directly and verify residence, product eligibility, current fees, API terms, and intended permissions. Never paste keys, recovery phrases, passwords, or identity documents into chat.

No process is running. No private account was accessed. No trade, paid service, GitHub remote/issue/PR, or deployment was created. Runtime databases and validation configuration are local ignored artifacts.
