# TL-003 channel-breakout shared synthetic path

Owner: [#95](https://github.com/Loothore907/tidelab/issues/95). Classification: selected strategy implementation, not a real-data trial. The owner approved the completed private proposal's candidate, implementation, synthetic testing, distinct review and gated integration scope. Price access and trial authority remain ungranted. The private implementation receipt and selected intake v2 stay under ignored `data/strategy_intake/`.

## Outcome and boundaries

The shared normalized-package path now represents actual OHLC and lagged channel bounds. Schema v3 adds only `donchian_upper(window=480, lag=1)` and `donchian_lower(window=240, lag=1)` to the existing close/constant/SMA/Boolean grammar. It is not a general source parser or indicator library. Raw Python/Pine does not become executable because this adaptation exists.

At close t, a flat account buys when close exceeds the maximum high over t-480 through t-1; a held account sells when close falls below the minimum low over t-240 through t-1. Equality holds. The current bar is excluded from both bounds. Entry budgets 25% of signal-time cash, with fee-inclusive next-open units floored to 0.00000001; exit sells all units at the next scored open. No shorts, leverage, rebalance, ATR, intrabar stops, timed expiry or terminal sale. Holdings are marked at the final scored close. Missing or inconsistent high/low fails rather than becoming a close-only approximation.

Readiness is 481 samples, requiring 480 preceding warmup bars at the first scored close. Parser, admission, replay and LEAN explicitly distinguish this from the historical v1/v2 warmup convention, which is preserved. The LEAN comparison uses native `DonchianChannel(480,240)` and observes it before updating with the current bar. Python uses monotonic queues over the same prior windows, so independent expected traces remain important.

This continuation hypothesis differs from the RSI rebound mechanism but overlaps earlier trend research. It is a candidate to investigate, not evidence of an edge. The current demonstration contains no market data and makes no research nomination.

## Source and adaptation

Rule reference: QuantConnect Documentation [equity-donchian-breakout-turtle/main.py](https://github.com/QuantConnect/Documentation/blob/a0fcde52f4a9acd88fb3720ff7aaff1e3f2be1be/project-templates/python/equity-donchian-breakout-turtle/main.py), pin `a0fcde52f4a9acd88fb3720ff7aaff1e3f2be1be`, source SHA-256 `fffd5a20080f9206d254df1a269ad7b7a0ca6d9a887499b974511a439735cd00`. Its [license](https://github.com/QuantConnect/Documentation/blob/a0fcde52f4a9acd88fb3720ff7aaff1e3f2be1be/LICENSE) is Apache-2.0. The template uses daily 20/10 channels on equity ETFs, scheduled opening checks and ATR/capped sizing. TideLab's independently written adaptation uses rolling hourly windows, spot long/cash, fixed cash budgeting and next-open fills. Twenty calendar days of crypto observations are not twenty equity trading sessions. No template performance or original Turtle-system replication is claimed.

Indicator reference: QuantConnect LEAN [DonchianChannel.cs](https://github.com/QuantConnect/Lean/blob/88bce0fc6fe282378ee73c54cef1090d0d7a73ee/Indicators/DonchianChannel.cs), SHA-256 `89c2e61ebfd08750f67243a4ca109d041d7bb779c30ec04b9db53c3a176d65b6`. Copyright QuantConnect Corporation; Apache-2.0 at the unchanged LEAN pin `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`. Preserve applicable attribution and licenses for distribution; neither source license grants data rights or endorsement. No third-party source was executed as intake.

## Reuse and authority controls

- `strategy_batch.py`, `historical_input.py` and `package_lean_parity.py` carry explicit OHLC through shared parsing, replay and traces. Existing v1/v2 package semantics remain intact.
- `channel_breakout.package` supplies one source-bound normalized rule; the synthetic demonstration binds the same rule to a clearly labeled TideLab conformance record. The actual external selected intake and its generated package are retained privately. Synthetic counterpart tests do not establish general external-source admission.
- `private_history.py` extracts canonical-store verification and bounded row/window/provenance mechanics from the existing RSI module. These helpers do not grant access. RSI retains its original grant, proposal/record hashes, dates, 20-trip review floor and consumed-event protection. Its past receipts and results are not rewritten.
- `UnapprovedChannelPolicy`, `prepare_private` and `execute_private` reject unconditionally before store or price access. There is no approval flag, alternate registry option or file-based grant bypass. The ordinary historical CLI remains synthetic-only. A future explicit trial decision needs a separately reviewed admission change that appends to the established program store; this slice does not create a new grant or runnable private workflow.
- `batch_review.py` shares descriptive review and retained-trace diagnostics. The channel's five-trip floor is synthetic policy acceptance only; RSI's 20-trip policy remains fixed. Incomplete jobs take precedence, any batch incompleteness makes eligibility provisional, and neither path promotes automatically. Terminal unrealized contribution and hypothetical exit friction are reported without a rerun or forced sale.

The canonical `data/research_program/trials.sqlite3` and `data/strategy_intake/RSI-BATCH-V1-STORE.json` anchor remain mandatory for future research admission. Keep #3 data rights/timeliness and #48 external execution independent. No private prices, accounts, orders, downloads, paid services or public real-data outputs are part of this slice.

## Acceptance and reproduction

Use fresh output directories; do not erase an earlier attempt to rerun a demonstration. All following inputs are invented. The synthetic ledger is separate from the canonical real-research store.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_channel_breakout.py
.\.venv\Scripts\python.exe scripts/historical_batch.py demo --channel --output data/channel-synthetic/demo-new
```

The command generates five synthetic markets with 9,264 OHLC rows each (480 warmup plus 8,784 scored), one package, baseline/stress costs and cash/passive benchmarks. It sends the 30 jobs through the existing admission, replay, metrics and artifact-recovery path. `review.json` is outside the immutable batch artifact and is derived only from verified retained synthetic inputs/results/traces. One CLI command plus reading the retained result is the operator workflow; there is no per-market agent action or candidate-only runner.

Baseline per side remains 0.0025 fee plus 0.001 adverse price; stress doubles both. Independent golden cases check upper/lower wicks, strict equality, rolling-window expiry, first scored signal, gap-open accounting, terminal holdings and no future dependence. Malformed OHLC, unsupported operator variants, absent trial authority, changed/missing canonical identity and spent RSI grants fail on invented inputs. Golden gap accounting checks quantity `12.45637155`, next-open prices `200.2` and `49.95`, and final cash `8120.64027125441875`; these numbers are wholly synthetic.

Native runtime reproduction requires a clean LEAN checkout at the stated pin, .NET 10 and `TIDELAB_LEAN_ROOT` / `TIDELAB_DOTNET`. The existing `lean-package-parity` CI job now includes `tests/test_channel_breakout.py`; it executes all eight new native-channel cases along with earlier package, historical and RSI regressions. This is the established harness with actual LEAN orders/fees/portfolio accounting, not full feed/AlgorithmManager acceptance or realistic market liquidity.

Development verification: Windows suite passed 184 tests with 27 environment skips before the additional shared-OHLC test; all eight new actual-LEAN cases passed locally. The first full synthetic demonstration accounted for all 30 completed jobs, five market reads and 263,520 scored trace rows. Measured on WSL with the Windows-mounted checkout: 12.25 seconds batch time, 21.25 seconds total generation/replay/review, 79,720 KiB peak process RSS. That first attempt used the inherited generic synthetic intake record; the final demonstration uses a dedicated channel conformance record to make source meaning explicit. Both attempts remain retained. This is one rule on invented waves, not diverse strategy ingestion or profitability evidence. Exact-head checks and final review are reported on the PR.

## Integration gate and next decision

The author must inspect the exact diff, source interpretation, inventory and evidence against the approved brief. A distinct reviewer is required for the package semantics and authority boundary; self-review and green CI are insufficient. Keep the PR draft until that review is available and resolved. GitHub currently requires `test` and conversation resolution, with admin enforcement; its required approving-review count is zero, so the stronger distinct-review gate is a process requirement.

After reviewed integration, the only next owner decision is whether to authorize the separately proposed bounded private trial. Integration does not make that decision. Preserve the finished RSI study without tuning, reruns or new partitions.
