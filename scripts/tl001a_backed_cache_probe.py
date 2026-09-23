"""Manual TL-001A Redis cache smoke test with synthetic sandbox state only.

Run ``seed`` and ``restore`` in separate Python processes against an isolated,
local Redis instance. This deliberately creates a DENIED order: it does not
exercise pending-order recovery or venue reconciliation.
"""

from __future__ import annotations

import argparse
import json
import os
import threading
import time

import nautilus_trader
from nautilus_trader.adapters.sandbox import (
    SandboxExecutionClientConfig,
    SandboxExecutionClientFactory,
)
from nautilus_trader.common import Environment
from nautilus_trader.infrastructure import RedisCacheConfig
from nautilus_trader.live import LiveNode
from nautilus_trader.model import (
    AccountType,
    Currency,
    InstrumentId,
    Money,
    OmsType,
    OrderSide,
    Quantity,
    TraderId,
    Venue,
)
from nautilus_trader.trading import Strategy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seed", "restore"))
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--trader-id", required=True)
    parser.add_argument("--order-id", help="client order ID printed by seed")
    args = parser.parse_args()
    if nautilus_trader.__version__ != "2.0.0rc5":
        raise RuntimeError("this probe requires NautilusTrader 2.0.0rc5")
    if args.mode == "restore" and not args.order_id:
        parser.error("restore requires --order-id")

    venue = Venue("SIM")
    usdt = Currency.from_str("USDT")

    class MissingInstrumentOrder(Strategy):
        def on_start(self) -> None:
            order = self.order_factory.market(
                instrument_id=InstrumentId.from_str("BTC-USDT.SIM"),
                order_side=OrderSide.BUY,
                quantity=Quantity.from_str("1.000"),
            )
            self.submit_order(order)

        def on_order_denied(self, event: object) -> None:
            if "INSTRUMENT_NOT_FOUND" not in str(event.reason):
                raise AssertionError(f"unexpected denial: {event.reason}")
            print("TL001A_PROBE=" + json.dumps({
                "mode": "seed",
                "client_order_id": str(event.client_order_id),
                "status": "DENIED",
                "reason": str(event.reason),
            }, sort_keys=True), flush=True)
            # Give the unbuffered cache adapter time to complete its write,
            # then simulate abrupt process loss without node shutdown/dispose.
            time.sleep(0.5)
            os._exit(23)

    builder = LiveNode.builder("TideLabCacheProbe", TraderId(args.trader_id), Environment.SANDBOX)
    builder.with_cache_database_factory(RedisCacheConfig(host="127.0.0.1", port=args.port))
    builder.with_reconciliation(False)
    builder.with_delay_post_stop_secs(0)
    builder.add_simulated_exec_client(
        "SIM",
        SandboxExecutionClientFactory(),
        SandboxExecutionClientConfig(
            venue=venue,
            starting_balances=[Money(10_000 if args.mode == "seed" else 2_000, usdt)],
            account_type=AccountType.CASH,
            oms_type=OmsType.NETTING,
        ),
    )
    node = builder.build()
    if args.mode == "seed":
        node.add_strategy(MissingInstrumentOrder())
    handle = node.handle()

    def stop_later() -> None:
        time.sleep(5 if args.mode == "seed" else 1)
        handle.stop()

    threading.Thread(target=stop_later, daemon=True).start()

    try:
        node.run()
        if args.mode == "seed":
            raise AssertionError("the synthetic denial did not occur")
        orders = node.cache.orders(venue=venue)
        account = node.cache.account_for_venue(venue)
        if (len(orders) != 1 or str(orders[0].client_order_id) != args.order_id
                or orders[0].status.name != "DENIED"):
            raise AssertionError("the closed synthetic order was not restored")
        print("TL001A_PROBE=" + json.dumps({
            "mode": "restore",
            "client_order_id": str(orders[0].client_order_id),
            "status": orders[0].status.name,
            "account_total": str(account.balance_total(usdt)),
        }, sort_keys=True), flush=True)
    finally:
        node.dispose()


if __name__ == "__main__":
    main()
