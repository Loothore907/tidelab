# H1 v1 synthetic next-open accounting

Issue: [TL-002 #48](https://github.com/Loothore907/tidelab/issues/48). This checks TideLab's preregistered H1 v1 arithmetic with TideLab-authored invented bars only. The amounts below are fixture checks, not returns from any market or a claim about obtainable fills.

## Method

The same `TideLabH1V1ResearchReplay` and previously checked H1 v1 policy are compiled into pinned LEAN commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` for both historical Launcher and managed forward `AlgorithmManager` delivery. Historical receives 171 closed invented OHLC hours. Forward seeds 168 invented warmup hours and receives the next three OHLC hours from LEAN's live feed. Both pass the resulting sequence into the same batch replay. No LEAN order is submitted.

Each partition begins with 10,000 hypothetical cash units and zero inventory. The first 168 closes warm the indicator only. Two scored hours have closes `102, 98` after the flat `100` warmup; the next hour supplies the terminal open. The entry proposal at the first scored close buys at the following open, with an adverse 0.10% price adjustment and a 0.25% fee. Units round **down** to eight decimal places. The exit proposal at the next scored close sells all units at the following open with the same adverse adjustment and fee. The stress replay doubles both rates. Cash may never go negative. An absent, duplicate, or unclosed scored hour invalidates the run before replay starts.

## Observed

| Path | Base final cash | Base total fees | Stress final cash | Fills | Orders |
| --- | ---: | ---: | ---: | ---: | ---: |
| Historical LEAN Launcher | 9884.91875772681400 | 12.24290415318600 | 9867.91025795471400 | 2 | 0 |
| Managed forward LEAN feed | 9884.91875772681400 | 12.24290415318600 | 9867.91025795471400 | 2 | 0 |

Both pinned LEAN builds finished with zero errors. A standalone .NET check independently calculated expected cash and fees, checked the exact next-bar timestamps and marked cash/inventory, replayed the same input twice with identical decisions and balances, and exercised terminal liquidation, a final-close entry, the 20% drawdown exit, missing-hour rejection, and unclosed-bar rejection. The older synthetic H1 decision probes remain separate.

The frozen rule can propose an entry on the final scored close. Under its literal timing, that entry fills at the next open and the terminal rule immediately liquidates it at that same open, charging both costs. This edge is explicitly tested; changing it would require a separately identified strategy version or preregistration correction before real results are opened.

Reproduce with the pinned separate LEAN checkout and .NET 10 binary:

```bash
dotnet run --project scripts/lean_fallback/h1_v1_check/H1V1Check.csproj
TL_H1_V1_ACCOUNTING_ONLY=1 bash scripts/lean_fallback/run_h1_historical_probe.sh <LEAN checkout> <dotnet binary>
TL_H1_V1_ACCOUNTING_ONLY=1 bash scripts/lean_fallback/run_forward_recovery_probe.sh <LEAN checkout> <dotnet binary>
bash scripts/lean_fallback/run_h1_v1_accounting_parity.sh <LEAN checkout> <dotnet binary>
```

## Limit and next gate

This is a deterministic **batch research accounting model**, using invented prices and declared hypothetical costs. It does not use LEAN's fill model or submit through a broker. It does not model spread observations, partial fills, quote size, exchange increments, pending order state, or process restart. The shared policy still needs a durable order boundary that blocks a new submission when a previous status is unknown, followed by replay/reconciliation checks. Issue #48 owns that integration. Only after that and recorded code/configuration/data identities should H1 v1 open local real-data performance; issue #3 separately owns an on-time forward source.
