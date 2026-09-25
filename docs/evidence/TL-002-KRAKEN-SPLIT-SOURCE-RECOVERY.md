# TL-002: split-source recovery gap probe

Date: 2026-09-25. Owner: [issue #48](https://github.com/Loothore907/tidelab/issues/48).
This is a documentation review and test-owned synthetic fixture, not a Kraken
adapter or evidence from a Kraken account. No API, account, market data, order,
provider contact, fee, or private H1 result was involved.

## Public source contract reviewed

The [Kraken spot WebSocket `executions` channel](https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/executions)
documents account order-status and fill events, an open-order snapshot, an
optional last-50-fill snapshot (`snap_trades=true`), an `exec_id` on trades, and
a subscription message `sequence`. Its `snap_trades` parameter says the default
is `false`, while the snapshot description says the latest 50 trades are
included by default; callers cannot assume either behavior without specifying
the parameter and testing the response. `filled`, `canceled`, and `expired`
are documented order states. `amended` is a user order change and `restated`
is an engine order change; neither is documented as a corrected-fill reversal.

The [WebSocket `balances` channel](https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/balances)
provides an asset snapshot and updates for completed account transactions,
with a ledger ID, a reference ID (a trade ID for a trade event), and its own
subscription message `sequence`. REST endpoints separately return
[balances](https://docs.kraken.com/api-reference/account-data/get-account-balance),
[open orders](https://docs.kraken.com/api-reference/account-data/get-open-orders),
[closed orders](https://docs.kraken.com/api-reference/account-data/get-closed-orders),
and [trade history](https://docs.kraken.com/api-reference/account-data/get-trades-history).
Closed orders are paged 50 at a time; trade history has time/transaction-ID
filters and offset pagination. [OrderAmends](https://docs.kraken.com/api-reference/account-data/get-order-amends)
records order amendment transactions.

The reviewed pages do not document one source-native revision shared by
balances, orders, and executions, a repeatable atomic read across them, a
resumable/replayable private stream cursor, a terminal-order finality interval,
or a corrected-fill reversal/replacement protocol. Absence from these pages is
an **unknown capability**, not proof that Kraken never offers it. A channel
sequence, REST offset, order amend, or two matching client reads must not be
relabelled as a whole-account consistency token. This review does not select
Kraken as a broker or resolve data-rights issue #3.

## Invented recovery probe

`tests/test_h1_local_report_join.py` now covers two bounded paths:

1. A synthetic order has 51 distinct fills. After an invented stream gap, a
   last-50-fill view omits one fill while the account includes all 51. The
   incomplete report fails accounting reconciliation and writes no execution
   rows. After a separate synthetic history backfill supplies all fills, two
   identical reads still carry independent balance, order, and execution
   sequence values. The H1 handoff refuses them; the parent remains unresolved
   and no successor intent is prepared.
2. An **idealized local mock** supplies a common cursor so the same 51-fill
   terminal report can prepare a successor. Before that successor can be
   claimed, one invented fill price changes. The guarded claim latches
   `late_h1_report_change`; the successor remains unclaimed, the original
   51 execution rows are not rewritten, and a restart cannot clear the hold.

The second path tests TideLab's local hold behavior only. It does not establish
that Kraken supplies the idealized cursor, publishes every correction, or
provides finality. The existing pinned-LEAN post-handoff probe separately
verified zero new mock order requests after a reported correction; this Python
probe does not run LEAN.

## Disposition

Keep #48's external-source gate open and keep the durable hold fail-closed.
Before considering a source adapter or hold-release design, obtain a documented
or otherwise authoritative source-native way to reconstruct complete
account/order/execution state across interruption, identify terminal orders,
and observe and reverse/replace corrected fills. If unavailable, evaluate a
different execution source against that same contract using public materials
before any account access. Issue #3 independently owns timely research data,
rights, continuity, and cost.
