"""Shared fixed-order descriptive review. No selection or trial authority."""
from decimal import Decimal
import json


def review_scenarios(summary: dict, market_order: list[str], *, minimum_round_trips: int,
                     scope="exposed_history_exploratory_triage_not_edge_evidence") -> dict:
    markets = []
    for m_index, market in enumerate(market_order):
        rows = summary["jobs"][m_index * 6:(m_index + 1) * 6]
        if (len(summary["jobs"]) != len(market_order) * 6 or len(rows) != 6
                or any(x.get("index") != m_index * 6 + i or x["status"] != "completed" for i, x in enumerate(rows))):
            markets.append({"market": market, "status": "incomplete"}); continue
        try:
            metrics = [x["metrics"] for x in rows]
            for value in metrics:
                if (type(value["round_trips"]) is not int or value["round_trips"] < 0
                        or not Decimal(value["net_return"]).is_finite()
                        or not Decimal(value["max_drawdown"]).is_finite()
                        or not 0 <= Decimal(value["max_drawdown"]) <= 1):
                    raise ValueError("invalid_review_metric")
        except (KeyError, TypeError, ValueError, ArithmeticError):
            markets.append({"market": market, "status": "incomplete"}); continue
        base, stress, cash, cash_stress, passive, passive_stress = metrics
        excess = Decimal(base["net_return"]) - Decimal(passive["net_return"])
        if base["round_trips"] < minimum_round_trips: status = "inconclusive"
        elif (Decimal(base["net_return"]) > 0 and excess > 0 and Decimal(stress["net_return"]) > 0
              and Decimal(base["max_drawdown"]) <= Decimal("0.15")): status = "eligible_for_deeper_review"
        else: status = "not_nominated"
        markets.append({"market": market, "status": status, "baseline_excess_return": str(excess)})
    incomplete = any(x["status"] == "incomplete" for x in markets)
    return {"status": "incomplete" if incomplete else "reviewed", "markets": markets,
            "eligibility_provisional": incomplete, "automatic_promotion": False,
            "scope": scope}


def trace_diagnostics(path, *, fee_rate: Decimal, adverse_rate: Decimal) -> dict:
    """Descriptive P&L decomposition of a retained long/cash trace, no rerun.

    Fee-inclusive entry basis; open inventory is never counted as a closed trip.
    Terminal hypothetical exit friction is disclosed without forcing a sale.
    """
    basis = Decimal(0)
    largest = None
    final = None
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            fill = row["fill"]
            if fill:
                notional = Decimal(fill["quantity"]) * Decimal(fill["price"])
                fee = Decimal(fill["fee"])
                if fill["side"] == "buy":
                    basis += notional + fee
                elif fill["side"] == "sell":
                    profit = notional - fee - basis
                    largest = profit if largest is None else max(largest, profit)
                    basis = Decimal(0)
                else:
                    raise ValueError("unknown_fill_side")
            final = row
    if final is None:
        raise ValueError("empty_trace")
    marked = Decimal(final["equity"]) - Decimal(final["cash"])
    return {"largest_closed_trade_net_pnl": None if largest is None else str(largest),
            "terminal_unrealized_net_of_entry_fee": str(marked - basis),
            "terminal_hypothetical_exit_cost": str(marked * (1 - (1 - adverse_rate) * (1 - fee_rate))),
            "meaning": "retained_trace_diagnostics_not_additional_trial"}

