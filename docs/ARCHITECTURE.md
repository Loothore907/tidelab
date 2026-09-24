# Research platform, access, and deployment

## ADR-001: One reference venue, portable core

Choose Coinbase Advanced Trade BTC-USD for the initial public-data fixture because it is tractable and offers documented REST and streaming access. This is a practical implementation starting point, not a claim that Coinbase, BTC, centralized spot, or hourly trend has the highest expectancy.

The fixture does not establish that Coinbase data may be retained, redistributed, charted, or published in the form TideLab requires. Data rights and historical depth are independent selection gates. A different source may replace Coinbase for research and publication while the TL-001 adapter remains a conformance fixture.

The research core must not contain Coinbase product identifiers, fee assumptions, order types, or availability rules. Venue adapters normalize common facts while preserving native payloads and semantics when normalization would hide material behavior. A second structurally different read-only/paper adapter must prove this portability before any live pilot.

Different products remain genuinely different. Event contracts add expiry, outcome criteria, and settlement. On-chain swaps add wallet signing, routing, transaction construction, network and priority fees, confirmation/expiration, and MEV. Equities would add sessions and corporate actions. Do not force these into a lowest-common-denominator spot-order model.

Hosting does not change the user's Alaska residency. Local research is acceptable; a future US cloud region is an uptime choice. Do not use hosting to circumvent geographic restrictions. Exact legal/product eligibility must be checked for the selected service, not inferred from public API availability.

## ADR-002: Direct venue APIs; optional MCP for inspection

API is the exchange connection. MCP can expose a selected set of application operations to an assistant; an MCP exchange connector would usually call an API underneath. It does not remove fees, credentials, exchange rules, or execution failure modes.

TideLab calls each supported venue through a dedicated adapter. Keep scheduled research and any future trading loop independent of chat sessions, model availability, model usage costs, and tool approval round trips. Deterministic versioned rules generate target positions or trade intents; an independent risk check validates them; a venue-specific planner and adapter handle execution.

An optional later MCP server may expose sanitized status, positions, experiment summaries, and journal queries. Do not expose secrets or raw order submission. Any later control operations require authentication, audit records, and explicit design review.

## ADR-003: Capability-aware contracts

The shared domain includes versioned forms of:

- `Instrument` and `CapabilityProfile`
- `MarketEvent` with exchange event time and local receipt time
- `StrategyManifest`, `TargetPosition`, and `TradeIntent`
- `RiskDecision`
- `OrderState`, `Fill`, `Cashflow`, and `Settlement`
- `Experiment`, including data/configuration/source identity and every attempted variant

A strategy declares required data and capabilities, such as continuous bars, order-book depth, expiry, settlement, short exposure, or on-chain routing. A venue adapter declares supported capabilities. An unsupported or ambiguous match fails closed. Product rules and costs are runtime/versioned data, never strategy constants.

Strategies share the same implementation in historical replay and forward operation. Backtest and paper environments inject a deterministic clock, recorded market stream, and simulated execution adapter. Live-capable adapters, if ever approved, implement the same intent and state contracts while retaining native reconciliation behavior.

## ADR-004: Explicit execution modes

- `simulated`: historical replay or forward-paper operation produces modeled fills and never accesses a private account.
- `advisory`: TideLab produces a time-limited, auditable proposal; the user decides whether to execute manually, and any actual fill is entered/reconciled separately. A proposal is not a fill.
- `automated`: an adapter may submit an approved intent only after separate live authority, least-privilege credential setup, venue eligibility review, and all live gates pass.

Analysis, strategy generation, and optional AI assistance never bypass deterministic risk controls or mutate a live strategy. Each strategy/version is immutable during its evaluation window.

## ADR-005: Adopt before building an engine

TideLab owns hypotheses, strategy manifests, experiment/trial accounting, promotion gates, capability requirements, reporting, and public evidence. It does not assume that value comes from rebuilding event dispatch, backtesting, portfolio accounting, simulated execution, reconciliation, or standard venue adapters.

The [TL-001A bakeoff selected pinned LEAN](decisions/TL-001A-INITIAL-ENGINE-SELECTION.md) for the first synthetic historical/local-paper integration. Use its public interfaces behind replaceable TideLab contracts. Keep TideLab's strategy/risk policy, cost assumptions, paper authority, and evidence separable; do not vendor, patch, or fork engine internals as the default integration cost. NautilusTrader was evaluated first and retains a tested backed external-data recovery gap at the pinned release.

## ADR-006: Apache-2.0 project with explicit dependency boundaries

TideLab-authored source and documentation use Apache-2.0. This does not relicense dependencies. Pinned LEAN is Apache-2.0; a future bundled release must preserve its license and applicable notices, identify changed engine files if any, and inventory transitive packages. A future NautilusTrader-backed distribution would additionally require the applicable LGPL source/replacement route and its independent-project trademark disclaimer. Upstream contributions are a separate choice subject to that project's rules.

Source-only development against a separately installed, pinned dependency is preferred. Container or executable distribution adds a release checklist for third-party source, licenses, notices, and replacement instructions. See `OPEN_SOURCE_AND_PUBLICATION.md`.

## ADR-007: Rights-cleared reproducibility and evidence-first publication

Public endpoint access is not a license to publish data or derived artifacts. Each data source must declare retention, research, reproducibility, redistribution, charting, video, and automated-analysis rights before its outputs can enter a public release. Restricted local artifacts remain ignored and unpublished; public tests use synthetic or expressly redistributable fixtures.

Capture durable, sanitized evidence during development: decisions, source/config/data identities, failures, test results, experiment manifests, forward reports, and selected milestone visuals. Produce a polished video later from that record, after a validated result exists. Recording and editing software remain unselected and no purchase is authorized.

## Access phases

1. Completed bounded public Coinbase Advanced fixture work for product rules, recent bars, and live-data characterization. Keep resulting artifacts local. Pending TL-001B, pause new Coinbase acquisition for strategy development or automated analysis except any separately approved minimal terms/technical clarification.
2. Completed synthetic engine bakeoff: pinned NautilusTrader first, then LEAN after the backed external-data recovery gap. Selected pinned LEAN for initial integration; no private account access or external order submission.
3. Rights-cleared historical simulation with complete experiment records and venue-specific cost assumptions.
4. Forward-paper operation with newly arriving data and no private account access.
5. A second structurally different public/read-only or simulated adapter to prove the core contracts without adding live authority.
6. Advisory/manual execution only if separately requested, with time-limited proposals and fill reconciliation. Private read access, if needed, requires a user-created least-privilege key and a fresh permissions review.
7. Only after explicit live approval: a dedicated minimally funded account/portfolio or wallet, current eligibility/API-terms verification, tested recovery, and credentials stored outside chat, Git, reports, logs, and model context. Use view/trade only where supported; never grant transfer/withdrawal permission merely for strategy execution.

## Application design

Market adapter -> canonical timestamped event store -> feature view -> versioned strategy -> target position/trade intent -> independent risk check -> venue execution planner -> simulated/advisory/automated adapter -> append-only ledger -> reports.

A future live broker implements the same intent interface with venue-specific state and reconciliation. Paper and live configurations and databases stay separate; missing or invalid configuration fails closed. Prefer adopted engine components where they satisfy TideLab's contracts; custom components require a documented gap from TL-001A. No strategy runner, private adapter, or live broker is included in the first implementation slice.

- Python for the TideLab control layer with pinned dependencies; verify the adopted engine's supported versions before integration.
- SQLite remains valid for TideLab's current single-writer fixture state and journals. Do not force the adopted engine into TideLab's storage choice; require exportable, versioned experiment and accounting evidence instead. Use decimal arithmetic for money and quantities.
- UTC timestamps for market/event storage; optionally display America/Anchorage time.
- Record exchange event time, local receipt time, product metadata version, strategy/config version, and source commit for each experiment.
- Preserve raw/native records or content hashes sufficient to audit normalization and replay decisions.
- Record every strategy trial, including rejected and failed variants. Untouched evaluation data cannot become a new development set after inspection without declaring a new experiment generation.
- CLI/status report first. A dashboard is optional after the recorder and reports work.
- Avoid Kubernetes, dedicated blockchain nodes, paid signal feeds, and continuous LLM calls in the initial design.

## Headless requirements

- One active trading worker, enforced with a lock/lease; prevent duplicate execution during restart or deployment.
- Persist order intents and unique client identifiers before submission. Timeout means unknown status: reconcile before retrying, never blindly resubmit.
- On restart, reconcile balances, orders, and fills before allowing entries. Idempotently process duplicate/out-of-order events.
- Heartbeats, freshness checks, gap detection, bounded retries, rate-limit handling, clock checks, and explicit unavailable status.
- Pause entries on inconsistent state; define management of existing positions separately. Do not cancel protective exits indiscriminately.
- Test disconnects, crashes around submission, partial fills, rejection, database recovery, and emergency pause. Exchange-held protections must be evaluated before unattended live operation; local stops do not work during host outages.
- Future deployment: small Linux VM, non-root process supervised by systemd, persistent disk, tested backups, secret injection, log rotation, and an external health monitor. Provider and price remain unselected; no deployment has occurred.

## Verified sources and evidence

Coinbase fixture, checked 2026-09-10:

- [Advanced REST endpoints](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/rest-api)
- [Advanced WebSocket overview](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/websocket/websocket-overview)
- [API key permissions](https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/data-api/get-api-key-permissions)
- [Static sandbox](https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sandbox)
- [Coinbase US agreement](https://www.coinbase.com/legal/user_agreement/united_states) and [licenses](https://www.coinbase.com/legal/licenses)
- [Coinbase Market Data Terms of Use](https://www.coinbase.com/legal/market_data), reviewed 2026-09-21; the page reported a 2026-08-07 update and broad restrictions on redistribution and derived works

An unauthenticated GET to https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD succeeded from this machine. It reported status online, trading_disabled false, base_min_size 0.00000001, quote_min_size 1, base_increment 0.00000001, and quote_increment 0.01. This is a point-in-time public response, not proof of account eligibility or a permanent trading minimum. Refresh rules and validate complete order constraints at runtime.

Open-source engine and publication sources were first reviewed 2026-09-21. The later [TL-001A decision](decisions/TL-001A-INITIAL-ENGINE-SELECTION.md) selects a pinned integration target; no engine runtime is installed in TideLab:

- [NautilusTrader license](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE), [open-source policy](https://nautilustrader.io/legal/open-source-licensing/), [trademark policy](https://nautilustrader.io/legal/trademark-policy/), [backtesting concepts](https://nautilustrader.io/docs/latest/concepts/backtesting/), and [Coinbase integration](https://nautilustrader.io/docs/latest/integrations/coinbase/)
- [GNU license FAQ](https://www.gnu.org/licenses/gpl-faq.en.html) for LGPL distribution/linking context
- [QuantConnect LEAN](https://github.com/QuantConnect/Lean) as the selected bounded initial integration target

These sources support the bounded technical and licensing bakeoff. They do not establish production stack fitness, legal advice, an installed runtime, or permission to publish third-party data and derived artifacts.

Future-adapter feasibility reviewed 2026-09-16; no account access or integration was performed:

- [Kalshi API and SDK overview](https://docs.kalshi.com/sdks/overview) and [CFTC designation record](https://www.cftc.gov/IndustryOversight/IndustryFilings/TradingOrganizations/42993)
- [Robinhood Crypto Trading API](https://docs.robinhood.com/)
- [Solana transaction confirmation](https://solana.com/developers/cookbook/transactions/confirmation), [fees](https://solana.com/docs/core/fees), and [DeFi overview](https://solana.com/docs/defi)

These sources show technically distinct automation surfaces; they do not prove user eligibility, profitability, complete historical data, acceptable terms, or authorization to trade.
