# TL-001A synthetic paper intent and LEAN restart join

Status: bounded [issue #2](https://github.com/Loothore907/tidelab/issues/2) engine evaluation, 2026-09-23 Alaska time. Neither engine is adopted. All account values, orders, execution IDs and reports are synthetic; no account, credential, real market data or live order was used.

## Joined restart probe

The [paper intent probe](TL-001A-LEAN-PAPER-INTENT-RECOVERY.md) recovered a stable client ID after two process-loss windows but had not checked LEAN's restored state. This follow-up runs fresh pinned LEAN `BrokerageSetupHandler` after each recovery. The TideLab test boundary first validates the accepted intent, the authoritative paper order report, the corrected execution journal and revision-3 broker account snapshot. Its mock brokerage then reports three open orders: the original partially filled order, an existing second order, and the newly accepted pending order. The host maps the stable client ID to its reported broker ID before comparing LEAN's restored open orders. It checks cash `9955.455`, holding `0.5`, statuses, third-order quantity and limit price, and all three broker IDs. LEAN emits no fill callback or new `PlaceOrder` call during setup.

An adversarial variant makes the third ID returned by LEAN's mock `GetOpenOrders` differ from the accepted paper report. The joined gate detects that disagreement and returns `BLOCK_ORDER_IDENTITY` with zero new submissions. The successful variants return `JOINED_RESTART_MATCH`; this is a matched synthetic restart snapshot, not authorization to submit another order.

The focused `TL001A_INTENT_ONLY=1` runner and full pinned LEAN recovery runner passed locally at LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`. The build had zero errors and existing upstream package-audit warnings. The focused runner printed `JOINED_RESTART_MATCH ... open_orders=3 callbacks=0 new_submissions=0` after both pre-dispatch and lost-acknowledgement recovery, and `BLOCK_ORDER_IDENTITY ... new_submissions=0` for the mismatch. Repository CI does not compile this C# probe.

## Decision effect and limits

The public LEAN startup seam can load three pending synthetic paper orders and the matching account while TideLab checks a separate stable client-ID/intent record. The engine does not carry that client ID as an enforced versioned submission token; TideLab owns the mapping, gate and authoritative broker/ledger state. LEAN's account, order and holding reads remain separate calls. This test holds the mock report static through setup and sends no next order, so it does not prove an uninterrupted snapshot-to-next-submission handoff, concurrent execution delivery, corrected running-engine state, or production durability. An external broker requires separate native guarantees and authority.

LEAN remains the stronger bounded candidate to evaluate, without adoption. The remaining TL-001A decision work is a realistic cost/fill and failure model, engine-independent experiment identity/evidence export, distribution obligations, and an explicit estimate of TideLab host integration against NautilusTrader `2.0.0rc5`'s external Python data-client/backing gap. [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3) remains separate.
