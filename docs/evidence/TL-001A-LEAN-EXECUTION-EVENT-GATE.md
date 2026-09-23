# TL-001A broker execution-ID screen before LEAN events

Status: bounded local synthetic probe on 2026-09-23 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open. This tests a TideLab-owned adapter boundary after the unsafe partial-order late-event result; it does not adopt LEAN.

## Method

At pinned LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, the synthetic `AlgorithmManager.Run` path submitted one order to a mock brokerage. A separate process published the first of two half-unit executions in an authoritative mock broker report, and TideLab's test ledger committed it. A fresh LEAN brokerage setup loaded the partially filled open order. Before constructing any new LEAN `OrderEvent`, `ScreenBrokerExecution` checked the broker-native execution ID and exact quantity, price, and fee against the report and committed ledger.

The test presented the already committed first execution, an unreported second execution, and a first execution with a wrong fee. It then advanced the authoritative report to include the second execution, screened that execution, and delivered one half-fill event to LEAN. A separate sequence forced process exit after the screen committed the second execution but before event delivery, then started LEAN again from the full broker report and ledger. The shell runner kept each sequence on its own temporary report path.

## Observed

- The first execution was `SUPPRESS_COMMITTED`; the unreported second was `BLOCK_UNREPORTED`; the wrong-fee first was `BLOCK_MISMATCH`. No event reached LEAN in those cases.
- With the second execution present in the broker report, the screen durably wrote the test ledger snapshot and returned `DELIVER_AFTER_COMMIT`. One new event reached LEAN. Cash moved from `9954.955` to `9909.91` USD, holding from `0.5` to `1`, the order closed, and no new `PlaceOrder` call occurred. Repeating the same second execution was suppressed.
- After a forced exit following the ledger commit but before event delivery, a fresh LEAN setup loaded the broker-reported final cash `9909.91`, holding `1`, and no open order, without resubmission. The full pinned .NET 10 runner built with zero errors and passed its existing expected positive and blocked recovery cases; upstream package audit warnings remained.

## Limits and next gate

The broker report, execution IDs, event order, and process exits are controlled test doubles. The screen is invoked by the harness before a LEAN event is constructed; no real/public brokerage adapter or unattended event stream was exercised. The snapshot write and same-process ledger/event handoff are not a production transaction or journal. A failure after ledger commit but before event delivery leaves the running LEAN portfolio stale until a new setup or explicit reconciliation; the forced-exit branch only proves the fresh-setup route. Concurrent events, power loss, report revision races, broker correction/cancel semantics, and repeated reconnects remain untested. LEAN's `OrderEvent` at this seam does not itself carry the broker-native execution ID used by the screen.

Next, specify and test an adapter-owned event-delivery protocol with durable broker execution IDs, replay/reconnect behavior, and fail-closed account reconciliation across crash windows. Then extend the shared historical/forward H1 strategy and risk semantics and compare the complete LEAN host burden with NautilusTrader's unresolved external Python data-client/backing gap. Keep [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3) separate; no real market data, account, credentials, or live order was used.
