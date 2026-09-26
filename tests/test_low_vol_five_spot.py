"""Invented bars only: timing, fixed rank and full-fill accounting boundaries."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from tidelab.low_vol_five_spot import (BASE_COST, MARKETS, HourlyBar,
                                      decision, measure, passive_fills,
                                      rank, replay)


FIRST = datetime(2026, 1, 1, tzinfo=timezone.utc)
SECOND = datetime(2026, 2, 1, tzinfo=timezone.utc)
TERMINAL = datetime(2026, 3, 1, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)


def invented_bars(*, switch: bool = False):
    start = FIRST - timedelta(days=60) - HOUR
    count = int((TERMINAL + HOUR - start) / HOUR) + 1
    result = {}
    for market in MARKETS:
        series = []
        for index in range(count):
            when = start + index * HOUR
            price = Decimal("100")
            if switch and market == MARKETS[0] and FIRST <= when < SECOND:
                price = Decimal("110") if when.day % 2 else Decimal("100")
            series.append(HourlyBar(when, price, price, price, price))
        result[market] = series
    return result


def test_rank_requires_all_five_and_uses_fixed_tie_order():
    flat = {market: [Decimal("100")] * 61 for market in MARKETS}
    chosen, values = rank(flat)
    assert chosen == MARKETS[0]
    assert values == (Decimal(0),) * 5
    flat[MARKETS[0]][-1] = Decimal("110")
    assert rank(flat)[0] == MARKETS[1]
    with pytest.raises(ValueError, match="61 daily closes"):
        rank({market: flat[market] for market in MARKETS[:-1]})


def test_replay_delays_fill_rebalances_and_sells_before_buy():
    outcome = replay(invented_bars(switch=True), FIRST, TERMINAL)
    assert [decision.selected for decision in outcome.decisions] == [MARKETS[0], MARKETS[1]]
    assert outcome.decisions[0].target_value == Decimal("2500")
    assert outcome.decisions[1].target_value < Decimal("2500")  # first fill paid costs
    assert [(fill.time, fill.market, fill.side) for fill in outcome.fills] == [
        (FIRST + HOUR, MARKETS[0], "buy"),
        (SECOND + HOUR, MARKETS[0], "sell"),
        (SECOND + HOUR, MARKETS[1], "buy"),
    ]
    assert outcome.cash >= 0
    assert outcome.market == MARKETS[1]
    assert outcome.quantity > 0
    assert outcome.fees == sum(fill.fee for fill in outcome.fills)
    assert outcome.turnover == sum(fill.quantity * fill.price for fill in outcome.fills)
    assert outcome.terminal_equity == outcome.cash + outcome.quantity * 100
    assert BASE_COST == {"fee": Decimal("0.0025"),
                         "half_spread": Decimal("0.0005"),
                         "slippage": Decimal("0.0005")}


@pytest.mark.parametrize("status", ["failed", "partial", "ambiguous"])
def test_nonfinal_sell_blocks_replacement(status):
    with pytest.raises(ValueError, match="sell not final"):
        replay(invented_bars(switch=True), FIRST, TERMINAL, sell_outcome=status)


def test_same_asset_rebalances_and_never_fills_at_signal():
    outcome = replay(invented_bars(), FIRST, TERMINAL)
    assert [decision.selected for decision in outcome.decisions] == [MARKETS[0]] * 2
    assert [fill.side for fill in outcome.fills] == ["buy", "sell"]
    assert outcome.fills[0].time == FIRST + HOUR
    assert outcome.fills[1].time == SECOND + HOUR  # same-name monthly rebalance
    assert outcome.cash > 0


def test_missing_hour_or_invalid_bar_fails_closed():
    bars = invented_bars()
    del bars[MARKETS[-1]][100]
    with pytest.raises(ValueError, match="missing, duplicate"):
        replay(bars, FIRST, TERMINAL)
    bars = invented_bars()
    bad = bars[MARKETS[-1]][100]
    bars[MARKETS[-1]][100] = HourlyBar(bad.start, Decimal(0), bad.high, bad.low, bad.close)
    with pytest.raises(ValueError, match="invalid hourly price"):
        replay(bars, FIRST, TERMINAL)


def test_month_clock_and_warmup_are_exact():
    bars = invented_bars()
    with pytest.raises(ValueError, match="monthly 00:00"):
        replay(bars, FIRST + HOUR, TERMINAL)
    for market in MARKETS:
        del bars[market][0]
    with pytest.raises(ValueError, match="warmup"):
        replay(bars, FIRST, TERMINAL)


def test_same_clock_passive_comparators_and_replay_ledger_agree():
    bars = invented_bars(switch=True)
    run = replay(bars, FIRST, TERMINAL)
    scored = measure(bars, run.fills, FIRST, TERMINAL)
    assert (scored.cash, scored.terminal_equity, scored.fees, scored.turnover) == (
        run.cash, run.terminal_equity, run.fees, run.turnover)
    btc = measure(bars, passive_fills(bars, FIRST, BASE_COST, "btc"), FIRST, TERMINAL)
    equal = measure(bars, passive_fills(bars, FIRST, BASE_COST, "equal"), FIRST, TERMINAL)
    cash = measure(bars, passive_fills(bars, FIRST, BASE_COST, "cash"), FIRST, TERMINAL)
    assert btc.turnover > equal.turnover > 0
    assert cash.net_return == cash.max_drawdown == cash.turnover == 0
    assert decision(scored, scored, equal, btc,
                    [item.selected for item in run.decisions]) == "rejected"
    delayed = replay(bars, FIRST, TERMINAL, fill_hour=2,
                     extra_adverse=Decimal("0.001"))
    assert delayed.fills[0].time == FIRST + 2 * HOUR
    assert delayed.terminal_equity < run.terminal_equity
