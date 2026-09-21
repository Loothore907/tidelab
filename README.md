# TideLab

A personal, multi-venue systematic market research and paper-trading project. Created 2026-09-10; research-platform direction approved 2026-09-16.

## Decision

Build a venue- and product-agnostic research core around canonical market data, versioned strategies, deterministic replay, explicit execution models, complete experiment records, and reconciled accounting. Coinbase Advanced Trade BTC-USD is the first reference fixture because it provides a tractable public-data starting point; it is not TideLab's permanent market boundary.

The economic objective is to discover whether any strategy, combined with a feasible execution environment, has positive expectancy after realistic costs and can eventually support useful income within a defined loss budget. Backtests select candidates; immutable forward tests evaluate them on newly arriving data. No profitable strategy or regular income capability has been demonstrated.

Initial work remains public-data and simulation only. No exchange credentials, deposits, paid infrastructure, live trading, or external account operation are authorized.

## Project documents

- [Core plan and assumptions](docs/PLAN.md)
- [Strategy research protocol](docs/STRATEGY_RESEARCH.md)
- [Exchange, access, and deployment decisions](docs/ARCHITECTURE.md)
- [Roadmap and evaluation gates](docs/ROADMAP.md)
- [Current handoff and next task](HANDOFF.md)
- [Agent working instructions](AGENTS.md)

## Current state

TL-001 is implemented and locally validated on the feature branch: canonical instrument/capability/event contracts, a restart-safe SQLite store, public Coinbase product and closed-hourly-bar synchronization, public WebSocket observation capture, and gap/duplicate/freshness reporting. See [the validation report](docs/evidence/TL-001-VALIDATION.md).

A 30-day probe found that the unauthenticated public candle endpoint returned only the latest 349 closed hourly bars from this environment and did not satisfy older requested windows. TideLab reports the missing periods instead of filling or hiding them. A longer historical source or accumulated archive is required before serious historical evaluation.

This folder is registered as the local Codex project TideLab and is now a local Git repository. No GitHub remote, issue, PR, remote CI result, private account integration, or deployment exists yet. Venue eligibility, fees, private API access, and live operation remain unverified.

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

Choose the GitHub owner and public/private visibility. Then create the remote, owning TL-001 issue, and PR; run exact-head CI before integration. TL-002 strategy or paper-broker scope has not started.
