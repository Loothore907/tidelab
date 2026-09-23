# TL-001A LEAN synthetic clock and late-event checkpoint

Status: bounded local probe on 2026-09-22 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open. No engine has been adopted.

## Method

At pinned, unmodified LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, a TideLab test harness manually advanced LEAN's UTC algorithm clock by three hourly synthetic `TradeBar` slices (close values 100, 102, 104) and invoked `QCAlgorithm.OnData`. The probe algorithm compared the first and third close and called LEAN's `LimitOrder` once from that callback. LEAN's transaction handler sent the order to the same mock `IBrokerage` used in the earlier submission probe. The broker wrote a durable `Submitted` report and emitted its acknowledgement; the first process terminated without teardown.

A separate synthetic brokerage phase changed the report to a full fill while LEAN was stopped. Fresh LEAN setup loaded the broker's cash and holdings with no new order. The TideLab test reconciliation record captured the execution once. The mock brokerage then emitted a **late `Filled` event for that already reported execution**, using the original LEAN order ID, to the fresh transaction handler. A second fresh restore repeated that event attempt against the same report and record. The reproducible sequence is included in `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`.

## Observed

- The manually advanced UTC clock delivered exactly three ordered `OnData` callbacks. The third generated one signal and one broker submission. The broker-assigned ID was retained as `Submitted` before process loss.
- During downtime the broker report changed to execution `TL001A-EXECUTION-1` at 90 with a 0.09 USD fee. Fresh setup loaded cash `9909.91`, holding `1`, and zero open orders; it made zero `PlaceOrder` calls.
- Fresh LEAN had no closed order or transaction history from setup. The late duplicate `Filled` event did **not** reach `OnOrderEvent` or change cash/holding. The fresh transaction handler could not associate that old LEAN order ID with an order. This is an observed rejection of this synthetic late event, not general duplicate-event protection.
- The first restore created the TideLab test record. The repeated restore verified the same record. Neither late-event attempt created a second execution record or resubmitted the order.
- The isolated .NET 10 Release build had zero errors. Pinned upstream NuGet package audit warnings remained. The local shell runner passed its prior pending, filled, same-process event, missing-report, and contradictory-report cases as well as this new sequence.

## Limits and decision

The harness calls `SetDateTime`, `SetCurrentSlice`, and `OnData` itself. It does **not** exercise LEAN's live data-feed scheduler, a continuously running algorithm manager, or historical/forward strategy parity. Three synthetic bars and a single hardcoded signal do not establish a research strategy or realistic fill model. The mock broker supplies a complete authoritative report; the TideLab record is a test artifact, not a production ledger. Partial fills, multiple orders, out-of-order or changed execution reports, record-write interruption, and duplicate live events against an active order remain untested.

The observed late-event rejection means a restart design cannot depend on replaying a closed fill into a fresh LEAN transaction handler. It needs an explicit, durable broker-execution reconciliation path with exact execution identity and accounting invariants. Next: test a real LEAN-managed synthetic forward feed or identify its public adapter seam; then test partial and conflicting reports plus interruption during record persistence before comparing total integration cost with the pinned NautilusTrader gap. Keep TL-001B rights separate.
