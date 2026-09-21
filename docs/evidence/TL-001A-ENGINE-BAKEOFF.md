# TL-001A NautilusTrader bakeoff: synthetic replay checkpoint

Status: partial checkpoint, 2026-09-21. Issue [#2](https://github.com/Loothore907/tidelab/issues/2) remains open. This is not engine adoption, a strategy evaluation, or permission for live operation.

## Candidate and boundary

- Candidate: `nautilus-trader==2.0.0rc5`, an upstream release candidate, isolated in `requirements.bakeoff.lock`; TideLab's normal runtime dependencies do not include it.
- Upstream tag: [`v2.0.0rc5`](https://github.com/nautechsystems/nautilus_trader/releases/tag/v2.0.0rc5), resolving on 2026-09-21 to source commit `1b0a49d2792a9432a3aca3fcb617ce7a630d905e`.
- Installed wheel: Windows x64, CPython 3.12; package metadata reports `LGPL-3.0-only`. No source was vendored or patched.
- This candidate was chosen for a compatibility probe, not because a release candidate is suitable for a production commitment. Upstream's [v2 migration roadmap](https://github.com/nautechsystems/nautilus_trader/issues/4042) describes significant v1/v2 API changes. Re-evaluate version, maintenance, licensing, and distribution obligations before adoption.
- The probe uses only `SIM:BTC-USDT` synthetic prices, a simulated venue, and an observer strategy that submits zero orders. It makes no market-data request, account connection, or real-data publication.

## Reproduction

On Python 3.12 in a fresh, isolated environment, install `requirements.lock` and `requirements.bakeoff.lock`, install TideLab editable with `--no-deps`, then run `python -m pytest tests/test_nautilus_bakeoff.py`. The optional dependency is deliberately absent from ordinary runtime setup. CI has an independent Windows `engine-bakeoff` job.

Local result on 2026-09-21: five probe tests passed; the combined suite with the optional dependency installed passed 20 tests. This is local evidence, not a remote-CI claim.

## Observed behavior

- A canonical TideLab `MarketEvent` at the **start** of a closed hourly interval maps to a Nautilus `Bar` with `ts_event` at the **end** of that interval; conversion never silently makes an open bar strategy-ready.
- The converter rejects non-synthetic sources, open bars, non-UTC starts, gaps, duplicates, out-of-order hours, early receipt, invalid OHLCV, and excess synthetic instrument precision. Original event IDs and a stable fixture ID remain outside the engine objects for provenance.
- The engine delivered five synthetic bars in timestamp order to one strategy callback. A 2-versus-3-bar moving-average signal skeleton produced `warming, warming, long, cash, cash` both inside the engine and in sequential evaluation. Two independent runs returned identical reported evidence. No orders were submitted.

## Not yet demonstrated; required before TL-001A completion

- Identical *operational* strategy behavior under historical and forward-paper clocks, including restart and timer behavior. The current sequential comparison shares the signal function but is not a forward-paper runner.
- Fee, spread, slippage, quantity rounding, partial/missed/rejected fills, portfolio/cash/inventory accounting, and reconciliation after interruption or ambiguous order state.
- A complete experiment identity covering engine/source, TideLab code/config, allowed input data, cost model, and every trial; source event IDs alone are not sufficient.
- Replaceability through public extension points, Windows/Linux portability, migration stability, and packaged-distribution obligations under LGPL-3.0 and upstream trademark policy.
- LEAN comparison only if a critical Nautilus requirement fails. No such failure has been established by this small probe.

No profitability, realistic execution, or live safety conclusion follows from this checkpoint. The public [Nautilus backtesting guide](https://nautilustrader.io/docs/latest/concepts/backtesting/data-and-venues/) notes that bars cannot establish intrabar path, spread, depth, or queue position; later execution tests must make these assumptions explicit.
