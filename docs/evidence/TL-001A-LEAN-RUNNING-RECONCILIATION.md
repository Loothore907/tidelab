# TL-001A synthetic running-engine reconciliation

Status: bounded synthetic LEAN evaluation for [issue #2](https://github.com/Loothore907/tidelab/issues/2), 2026-09-23 Alaska time. Neither LEAN nor NautilusTrader is adopted. No account, credential, real market data, paid service, or live order was used.

## Method

At pinned LEAN source commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, the existing managed-feed/`AlgorithmManager.Run` probe submitted one synthetic limit order to a mock brokerage. Its report advanced to one half-unit execution; TideLab's test ledger committed that broker execution ID. A fresh LEAN setup loaded the partially filled order with `9954.955` USD cash, `0.5` holding, and the same broker order ID.

The new `ITideLabBrokerExecutionSource` and `ITideLabEngineExecutionPort` boundaries keep broker-native execution IDs outside LEAN `OrderEvent`. A file-backed synthetic source validates the report and test ledger. The engine port reads LEAN cash, holding, open-order count and broker order ID, and raises one `OrderEvent` when instructed. The bounded protocol compares the running engine with the broker execution prefix and post-state before delivering. Any mismatch blocks. It checks the observed engine state again after delivery and holds if the broker report changes during delivery. All quantities and fees are decimal.

Two independent temporary report paths exercise the same second half-unit execution at broker revision 3:

1. **Interrupted before application:** the test ledger commits the execution, then the engine sink throws before LEAN receives an event. Reconnect sees the same committed broker execution ID but the engine's first-fill state, and delivers that execution once. Two more reconnects see the final state and do not deliver again.
2. **Acknowledgement lost after application:** the sink raises the LEAN event and then throws. Reconnect sees the engine's final state and does not deliver a duplicate. Two more reconnects remain quiet.

Each path also presents a wrong cash state and a different open broker order ID; both must block before delivery. Fresh setup from the final report remains an independent recovery control. Reproduce with `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`.

## Observed and limits

In both paths, the interruption returned `BLOCK_DELIVERY_INTERRUPTED`. The pre-application reconnect returned `APPLIED_FROM_COMMITTED`; the post-application reconnect returned `ALREADY_APPLIED`. After repeated reconnects, LEAN held `9909.91` USD cash, `1` holding, no open order, and exactly one fill callback. The mock brokerage received no new `PlaceOrder`. The wrong cash and wrong broker order ID returned `BLOCK_ENGINE_MISMATCH` without delivery. The full local runner built with zero errors and passed its expected positive and blocked cases; upstream package audit warnings remained. Repository CI does not compile this C# probe.

This is a one-order, two-execution test with invented values and a replaceable *test* source/engine port. Its JSON snapshot is not a production event journal, and the port is not a deployed `IBrokerage` adapter. The protocol assumes a known starting account and sequential execution report; equal cash/holding can conceal unrelated account activity. It does not handle concurrent orders, cancel/correction reports, power-loss durability, or broker revision races. A real adapter must provide authoritative order and per-execution state, a durable delivery cursor, account and order barriers, and a hold on new submissions until reconciliation completes. The current result proves only that this public LEAN event/setup seam can recover the two controlled running-engine interruption windows without blind resubmission.

The next separate TL-001A requirement is one H1 skeleton with identical historical and forward strategy **and independent risk** decisions. The engine comparison and unresolved Nautilus external-Python-client/backing gap remain in [the decision map](TL-001A-ENGINE-DECISION-MAP.md). Keep [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3) independent.
