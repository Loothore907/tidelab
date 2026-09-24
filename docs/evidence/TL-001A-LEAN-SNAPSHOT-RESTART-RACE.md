# TL-001A synthetic broker snapshot revision during LEAN restart

Status: bounded [issue #2](https://github.com/Loothore907/tidelab/issues/2) engine evaluation, 2026-09-23 Alaska time. Neither engine is adopted. No real market data, account, credential, paid service, or live order was used.

## Method and observation

At pinned LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, the existing managed mock order path produced a half-fill. A test-owned broker snapshot published revision 2 with two open order IDs, `9954.955` USD cash, `0.5` holding, and a three-event journal cursor. Publication wrote and flushed a candidate file, then replaced the snapshot path. It is one synthetic writer, not an actual broker transaction.

In the race phase, LEAN setup read revision 2 account balances. During its public `GetOpenOrders` call, the mock broker appended a reversal and corrected replacement at `89` to the journal and published snapshot revision 3 with `9955.455` cash and five journal events. Setup completed with the old account. The test compared the authoritative snapshot before and after setup, observed revision `2 → 3`, and returned `BLOCK_REVISION_RACE` with no new mock `PlaceOrder`. It did not deliver the correction to the running engine.

A later independent process read stable revision 3 before and after fresh `BrokerageSetupHandler` setup. LEAN loaded `9955.455` cash, `0.5` holding, both open broker IDs, and no fill callback or new submission. The snapshot and journal agreed on cash, holding, per-order executed quantity, and five events. The focused path passed with `TL001A_SNAPSHOT_ONLY=1 bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`; the full local runner also includes it. Repository CI does not compile these C# probes.

## Decision effect and limits

The public LEAN setup seam can load a stable corrected mock account with two open orders. TideLab must own the before/after revision check and keep submissions held on a change; setup success alone did not mean the engine matched the latest broker state. The earlier [correction journal probe](TL-001A-LEAN-CORRECTION-JOURNAL.md) showed that sending a negative reversal event to running LEAN left cash and holdings inconsistent, so restarting from an authoritative snapshot is the safer *candidate path* to evaluate.

This probe uses a single local file writer and a controlled callback. It does not prove atomicity across broker account, orders, and journal; a real broker API may not expose a consistent revision, and a correction can arrive after the final check. It does not implement an actual submission barrier, process supervision, power-loss durability, or live recovery. A production adapter would need a broker-native consistency token or repeatable snapshot protocol, an order/account barrier that stays engaged through handoff, and a policy for unresolvable revisions. LEAN still needs that TideLab-owned integration; NautilusTrader `2.0.0rc5` retains the external Python data-client/backing gap. Neither is adopted. Keep [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3) separate.

Next compare the required integration and failure controls for both candidates, then close realistic cost/fill, experiment-provenance, and distribution obligations before an engine decision.
