# TL-001A LEAN partial-fill and interrupted-record checkpoint

Status: bounded synthetic probe on 2026-09-22 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open; neither engine is adopted.

## Method

The probe extends the pinned LEAN `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` local execution/restart fixture. A first process submits one synthetic limit order through LEAN's transaction handler to a mock brokerage, receives a `Submitted` acknowledgement, and exits. The mock brokerage then reports one partial execution: 0.5 of 1 unit at 90, fee 0.09 USD, cash 9,954.91 USD, holding 0.5, and the original order still open as `PartiallyFilled`. Fresh `BrokerageSetupHandler` and `BrokerageTransactionHandler` load that report.

Separate fixtures change either partial-fill cash or full-fill executed quantity while retaining inconsistent balances; TideLab's test guard rejects both before LEAN setup. Another fixture settles fully, then writes only the prefix of a synthetic reconciliation JSON record with a durable flush, representing a process interrupted during record persistence. A fresh setup reads the broker's valid filled report but blocks when the record cannot be parsed. `scripts/lean_fallback/run_forward_recovery_probe.sh` runs these cases alongside the prior ones against the isolated pinned checkout.

## Observed

- Valid partial report: fresh LEAN setup loaded one `PartiallyFilled` open order with the same broker ID, cash `9954.91`, and holding `0.5`. It made zero `PlaceOrder` calls. The test printed `HOLD_NEW_ORDERS` because the current single-execution test record does not yet account for a remaining fill.
- Contradictory partial cash and contradictory full executed quantity each caused a nonzero `BLOCK` before setup. Neither case submitted an order.
- A truncated existing reconciliation record caused a nonzero `BLOCK` after LEAN loaded the valid filled account. It was neither overwritten nor treated as a completed execution, and no order was submitted.
- The isolated .NET 10 Release build had zero errors; upstream NuGet package audit warnings remained. The complete local synthetic runner passed its expected success and blocked cases.

## Limits and next gate

The brokerage report is fully synthetic and authoritative by construction. These checks do not prove a production broker's completeness, timeliness, or execution IDs. The partial-order probe does not verify LEAN's internal cumulative filled quantity or safely allow the remaining 0.5 unit to trade. The truncated-file case simulates an interrupted record write; it does not kill a process at the exact filesystem boundary or prove crash-safe atomic persistence. No multi-execution ledger, partial-to-full transition, out-of-order report sequence, managed live feed, or historical/forward strategy parity has been tested.

Next in TL-001A: use LEAN's managed forward feed with synthetic data, then test a durable per-execution reconciliation design across partial-to-full transitions and crash points. Keep TL-001B data rights separate. No engine adoption follows from this checkpoint.
