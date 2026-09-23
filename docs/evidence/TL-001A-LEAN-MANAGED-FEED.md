# TL-001A LEAN managed synthetic forward-feed checkpoint

Status: bounded local test on 2026-09-22 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open. LEAN is not adopted.

## Method

The TideLab-authored probe ran against pinned, unmodified LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` with an isolated .NET 10 SDK. It created three synthetic hourly `TradeBar` values (100, 102, 104), stamped in the security's New York exchange time. An unmodified LEAN `LiveTradingDataFeed`, `LiveSynchronizer`, and test data-queue handler formed a live-mode subscription for a synthetic fixture labeled `SPY`. A manual UTC time provider advanced to each expected bar boundary and waited there until the feed produced the bar. The TideLab harness consumed the resulting LEAN `TimeSlice` and called the probe algorithm's `OnData` callback. The `AlgorithmManager` loop did not run.

The reproducible command is `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`. The script copies TideLab probe code into the separate pinned checkout, builds, and runs this `managed_feed` case alongside the brokerage restart cases. It uses only synthetic local values, no market-data download, account, token, or paid CLI.

## Observed

- LEAN's live feed and synchronizer emitted three slices in order. The harness delivered their values `100,102,104` to three `OnData` callbacks at the expected UTC hourly boundaries. The isolated build had zero errors; upstream NuGet package audit warnings remained. The full local runner passed.
- An initial fixture stamped the bars in UTC although this equity subscription interprets `TradeBar.Time` in exchange-local time. It produced callbacks for `100,104,104` at unintended frontiers, missing the middle value. Correcting timestamps to New York time fixed that specific error.
- A fast manual-clock variant advanced beyond an expected bar before it arrived and also skipped the middle value. A fixed jump to a boundary produced no bars in that run; a one-minute step delivered only one before its short timeout. The final test advances by up to five minutes per synchronizer pulse but holds at each expected boundary until its bar is observed. Three standalone final runs and the full runner passed. These failed variants remain part of the evidence because delivery cadence is material.

## Limits and next gate

This establishes a **managed live-feed/synchronizer input seam**, with harness-dispatched callbacks. It does not run LEAN's full `AlgorithmManager`, submit an order from this feed, exercise a live brokerage, or demonstrate historical/forward strategy parity. The `SPY` symbol is a test label for invented prices; no real SPY market data was used. The queue handler and clock are test doubles, so scheduler timing and external-data behavior are not proven. The test is local; repository CI currently does not build or run the C# probe.

Next in TL-001A: run one shared synthetic strategy through historical and managed-forward paths, connect the forward callback to the synthetic brokerage submission/restart seam, and test the per-execution ledger through partial-to-full transitions. Compare the complete integration path with the pinned NautilusTrader backing limitation before choosing an engine. TL-001B rights remain separate.
