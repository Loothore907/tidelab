# TideLab context map

This is a navigation map, not a second source of authority. For a fresh session, read `AGENTS.md` and `HANDOFF.md`, then verify the active branch, remote refs, open issues/PRs, reviews, and exact-head CI. The repo-local `tidelab-context` skill and `node scripts/tidelab-context.mjs current` provide a bounded committed-HEAD orientation; neither sees provider replies or uncommitted content.

| Question | First source | Then inspect |
| --- | --- | --- |
| What is authorized and prohibited? | `AGENTS.md` | The applicable roadmap gate and fresh user instruction |
| Where do we resume? | `HANDOFF.md` | Current GitHub issues/PRs, reviews, exact-head checks, and working diff |
| What is the product hypothesis and economic test? | `README.md`, `docs/PLAN.md` | `docs/STRATEGY_RESEARCH.md` for experiment discipline |
| What sequence and acceptance gates apply? | `docs/ROADMAP.md` | Owning issue and the slice's current evidence |
| How are venues, modes, and risk separated? | `docs/ARCHITECTURE.md` | `src/tidelab/domain.py` and tests for implemented behavior |
| What can be open-sourced or published? | `docs/OPEN_SOURCE_AND_PUBLICATION.md` | `docs/evidence/` for dated rights findings; provider terms/replies for fresh authority |
| What did TL-001 actually validate? | `docs/evidence/TL-001-VALIDATION.md` | `src/tidelab/` and `tests/` for code-level proof |

## Implementation areas

- `src/tidelab/domain.py`, `config.py`: canonical market, capability, and configuration contracts.
- `src/tidelab/coinbase.py`, `stream.py`: bounded public reference-adapter ingestion and observations; not an approved strategy-data source.
- `src/tidelab/storage.py`, `service.py`, `cli.py`, `__main__.py`: local persistence, orchestration, and entry points.
- `tests/`: fixture-based behavioral checks; `.github/workflows/ci.yml`: remote check definition. Passing local tests does not imply exact-head CI passed.
- `docs/evidence/`: dated observations and bakeoff/preflight reports. A branch's unmerged evidence will not appear on `main` until integration.

## Active research streams at this handoff

- [TL-001A decision](decisions/TL-001A-INITIAL-ENGINE-SELECTION.md) / [closed issue #2](https://github.com/Loothore907/tidelab/issues/2): pinned LEAN is selected for the first synthetic historical/local-paper integration. [TL-002 issue #48](https://github.com/Loothore907/tidelab/issues/48) now has a [pinned LEAN H1 report/account handoff](evidence/TL-002-H1-LEAN-REPORT-HANDOFF.md), [costed synthetic execution/trial accounting](evidence/TL-002-H1-CONSERVATIVE-EXECUTION-TRIAL-ACCOUNTING.md), a [private exact-source development runner](evidence/TL-002-H1-PRIVATE-DEVELOPMENT-RUNNER.md), and [independent private review plus guarded validation](evidence/TL-002-H1-PRIVATE-REVIEW-VALIDATION-GATE.md). [H1 v1](experiments/H1-V1-PREREGISTRATION.md) fixes the rule and evaluation plan. Development output stays local; untouched evaluation remains unopened. External broker finality and packaging remain separate. Start at the engine decision, these TL-002 reports, and `scripts/lean_fallback/`.
- [Issue #3](https://github.com/Loothore907/tidelab/issues/3) / [OKX historical selection](evidence/TL-001B-OKX-HISTORICAL-20260924.md) / [earlier options](evidence/TL-001B-DATA-OPTIONS-20260924.md): OKX BTC-USDT monthly/daily archives are locally validated for personal historical research. Their one-to-two-day delay cannot serve an on-time H1 paper decision, so the forward source remains open. Kraken is no longer a schedule dependency; Bitstamp's rights selection was reversed. One Gemini inquiry was sent; its fee, exact depth, and research scope remain unresolved in the bounded correspondence search. Public real-data artifacts are separately gated.
- [Merged PR #10](https://github.com/Loothore907/tidelab/pull/10) introduced this context map and handoff. Later decisions supersede its initial state; verify the current decision records and remote state.

For questions outside these paths, start with a short `search-docs`, `decision`, `evidence`, or `impact` query. Open its cited lines and nearby context before acting. The map can become stale; current repository and provider state must be checked live.
