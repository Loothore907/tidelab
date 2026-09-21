# TideLab

A personal, multi-venue systematic market research and paper-trading project. Created 2026-09-10; research-platform direction approved 2026-09-16.

## Decision

Build a venue- and product-agnostic research core around canonical market data, versioned strategies, deterministic replay, explicit execution models, complete experiment records, and reconciled accounting. Coinbase Advanced Trade BTC-USD is the first reference fixture because it provides a tractable public-data starting point; it is not TideLab's permanent market boundary.

TideLab is licensed under Apache-2.0. It will adopt proven open-source engine components before building commodity trading infrastructure. NautilusTrader is the first engine candidate for a bounded compatibility bakeoff; it is not yet an adopted dependency. TideLab will remain an independent project and will not default to an upstream fork.

The economic objective is to discover whether any strategy, combined with a feasible execution environment, has positive expectancy after realistic costs and can eventually support useful income within a defined loss budget. Backtests select candidates; immutable forward tests evaluate them on newly arriving data. No profitable strategy or regular income capability has been demonstrated.

Initial work remains public-data and simulation only. No exchange credentials, deposits, paid infrastructure, live trading, or external account operation are authorized.

Open API access is not publication permission. Coinbase remains a bounded technical fixture while TideLab selects a data source whose retention, reproducibility, charting, and public-demonstration rights fit the intended open-source workflow.

## Project documents

- [Core plan and assumptions](docs/PLAN.md)
- [Strategy research protocol](docs/STRATEGY_RESEARCH.md)
- [Exchange, access, and deployment decisions](docs/ARCHITECTURE.md)
- [Roadmap and evaluation gates](docs/ROADMAP.md)
- [Open-source and publication policy](docs/OPEN_SOURCE_AND_PUBLICATION.md)
- [Current handoff and next task](HANDOFF.md)
- [Agent working instructions](AGENTS.md)
- [Apache-2.0 license](LICENSE) and [project notice](NOTICE)

## Current state

TL-001 is implemented and locally validated on the feature branch: canonical instrument/capability/event contracts, a restart-safe SQLite store, public Coinbase product and closed-hourly-bar synchronization, public WebSocket observation capture, and gap/duplicate/freshness reporting. See [the validation report](docs/evidence/TL-001-VALIDATION.md).

A 30-day probe found that the unauthenticated public candle endpoint returned only the latest 349 closed hourly bars from this environment and did not satisfy older requested windows. TideLab reports the missing periods instead of filling or hiding them. Current Coinbase market-data terms also create a publication-rights concern. A rights-cleared source with adequate historical depth is required before serious, publicly reproducible evaluation.

This folder is registered as the local Codex project TideLab. The public [GitHub repository](https://github.com/Loothore907/tidelab) now contains the planning baseline; TL-001 is under draft review in [PR #5](https://github.com/Loothore907/tidelab/pull/5), and the open-source decision is stacked in [PR #6](https://github.com/Loothore907/tidelab/pull/6). Neither slice is merged. No private account integration or deployment exists. Venue eligibility, fees, private API access, and live operation remain unverified.

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

## Current integration task

The public remote is now `Loothore907/tidelab`. Review and integrate TL-001 through [issue #1](https://github.com/Loothore907/tidelab/issues/1) and [draft PR #5](https://github.com/Loothore907/tidelab/pull/5) only after exact-head checks and review. Then retarget/recheck the stacked open-source decision in [issue #4](https://github.com/Loothore907/tidelab/issues/4) and [draft PR #6](https://github.com/Loothore907/tidelab/pull/6). TL-001A [engine evaluation](https://github.com/Loothore907/tidelab/issues/2) and TL-001B [data-rights gate](https://github.com/Loothore907/tidelab/issues/3) precede TL-002. TL-002 strategy integration has not started.
