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

Planning workspace only: no application, running bot, Git repository, remote, issues, or CI yet. Public BTC-USD product access was successfully checked from this machine. The design now permits later centralized spot, event-contract, and on-chain adapters without pretending their execution and settlement semantics are interchangeable. Venue eligibility, fees, private API access, and live operation remain unverified.

This folder is registered as the local Codex project TideLab. It remains a non-repository planning workspace until repository ownership, visibility, and integration authority are selected.

## First implementation task

Read AGENTS.md and HANDOFF.md. Establish repository ownership and integration scope, then build only TL-001: the canonical public-data foundation, Coinbase BTC-USD reference adapter, and validation report. Define narrow portability seams but do not implement additional venue adapters, strategy execution, credentials, or orders in this slice.
