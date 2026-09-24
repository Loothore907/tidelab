# TL-001A synthetic submission handoff boundary

Status: bounded [issue #2](https://github.com/Loothore907/tidelab/issues/2) engine evaluation, 2026-09-23 Alaska time. Neither engine is adopted. No account, credential, real market data, paid service, or live order was used.

## Public interface finding

At pinned LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, `Common/Interfaces/IBrokerage.cs` exposes separate `GetOpenOrders` (line 94), `GetAccountHoldings` (100), `GetCashBalance` (106), and `PlaceOrder` (113) methods. None accepts or returns a common snapshot revision. `Engine/Setup/BrokerageSetupHandler.cs` calls cash, open orders, then holdings separately (lines 375, 405, 420). This public engine-facing surface allows an adapter to return a consistent *test* snapshot, but it does not itself give a broker-atomic account/order/execution view or a versioned order submission.

## Bounded probe

The existing synthetic two-order journal and broker snapshot began at revision 2: one half-fill, `9954.955` cash, `0.5` holding. Fresh LEAN setup loaded that state, and the test's final broker snapshot read still returned revision 2. Immediately afterward, before any mock `PlaceOrder`, the synthetic broker appended the correction reversal/replacement and published revision 3 with `9955.455` cash. The test returned `BLOCK_UNVERSIONED_HANDOFF`; no new submission was sent. A separate process then restored stable revision 3 and matched the corrected journal, cash, holding, and both open order IDs.

The focused command `TL001A_HANDOFF_ONLY=1 bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>` passed. The full local runner includes the same case. Repository CI does not compile this C# probe.

## Decision effect

The preceding [snapshot-race test](TL-001A-LEAN-SNAPSHOT-RESTART-RACE.md) detected a correction during setup. This case shows why even a stable read **after** setup is insufficient: the broker can change before the next submission. Rechecking just before `PlaceOrder` narrows the interval but cannot close it without a broker-enforced versioned command or a correction/submission serialization guarantee. The test deliberately held rather than claiming it implemented such a guarantee.

LEAN still has the stronger demonstrated historical/forward and public restart path. For forward paper, TideLab could own a replaceable paper-broker source that serializes correction intake, snapshot reads, and submissions while retaining native-style execution IDs and correction history. `IBrokerage` does not supply the cross-call revision or compare-and-submit operation, so the host adapter must enforce the paper barrier. An eventual external broker would need its own enforceable consistency guarantee and separate authorization. NautilusTrader `2.0.0rc5` still has the external Python data-client/cache-backing incompatibility and would need its own evidenced persistence/reconciliation route. Neither engine is adopted; no custom engine or fork is justified.

The specific unresolved TL-001A requirement is a **replaceable forward-paper source with an enforced snapshot-to-submission barrier**, not another synthetic LEAN callback. The current mock does not implement that barrier. Broker-native guarantees for a later external venue remain a separate future gate. Complete realistic cost/fill, experiment-provenance, and distribution checks before an engine decision. Keep [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3) separate.
