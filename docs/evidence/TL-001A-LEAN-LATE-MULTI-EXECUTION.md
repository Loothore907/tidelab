# TL-001A late event after two-execution recovery

Status: bounded local synthetic probe on 2026-09-23 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open. This records a critical partial-order recovery gap; no engine adoption.

## Method

At pinned LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, the prior manager-generated synthetic order and mock brokerage report advanced through two half-unit executions. Separate processes restored LEAN first with one `PartiallyFilled` open order and one committed test-ledger execution, then with a fully filled broker report and two committed executions. After each fresh setup, the mock brokerage raised two late half-unit `OrderEvent`s bearing the original LEAN order ID and broker order ID. In the partial case both carried `PartiallyFilled` status; in the full case they carried `PartiallyFilled` and `Filled` status. The test compared LEAN callback count, cash, holding, open orders, and ledger bytes with the pre-event state. The same cases ran after both earlier ledger interruption paths.

## Observed

- **Partial restore was unsafe if those events were forwarded.** LEAN's fresh setup restored the open order with the original LEAN order ID. It delivered both late events to `OnOrderEvent` and applied both half-unit fills again. Cash changed from `9954.955` to `9864.865` USD and holding from `0.5` to `1.5` units, exceeding the one-unit order. The committed test ledger remained unchanged and no new `PlaceOrder` call occurred. The probe records `decision=BLOCK` and exits nonzero for this expected negative case.
- **Full restore rejected the late events.** With no open order in the fresh transaction handler, neither event reached `OnOrderEvent`; cash stayed `9909.91`, holding stayed `1`, the ledger bytes were unchanged, and no new order was submitted.
- The full pinned .NET 10 runner built with zero errors and retained its other synthetic recovery cases. Upstream package audit warnings remained.

## Interpretation and next gate

The mock brokerage controls event delivery, fees, and balances. LEAN `OrderEvent` does not carry the test report's authoritative broker execution ID in this probe, so the engine could not distinguish an already reconciled execution from a new one at this seam. The partial result is a reason to withhold late events and all new orders until a broker-native execution-ID boundary can identify, deduplicate, and reconcile them before they reach LEAN. A post-event balance assertion is too late to protect a real account. This boundary has not been implemented or validated, and the test-owned `BLOCK` marker is not a production safeguard. Repository CI does not compile this C# probe. Before any engine decision, test a public-adapter event gate with both duplicate and genuinely new partial fills, plus shared historical/forward strategy and risk semantics. Keep TL-001B separate.
