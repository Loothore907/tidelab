# TideLab

A personal, multi-venue systematic market research and paper-trading project. Created 2026-09-10; research-platform direction approved 2026-09-16.

## Decision

Build a venue- and product-agnostic research core around canonical market data, versioned strategies, deterministic replay, explicit execution models, complete experiment records, and reconciled accounting. Coinbase Advanced Trade BTC-USD is the first reference fixture because it provides a tractable public-data starting point; it is not TideLab's permanent market boundary.

TideLab is licensed under Apache-2.0. [TL-001A selected pinned LEAN](docs/decisions/TL-001A-INITIAL-ENGINE-SELECTION.md) as the initial synthetic historical and local paper integration target. The engine is not yet an installed TideLab runtime or a production paper system. TideLab remains independent and will not default to an upstream fork.

The economic objective is to discover whether any market-and-strategy candidate, combined with a feasible execution environment, has positive expectancy after realistic costs and can eventually support useful income within a defined loss budget. TideLab should screen an objectively defined, affordable market universe rather than ask the owner to nominate promising pairs. Record screened and rejected candidates and every strategy trial; backtests nominate candidates, while immutable forward tests evaluate them on newly arriving data. BTC and the frozen H1 hypothesis are initial research fixtures, not a selected opportunity. No cross-market scanner, profitable strategy, or regular income capability has been demonstrated.

Initial work remains public-data and simulation only. No exchange credentials, deposits, paid infrastructure, live trading, or external account operation are authorized.

Open API access alone does not establish research or publication rights. Coinbase remains a bounded technical fixture; the selected OKX archive supports local scripted historical research and retention under its personal-use terms. Public real-data artifacts are optional and checked separately.

[OKX BTC-USDT spot archives](docs/evidence/TL-001B-OKX-HISTORICAL-20260924.md) are now selected for **local historical research**: 28,344 contiguous hourly bars were validated through a delayed daily archive. They are local ignored data, not a timely paper feed or permission to publish real-data results. TL-001B remains open for a timely forward source.

## Project documents

- [Core plan and assumptions](docs/PLAN.md)
- [Strategy research protocol](docs/STRATEGY_RESEARCH.md)
- [Frozen H1 v1 research specification](docs/experiments/H1-V1-PREREGISTRATION.md)
- [Exchange, access, and deployment decisions](docs/ARCHITECTURE.md)
- [Roadmap and evaluation gates](docs/ROADMAP.md)
- [Open-source and publication policy](docs/OPEN_SOURCE_AND_PUBLICATION.md)
- [TL-001A synthetic engine checkpoint](docs/evidence/TL-001A-ENGINE-BAKEOFF.md)
- [TL-002 synthetic paper intent barrier](docs/evidence/TL-002-PAPER-INTENT-BARRIER.md)
- [TL-002 synthetic local order reconciliation](docs/evidence/TL-002-SYNTHETIC-LOCAL-RECONCILIATION.md)
- [TL-002 synthetic LEAN intent and account join](docs/evidence/TL-002-LEAN-SYNTHETIC-INTENT-JOIN.md)
- [TL-002 synthetic forward sell and two-order ledger](docs/evidence/TL-002-LEAN-FORWARD-SELL-LEDGER.md)
- [TL-002 synthetic paper product-rule gate](docs/evidence/TL-002-PAPER-PRODUCT-RULES.md)
- [TL-002 synthetic H1 local report join](docs/evidence/TL-002-H1-LOCAL-REPORT-JOIN.md)
- [TL-001A engine decision map and reconnect probe](docs/evidence/TL-001A-ENGINE-DECISION-MAP.md)
- [TL-001A synthetic running-engine reconciliation](docs/evidence/TL-001A-LEAN-RUNNING-RECONCILIATION.md)
- [TL-001A synthetic H1 strategy and risk parity](docs/evidence/TL-001A-LEAN-H1-RISK-PARITY.md)
- [TL-001A synthetic correction and concurrent-order boundaries](docs/evidence/TL-001A-LEAN-CORRECTION-CONCURRENCY.md)
- [TL-001A synthetic correction journal and LEAN recovery boundary](docs/evidence/TL-001A-LEAN-CORRECTION-JOURNAL.md)
- [TL-001A synthetic broker snapshot restart race](docs/evidence/TL-001A-LEAN-SNAPSHOT-RESTART-RACE.md)
- [TL-001A synthetic submission handoff boundary](docs/evidence/TL-001A-LEAN-SUBMISSION-HANDOFF.md)
- [TL-001A synthetic forward-paper submission barrier](docs/evidence/TL-001A-LEAN-PAPER-SUBMISSION-BARRIER.md)
- [TL-001A synthetic paper intent and ambiguous-submission recovery](docs/evidence/TL-001A-LEAN-PAPER-INTENT-RECOVERY.md)
- [TL-001A synthetic paper intent and LEAN restart join](docs/evidence/TL-001A-LEAN-PAPER-RESTART-JOIN.md)
- [TL-001A synthetic conservative fill and joined paper workflow](docs/evidence/TL-001A-LEAN-JOINED-PAPER-WORKFLOW.md)
- [TL-001A portable experiment identity and hybrid foundation review](docs/evidence/TL-001A-HYBRID-FOUNDATION-DECISION.md)
- [TL-001A joined synthetic selection gate](docs/evidence/TL-001A-LEAN-SELECTION-GATE.md)
- [TL-001A initial engine decision](docs/decisions/TL-001A-INITIAL-ENGINE-SELECTION.md)
- [TL-001B data-rights preflight](docs/evidence/TL-001B-DATA-RIGHTS-PREFLIGHT.md)
- [TL-001B free and paid data options](docs/evidence/TL-001B-DATA-OPTIONS-20260924.md)
- [TL-001B selected OKX historical source and delayed-feed limit](docs/evidence/TL-001B-OKX-HISTORICAL-20260924.md)
- [TL-001B bounded cross-market source screen](docs/evidence/TL-001B-OKX-CROSS-MARKET-SCREEN-20260924.md)
- [Current handoff and next task](HANDOFF.md)
- [Project context map](docs/CONTEXT_MAP.md) and [repo-local context skill](.agents/skills/tidelab-context/SKILL.md)
- [Agent working instructions](AGENTS.md)
- [Apache-2.0 license](LICENSE) and [project notice](NOTICE)

## Current state

TL-001 is implemented and integrated: canonical instrument/capability/event contracts, a restart-safe SQLite store, public Coinbase product and closed-hourly-bar synchronization, public WebSocket observation capture, and gap/duplicate/freshness reporting. See [the validation report](docs/evidence/TL-001-VALIDATION.md).

A 30-day probe found that the unauthenticated public candle endpoint returned only the latest 349 closed hourly bars from this environment and did not satisfy older requested windows. TideLab reports the missing periods instead of filling or hiding them. Current Coinbase market-data terms also create research-use and publication-rights concerns. A source with adequate historical depth and supportable local research rights is required before serious evaluation; public real-data presentation is a separate decision.

This folder is registered as the local Codex project TideLab. The public [GitHub repository](https://github.com/Loothore907/tidelab) contains TL-001 via [PR #5](https://github.com/Loothore907/tidelab/pull/5); the Apache/open-source decision is recorded in [PR #6](https://github.com/Loothore907/tidelab/pull/6). No private account integration or deployment exists. Venue eligibility, fees, private API access, and live operation remain unverified.

## Local setup

Requires Python 3.11 or newer. The validated environment used Python 3.12.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --requirement requirements.lock
.\.venv\Scripts\python.exe -m pip install --editable . --no-deps
Copy-Item config.example.toml config.toml
```

`config.toml`, local databases, and generated artifacts are ignored. The example configuration contains no secrets.

## Commands

These commands document the completed TL-001 fixture. Pending TL-001B, do not use them to acquire new Coinbase data for strategy development or automated analysis. Use synthetic or otherwise rights-cleared fixtures for the engine bakeoff.

```powershell
# Initialize local storage and refresh point-in-time product rules.
.\.venv\Scripts\python.exe -m tidelab --config config.toml init
.\.venv\Scripts\python.exe -m tidelab --config config.toml metadata

# Synchronize a UTC-aligned, end-exclusive range of closed hourly bars.
.\.venv\Scripts\python.exe -m tidelab --config config.toml sync `
  --start 2026-09-15T00:00:00Z --end 2026-09-16T00:00:00Z

# Report missing bars, restart duplicates, and freshness for the same range.
.\.venv\Scripts\python.exe -m tidelab --config config.toml report `
  --start 2026-09-15T00:00:00Z --end 2026-09-16T00:00:00Z

# Capture bounded public five-minute candle observations and heartbeats.
.\.venv\Scripts\python.exe -m tidelab --config config.toml stream --seconds 10

# Exercise metadata, first/restart sync, stream capture, and reporting together.
.\.venv\Scripts\python.exe -m tidelab --config config.toml smoke --hours 24 --stream-seconds 10
```

The WebSocket candle channel provides live five-minute updates. TideLab keeps those as observations; strategy-ready hourly bars are admitted only after the public REST interval is closed.

### Local OKX historical import

Download an older BTC-USDT spot candlestick ZIP from the [official OKX historical-data portal](https://www.okx.com/en-us/historical-data), then import the local file. This command reads the ZIP and writes only to a local SQLite database; it does not call an exchange API or require an account. The archive day runs from 16:00 UTC on the prior calendar date through 15:59 UTC on the named date. Monthly and daily ZIPs use `YYYY-MM` and `YYYY-MM-DD` respectively.

```powershell
.\.venv\Scripts\python.exe -m tidelab import-okx `
  --file data\okx\BTC-USDT-candlesticks-2024-01.zip `
  --symbol BTC-USDT --period 2024-01 `
  --database data\okx\research.sqlite3
```

The importer requires complete minute coverage, builds UTC hourly bars, skips identical duplicate rows, and stops if an archive changes a stored bar. Downloaded ZIPs and the database remain ignored local files. OKX releases the archive after a delay, so it cannot supply on-time forward paper decisions. See the [source and rights decision](docs/evidence/TL-001B-OKX-HISTORICAL-20260924.md) before using or sharing derived material.

To prepare a bounded local signal-input file for LEAN's existing `TideLabH1Bar` custom reader, export exact-source closed hourly bars. The command requires every hour in the selected UTC interval and writes a new directory of two-column CSVs under ignored `data/`. Row timestamps are UTC; filenames follow LEAN's New York subscription date. An export made before this correction must be regenerated for LEAN. Its close-only format can check signal delivery; it cannot model fills, spread, or fees.

```powershell
.\.venv\Scripts\python.exe -m tidelab export-lean-h1 `
  --database data\okx\research.sqlite3 --venue okx `
  --instrument okx:BTC-USDT --source okx.historical_archive.candlesticks.1m `
  --start 2024-01-01T00:00:00Z --end 2024-02-01T00:00:00Z `
  --output data\lean_h1\jan2024
```

Keep these real-data-derived CSVs local. This prepares the reader's file format; it does not run LEAN. The [H1 v1 specification](docs/experiments/H1-V1-PREREGISTRATION.md) lists the remaining strategy, accounting, and trial gates before a real-data performance run.

## Next research gates

TL-001A [engine evaluation](https://github.com/Loothore907/tidelab/issues/2) selected pinned LEAN for the bounded initial integration. TL-001B [data-rights gate](https://github.com/Loothore907/tidelab/issues/3) remains open for an on-time forward source; OKX monthly/daily archives are selected for local historical research only. TL-002 has bounded synthetic intent, LEAN local report, and one forward sell check; full strategy and runtime integration remain open.
