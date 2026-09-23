# TL-001A synthetic per-execution recovery checkpoint

Status: bounded local probe on 2026-09-23 Alaska time. [Issue #2](https://github.com/Loothore907/tidelab/issues/2) remains open. No engine adoption or production ledger.

## Method

The pinned LEAN `AlgorithmManager.Run` phase submitted one synthetic order to a mock brokerage, which durably wrote a `Submitted` report. Two separate test sequences then advanced that authoritative report from a half-unit partial fill to a full one. Each execution had a distinct broker execution ID, quantity `0.5`, price `90`, and fee `0.045` USD. The report's cash and holding totals were `9954.955`/`0.5` after the first execution and `9909.91`/`1` after the second.

TideLab's test-only ledger reader checked the broker order and instrument, unique execution IDs, exact execution details, revision/status progression, and decimal cash/holding sums. Its durable snapshot retained the first execution as a prefix while the broker report advanced to two. One sequence forced process exit before the second ledger write. The other flushed a two-execution candidate file and forced exit before same-directory replacement of the committed ledger file. Fresh processes reconciled from the broker report, then repeated reconciliation to test idempotence. Reproduce with `bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned-LEAN-checkout> <dotnet-10-binary>`.

## Observed

- The first execution was recorded once with cash `9954.955` and holding `0.5`.
- After exit before the second write, a fresh process saw two broker executions and one committed ledger execution, wrote the two-execution snapshot, and verified it unchanged on the next restore.
- After exit following candidate flush, a fresh process validated the candidate against both authoritative executions, published it, and verified it unchanged on the next restore. Both full snapshots had cash `9909.91` and holding `1`.
- The full pinned .NET 10 runner built with zero errors and retained its prior pending, partial, conflict, torn-record, late-event, feed, and manager cases. Upstream package audit warnings remained.

## Limits and next gate

The mock brokerage supplies invented executions and balances. The ledger code is a test-only snapshot, not an append-only production journal, and the scenario does not call LEAN's brokerage setup after the second execution. The ledger path cannot submit orders; therefore it cannot establish integrated no-resubmission behavior through partial-to-full recovery. The forced exits are at selected process boundaries, not arbitrary power loss; file and directory durability across filesystems is unproven. Other failure windows, concurrent writers, missing reports, out-of-order revisions, and realistic broker corrections require separate tests. Repository CI does not compile the C# probe. Before an engine decision, connect multi-execution recovery to the fresh LEAN setup/order gate, extend shared strategy/risk semantics, and compare the remaining LEAN host work with NautilusTrader's backed external-client limitation. Keep TL-001B separate.
