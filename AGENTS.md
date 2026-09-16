# TideLab working instructions

Read README.md, HANDOFF.md, and docs/ROADMAP.md before changing scope. Preserve the user's global Git hygiene rules; these instructions supplement them.

## Scope and authority

- Current deliverable is the project plan. Implementation proceeds when requested, beginning with TL-001 public-data recording.
- Coinbase BTC-USD is the first reference fixture, not the product boundary. Keep the research core venue- and product-agnostic through explicit contracts and capabilities, but do not build unused adapters before their roadmap slice.
- Default to paper mode. Do not infer live trading, deposits, paid services, or account access authorization from interest in this project or a hypothetical budget.
- Never put credentials in chat, source, test fixtures, logs, reports, or Git. Public-data work must not require a funded account.
- Do not represent simulation as live performance, a sandbox as realistic execution, or a local check as remote CI.
- No model-dependent live trade loop or self-modifying live strategy. Optional AI assistance operates outside deterministic risk and execution controls.

## Engineering and research

- Keep exchange adapters, strategy, risk checks, broker, ledger, and reporting separable without premature distributed infrastructure.
- Share strategy and risk semantics between historical replay and forward operation. Change the clock, data source, and execution adapter rather than maintaining separate strategy implementations.
- Preserve venue-native data and behavior where normalization would hide expiry, settlement, routing, confirmation, fees, or order-state semantics. A capability declaration must fail closed when a strategy requires an unsupported feature.
- Use UTC, decimal monetary values, explicit product rules, versioned configurations, deterministic replay, and complete decision records.
- Test accounting invariants and failure recovery, including unknown order status and duplicate events. Never blindly retry ambiguous submissions.
- Preserve every failed experiment and generated variant. Freeze evaluation criteria and untouched periods before examining results; record changes as new experiments and count all trials when assessing evidence.
- Support simulated, advisory, and automated execution as distinct modes. Advisory output is a time-limited proposal that requires user execution and later fill reconciliation; automated execution always requires separate authority.
- Separate paper accounts/databases from future live operation. No live credentials or broker in the first slice.

## Git integration once a repository exists

Inspect guidance/handoff, branch, working tree, upstream, fresh remote refs, issues/PRs, findings, and exact-head CI. Preserve unrelated work and resolve inherited debt. Use issue-linked focused branches, coherent Conventional commits, and draft PRs. Respect existing authority and gates; do not reset, force-push, indiscriminately stage, or weaken checks.

At closeout, report head, issue/PR, local checks, remote CI, merge state, remaining changes, and blockers with an owning issue/next action. For this initial non-repository planning workspace, no artificial commit or PR is required.
