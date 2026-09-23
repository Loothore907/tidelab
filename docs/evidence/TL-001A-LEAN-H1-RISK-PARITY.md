# TL-001A synthetic H1 strategy and risk decision parity

Status: bounded engine compatibility probe for [issue #2](https://github.com/Loothore907/tidelab/issues/2), 2026-09-23 Alaska time. The H1 rule here is a **synthetic skeleton**, not a registered or frozen trading candidate. No performance, engine-adoption, or live-safety conclusion follows.

## Shared rule and inputs

One TideLab-authored `TideLabH1Skeleton` class is compiled into both paths. Its strategy proposes a long entry at the third closed hour if that close exceeds the first, and an exit to cash at the fourth closed hour if that close is below the first. A separate `TideLabH1RiskGate` allows exits during an entry pause, blocks new entries below 95% of peak equity, and caps target gross exposure at 25%. The synthetic cases use the provisional engineering thresholds in `docs/PLAN.md`; they do not choose H1's real indicators, sizing, evaluation dates, or pass criteria.

The fixture contains four contiguous invented hourly closes `100, 102, 104, 98`. The historical path reads UTC bar starts `05:00–08:00` through LEAN's direct open-source Launcher and local custom-data reader; callbacks must occur at `06:00–09:00 UTC`. The forward path sends the same values through `LiveTradingDataFeed`, `LiveSynchronizer`, and `AlgorithmManager.Run` to `OnData`, with four asserted consecutive UTC boundaries. Both call the same strategy and risk code; environment-specific code supplies only bar delivery and a controlled equity/peak-equity snapshot. Each path records a normalized decision sequence.

Two equity scenarios are fixed before the run: baseline `1000/1000` and drawdown `940/1000`. Reproduce against pinned LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` and .NET 10 with `run_forward_recovery_probe.sh` and `run_h1_historical_probe.sh` in `scripts/lean_fallback/`. The historical script restores its temporary Launcher configuration at exit.

## Observed

| Scenario | Historical Launcher | Managed forward `AlgorithmManager` |
| --- | --- | --- |
| Baseline | `3:EnterLong:Approve\|4:ExitToCash:Approve` | Same |
| Drawdown | `3:EnterLong:BlockDrawdown\|4:ExitToCash:Approve` | Same |

Both paths processed four bars in order. No order was submitted in these parity cases. The pinned local builds completed with zero errors; upstream package audit warnings remained. Repository CI does not compile the C# probe.

The first historical reader treated `00:00–03:00` fixture timestamps as exchange-local and delivered them at `06:00–09:00 UTC`, five hours later than their intended UTC close boundaries. Converting UTC starts into the subscription's New York clock and using `05:00–08:00 UTC` fixture starts produced the expected `06:00–09:00 UTC` callbacks. The reproducer now asserts those exact UTC times; matching decisions alone would have hidden the timestamp error.

## Limits and next gate

This proves identical *decisions for the two specified synthetic sequences*, including an exit that remains available during an entry pause. It does not establish general clock parity, data-gap handling, a complete H1 rule, realistic fills or cost accounting, portfolio-wide risk, decision-record export, or performance. The historical and forward fixtures have different absolute UTC dates; their relative closed-hour order and values match. The skeleton uses a bar-count trend check and fixed account snapshots solely to test the integration seam. No strategy has been registered or promoted.

Before TL-001A adoption, compare the remaining integration burden against NautilusTrader's external Python client/backing gap and test the uncovered fill, cost, recovery and provenance requirements. Before any TL-003 evaluation, freeze H1's actual indicator, entry, exit, sizing, cost, data partitions and acceptance criteria as a new versioned experiment. Keep [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3) separate.
