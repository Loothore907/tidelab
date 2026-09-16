# Handoff

Updated 2026-09-16. Research-platform scope approved; implementation not started.

## Decisions carried forward

TideLab is an evidence-controlled, multi-venue strategy research platform. The economic goal is to identify positive expectancy after realistic execution costs and then determine whether any validated edge and available capital could support useful income. Engineering and learning are valuable outcomes but are not substitutes for trading evidence.

Coinbase Advanced Trade BTC-USD remains the first public-data fixture and the initial hourly trend hypothesis remains the first baseline experiment. Neither defines the permanent scope. The core will use canonical research contracts, capability-aware venue/product adapters, versioned strategies, deterministic replay, a complete experiment registry, independent risk decisions, and reconciled accounting. Later candidates may include centralized crypto, event contracts, or Solana markets only through separate research and eligibility gates.

Execution modes are explicit: simulated, advisory/manual, and automated. Historical and forward evaluation share strategy and risk semantics; venue-specific data, order, transaction, fee, expiry, and settlement behavior remains native behind adapters. No live orders, leverage, paid services, account access, or exchange credentials are authorized. MCP is optional reporting later. No edge is established.

The user lives in Alaska and has a stale Coinbase account and prior Solana DeFi experience. They prefer mock trades then small trades, and spending contingent on evidence. Their potential $500-$1,000 monthly budget is not current authorization. Live capital and loss tolerance remain unknown.

## Completed and verified

- Created README, plan, architecture decisions, roadmap, and agent guidance.
- Approved and documented the venue-agnostic research core, strategy protocol, execution modes, and second-adapter portability gate.
- Registered this folder as the local Codex project TideLab.
- Reviewed current official Coinbase API documentation and Codex project documentation.
- Successfully read public BTC-USD metadata without authentication; see ARCHITECTURE.md for evidence and limitations.
- Parent workspace is not a Git repository. No inherited repository changes exist in this new folder. No Git remote/CI status exists to report.

## Next actions and owners

1. User/Codex: choose repository owner, visibility, and integration scope before remote creation. Planning files currently remain a non-repository deliverable.
2. Codex, upon implementation instruction: implement TL-001 only, following AGENTS.md and the roadmap. Build the canonical data contracts and Coinbase BTC-USD reference adapter without speculative additional adapters.
3. Codex, in later authorized slices: implement the shared strategy/execution contract, ledger, experiment registry, historical evaluation, and immutable forward-paper runner before any live work.
4. User, before any private access: recover or establish the chosen account directly and verify residence, product eligibility, current fees, API terms, and intended permissions. Never paste keys, recovery phrases, passwords, or identity documents into chat.

No process is running. No account was accessed. No trade, paid service, GitHub issue, PR, repository, or deployment was created. Source files and runtime do not yet exist.
