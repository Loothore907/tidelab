# TL-001A synthetic correction journal and LEAN recovery boundary

Status: bounded [issue #2](https://github.com/Loothore907/tidelab/issues/2) engine evaluation, 2026-09-23 Alaska time. Neither engine is adopted. No real market data, account, credential, paid service, or live order was used.

## Method

At pinned LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, the existing managed `AlgorithmManager.Run` path submitted an invented buy limit at `90` to a mock brokerage. A test ledger committed a half-unit execution at `90` with fee `0.045`. A separate test-owned append journal recorded two broker order IDs and that execution. In later processes, it wrote a revision-3 reversal of the original execution and then a replacement with a new execution ID at `89`, also with fee `0.045`. Every append used write-through and flush; replay checked event sequence, revision order, execution identity, order quantity, and decimal cash/holding arithmetic. Replay after the reversal alone returned a pending-correction hold. Two later replays read the same five events without adding another fill.

The corrected journal expected `9955.455` USD cash, `0.5` holding, `0.5` executed on the first order and zero on the second. A LEAN setup loaded both mock open orders and the *old* `9954.955` cash/`0.5` holding. The test then sent a negative half-fill with a negative fee to reverse the original execution, through the public brokerage `OrdersStatusChanged` event path. It withheld the replacement event and new submissions after the observed failure. In a separate fresh process, a mock broker account derived from the corrected journal supplied `9955.455` cash and `0.5` holding, plus both open orders, to LEAN's public `BrokerageSetupHandler`.

Reproduce the focused path with `TL001A_JOURNAL_ONLY=1 bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`. The full runner includes the same phases. Repository CI does not compile these C# probes.

## Observed result

- Journal replay held at four events while reversal lacked a replacement, then produced the corrected five-event account state across process restarts.
- The running LEAN path logged `SecurityPortfolioModel.ProcessFill(): DivideByZeroException` at its average-price calculation. It did not throw to the adapter. Its cash became `10000`, holding remained `0.5`, and it emitted one callback. This state did not match the corrected journal. No replacement was sent and the mock broker saw no new `PlaceOrder`.
- Fresh LEAN setup from the corrected test account loaded both open order IDs, `9955.455` cash and `0.5` holding, with zero fill callbacks and zero new submissions.

The direct negative-fill correction route is unsafe at this pinned LEAN version. A TideLab adapter cannot infer success from a returned event call or account cash alone. The observed running instance must remain blocked; fresh setup from an authoritative broker snapshot is a possible recovery route, but this test did not prove production restart safety, order-status correction, atomic broker report publication, crash-safe journal integrity, or an actual submission barrier. The journal is an invented test fixture, not a production event store; flush calls alone do not prove power-loss durability.

LEAN remains the more promising candidate for a bounded public setup/clock integration, but its correction path adds TideLab-owned adapter and restart work. NautilusTrader `2.0.0rc5` still lacks evidence for backed recovery with an external Python data client. Neither engine is adopted. Next test an atomic authoritative broker snapshot and replay barrier under a correction arriving during restart; separately close realistic cost/fill, experiment provenance, and distribution gates. Keep [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3) separate.
