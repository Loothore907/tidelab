# H1 v1 synthetic decision and LEAN clock parity

Issue: [TL-002 #48](https://github.com/Loothore907/tidelab/issues/48). This is an invented-bar engineering check, not a strategy return or an order test. No market price or derived result was committed.

## Shared rule and controlled input

`TideLabH1V1Policy.cs` is compiled into both the historical Launcher algorithm and managed forward `AlgorithmManager` probe at pinned LEAN commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`. It requires 168 consecutive closed UTC hours, uses their inclusive arithmetic mean, enters only above the mean while in cash, exits at or below the mean while long, and declares a 25% entry target. The separate risk gate exits at a 20% marked equity drawdown and halts entries for the rest of the policy instance. Each scored partition needs a new instance. Missing or repeated hours throw instead of interpolating.

The invented closes are 168 repetitions of `100`, then `102, 98, 110`. The probe assumes each approved proposal changes synthetic position at the following bar's open; it submits no order. The standalone check explicitly records that the two modeled position changes occur one bar after their proposals. The drawdown scenario marks equity at `8,000` from the 170th closed bar onward against a `10,000` peak. Baseline marks stay at `10,000`.

## Observed local checks

| Path | Baseline | Drawdown |
| --- | --- | --- |
| Historical LEAN Launcher, 171 invented CSV bars | `169:EnterLong:Clear`, `170:ExitToCash:Clear`, `171:EnterLong:Clear` | `169:EnterLong:Clear`, `170:ExitToCash:DrawdownHalt`; no later entry |
| Managed forward LEAN feed and `AlgorithmManager`, 168 seeded warmup closes plus 3 delivered bars | Same | Same |

Both LEAN builds finished with zero errors and both runs recorded zero orders. Historical callbacks covered `2026-01-01 06:00` through `2026-01-08 08:00 UTC` with 171 bars. The standalone .NET check passed warmup, equality, next-open position timing, drawdown, oversized-entry rejection, partition reset, missing/duplicate rejection and historical/forward decision equality. The existing Python suite passed 41 tests; its optional Nautilus test was skipped. Upstream LEAN package-audit warnings remain; repository CI does not compile these C# probes.

Reproduce locally against the pinned separate LEAN checkout and .NET 10 binary:

```bash
dotnet run --project scripts/lean_fallback/h1_v1_check/H1V1Check.csproj
TL_H1_V1_ONLY=1 bash scripts/lean_fallback/run_h1_historical_probe.sh <LEAN checkout> <dotnet binary>
TL_H1_V1_ONLY=1 bash scripts/lean_fallback/run_forward_recovery_probe.sh <LEAN checkout> <dotnet binary>
```

The first historical attempt failed at a date boundary: LEAN requested custom-data files by New York subscription date, but the synthetic generator grouped them by UTC date. After the generator grouped files by New York date while retaining UTC timestamps in rows, all 171 hourly callbacks arrived in sequence. The existing `export-lean-h1` bridge had the same filename error and was corrected and tested here. Its earlier local January 2024 export remains untouched; a new ignored export has 744 continuous UTC rows in 32 New York date files. No H1 rule was run on those real bars.

## Remaining gate

This proves the declared **decision sequence** for these synthetic paths. The forward test seeds warmup directly into the shared rule because the managed test clock delivered only six of 171 queued bars within a 90-second deadline; the three decision bars traverse LEAN's managed feed. The probe's position and equity are controlled assumptions. There is no quantity rounding, fee/cash/inventory reconciliation, actual next-open fill, pending-order recovery, ambiguous-submission barrier, or general paper adapter here. Complete those synthetic accounting and recovery checks under issue #48 before opening H1 real-data performance. A timely, rights-supportable forward source remains issue #3.
