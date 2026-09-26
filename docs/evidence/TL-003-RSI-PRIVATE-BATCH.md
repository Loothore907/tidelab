# RSI v1: selected candidate through the shared historical backend

Owner: [#95](https://github.com/Loothore907/tidelab/issues/95). This slice implements the owner's explicitly approved source-attributed candidate and a single private exploratory batch. It is selected-strategy implementation and research evaluation, not candidate selection hidden inside foundation work. The immutable local proposal, approval receipt and selected intake v2 are under ignored `data/strategy_intake/`; they remain the authority for the exact private experiment.

## Source and interpretation

The source is QuantConnect LEAN's [RsiAlphaModel.py](https://github.com/QuantConnect/Lean/blob/88bce0fc6fe282378ee73c54cef1090d0d7a73ee/Algorithm.Framework/Alphas/RsiAlphaModel.py), [RelativeStrengthIndex.cs](https://github.com/QuantConnect/Lean/blob/88bce0fc6fe282378ee73c54cef1090d0d7a73ee/Indicators/RelativeStrengthIndex.cs), and [WilderMovingAverage.cs](https://github.com/QuantConnect/Lean/blob/88bce0fc6fe282378ee73c54cef1090d0d7a73ee/Indicators/WilderMovingAverage.cs), pinned at `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`. Copyright QuantConnect Corporation, Apache-2.0; see the pinned [license](https://github.com/QuantConnect/Lean/blob/88bce0fc6fe282378ee73c54cef1090d0d7a73ee/LICENSE). TideLab's Python algorithm is independently written from the documented behavior. This attribution grants neither data rights nor endorsement. Upstream code remains an external unmodified dependency.

The source alpha's daily directional insights, hysteresis reset bands, and insight expiry are not reproduced. The approved adaptation is hourly spot long/cash: RSI(14) strictly below 30 schedules entry while flat; strictly above 70 schedules exit while held. Equality holds. Entry commits 25% of signal-time cash, sized at the next open with fees/adverse movement and floored to 1e-8 units. No shorts, leverage, stop, rebalance or pyramiding. Terminal holdings are marked without forced sale. There is no source-backed profitability claim.

Package schema 2 adds only `rsi_wilder(period=14, lag=0)` to the existing bounded language; schema 1 meaning is unchanged. Native Wilder seeding and ten-decimal midpoint-even zero-loss handling are retained, including RSI 100 on flat inputs. Signals require 15 closes. The fixed private experiment uses 336 warmup closes. The shared replay handles timing/accounting; there is no second candidate-specific trading loop.

## Narrow private route

`scripts/rsi_private_batch.py` exposes `initialize`, `prepare`, and `run`, each requiring `--terms-reviewed-utc-date`. There are no caller-selected market/date/registry paths. The code binds the local proposal/approval/selected-record hashes, fixed markets/window/costs and 30 jobs. Missing private authority artifacts make a fresh clone fail closed.

Every action requires clean main matching fresh remote main and successful exact-head CI. A manually supplied current UTC date records an operator's fresh rights review; the command cannot prove that review or interpret changing terms. Independent review must check actual approval separately from hash/structure validation.

The canonical existing trial registry at `data/research_program/trials.sqlite3` gains immutable access events, not a parallel ledger. An external store anchor prevents silently recreating a missing established registry. One snapshot reservation precedes source price reads; one batch reservation precedes snapshot verification and replay. Failure consumes the relevant grant. No retry, later phase, alternate registry, acquisition, order, account or spend authority is provided. These local controls are audit/process safeguards, not security against an operator rewriting code and all local state.

Preparation copies only the exact declared hourly window from one read transaction, checks continuity/OHLCV/source/provenance, hashes referenced local archive bytes without parsing outside-window prices, closes/checkpoints the snapshot writer, and freezes a standalone snapshot hash plus row/plan/record/package identities. Monthly and daily importer provenance are supported. Batch reads are confined to this export. Artifacts and outcomes stay ignored/private.

Thirty ordered jobs comprise one fixed rule over five markets under baseline/stress costs, plus cash/passive benchmarks under both costs. The passive benchmark buys 25% at the first scored open, explicitly earlier than the first strategy fill opportunity. Existing history is exposed exploratory development; it is not a holdout. All prior studies remain separate and retained.

The frozen review gives missing/failed required scenarios priority (`incomplete`), then fewer than 20 baseline round trips (`inconclusive`), then the approved net/passive/stress/drawdown conditions (`eligible_for_deeper_review` or `not_nominated`). An incomplete batch blocks promotion; otherwise zero eligible outcomes stops v1 without tuning. Eligibility never triggers another trial. The private approval contains exact thresholds and budgets; no inferential edge or paper-readiness claim follows.

## Verification and continuation

Run `python -m pytest tests/test_rsi_private.py`. Invented archives exercise the full fixed-size 45,600-row snapshot and 30-job path, separate-process snapshot hash verification, out-of-window malformed data exclusion, one-shot failures, missing canonical store, immutable grants and disposition precedence. Structural corruption cases exercise continuity/source/provenance and invalid prices. These are authored synthetic bytes, not downloaded or published market data.

The `lean-package-parity` CI job supplies the pinned actual LEAN runtime. RSI cases compare native indicator readiness/value and full signal/order/fill/portfolio traces for flat/rising/falling, tiny loss, near-threshold arithmetic, stress and 336-bar scored warmup. Money/indicator values use the existing 1e-18 comparator tolerance; discrete decisions must agree exactly. This establishes bounded observed parity, not every possible decimal input or venue-realistic fills.

Review, CI and integration must finish before private snapshot preparation. Exact reviewed head, results and finding dispositions belong in the PR. Any real preparation or trial failure is retained and needs a new decision before replacement. Private results must not be copied into this public document, issues, PRs or CI artifacts. #3 timely-source rights and #48 external execution remain independent.
