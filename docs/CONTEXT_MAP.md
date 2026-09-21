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

- [Issue #2](https://github.com/Loothore907/tidelab/issues/2) / [draft PR #7](https://github.com/Loothore907/tidelab/pull/7): TL-001A synthetic NautilusTrader engine bakeoff. Adoption, realistic fills, and restart/reconciliation are not decided.
- [Issue #3](https://github.com/Loothore907/tidelab/issues/3) / [draft PR #8](https://github.com/Loothore907/tidelab/pull/8): TL-001B data rights and technical coverage. Kraken permission inquiry sent and its automated intake request answered; substantive rights reply pending. Full raw-dataset publication is optional, but research use and each public derived artifact need a supportable basis.
- [Issue #9](https://github.com/Loothore907/tidelab/issues/9) / [draft PR #10](https://github.com/Loothore907/tidelab/pull/10): this context map and handoff. It does not adopt a data source, engine, strategy, or live execution mode.

For questions outside these paths, start with a short `search-docs`, `decision`, `evidence`, or `impact` query. Open its cited lines and nearby context before acting. The map can become stale; current repository and provider state must be checked live.
