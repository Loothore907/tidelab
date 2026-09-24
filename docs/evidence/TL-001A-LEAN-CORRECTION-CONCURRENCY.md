# TL-001A synthetic correction and concurrent-order boundaries

Status: bounded [issue #2](https://github.com/Loothore907/tidelab/issues/2) engine evaluation, 2026-09-23 Alaska time. Neither engine is adopted. No account, credential, market data, paid service, or live order was used.

## Probe

The existing LEAN `AlgorithmManager.Run` path submitted one invented limit order to a mock brokerage. A separate process published and committed one half-unit broker execution. Fresh setup at pinned LEAN `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` restored `9954.955` USD cash, `0.5` holding, and the partially filled broker order. Two independent paths then exercised the replaceable `ITideLabBrokerExecutionSource` and `ITideLabEngineExecutionPort` boundary:

- **Corrected report:** the synthetic broker source returned revision 3 with the *same committed execution ID* but price `91` instead of `90` and consistent corrected cash `9954.455`. The running LEAN portfolio still reflected the original execution. Reconciliation returned `BLOCK_ENGINE_MISMATCH` before a ledger commit or engine callback.
- **Second open order:** the mock brokerage exposed a second submitted broker order with a distinct ID. LEAN setup restored both open orders. The source still described only the first order, so the one-order delivery protocol returned `BLOCK_ENGINE_MISMATCH` before delivery.

Both paths preserved the original committed test ledger, recorded zero new callbacks, and made zero new broker `PlaceOrder` calls after setup. The full local forward recovery runner built the pinned LEAN source and passed these cases alongside its prior recovery cases. Reproduce with `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`. Repository CI does not compile the C# probe.

## Decision effect

The boundary holds on these conflicting snapshots. It does **not** apply a broker correction, reverse an earlier portfolio effect, or reconcile two simultaneously active orders. The correction source is a test delegate with invented values, and the second order is a mock brokerage response; neither exercises an actual broker API, an atomic report journal, or a crash during correction. Current account equality alone cannot prove execution identity or independent per-order state.

LEAN continues to offer the stronger demonstrated public setup and managed-clock path, plus the two earlier controlled interruption recoveries and identical H1 strategy/risk decisions. TideLab would still have to build a durable, replaceable broker adapter with immutable report revisions, explicit correction/reversal events, per-order execution cursors, account and order barriers, and a submission hold until the running engine agrees. NautilusTrader `2.0.0rc5` remains blocked on backed recovery with an external Python data client; a public extension or TideLab-owned recovery path would need equivalent evidence. No custom engine or fork is justified. Keep [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3) separate.

**Next gate:** design and probe a durable multi-order and correction journal with explicit reversal semantics, then compare the total adapter cost for both candidates. Complete realistic cost/fill, experiment-identity, and distribution-obligation checks before adoption.
