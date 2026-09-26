"""Offline five-spot volatility allocation scenario; no broker or order path.

This is TideLab's five-market interpretation of Pyo and Jang (2026), not a
replication of their broad-universe result. Inputs must already be validated,
closed, same-source hourly bars. The replay additionally rejects gaps and
invalid prices; source/provenance checks belong to the private data reader.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN, localcontext
from typing import Mapping, Sequence


MARKETS = ("okx:BTC-USDT", "okx:ETH-USDT", "okx:BNB-USDT",
           "okx:XRP-USDT", "okx:SOL-USDT")
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
UNIT = Decimal("0.00000001")
SLEEVE = Decimal("0.25")
INITIAL_CASH = Decimal("10000")
BASE_COST = {"fee": Decimal("0.0025"), "half_spread": Decimal("0.0005"),
             "slippage": Decimal("0.0005")}
STRESS_COST = {name: value * 2 for name, value in BASE_COST.items()}


@dataclass(frozen=True)
class HourlyBar:
    start: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True)
class Fill:
    time: datetime
    market: str
    side: str
    quantity: Decimal
    price: Decimal
    fee: Decimal


@dataclass(frozen=True)
class Decision:
    time: datetime
    selected: str
    volatilities: tuple[Decimal, ...]
    target_value: Decimal


@dataclass(frozen=True)
class Replay:
    decisions: tuple[Decision, ...]
    fills: tuple[Fill, ...]
    cash: Decimal
    market: str | None
    quantity: Decimal
    terminal_equity: Decimal
    fees: Decimal
    turnover: Decimal


@dataclass(frozen=True)
class Measures:
    net_return: Decimal
    max_drawdown: Decimal
    terminal_equity: Decimal
    cash: Decimal
    fees: Decimal
    turnover: Decimal
    monthly_marks: tuple[tuple[datetime, Decimal], ...]


def _month_after(when: datetime) -> datetime:
    return (when.replace(year=when.year + 1, month=1) if when.month == 12
            else when.replace(month=when.month + 1))


def _check_time(when: datetime) -> None:
    if when.tzinfo != timezone.utc or when.minute or when.second or when.microsecond:
        raise ValueError("timestamps must be aligned UTC hours")


def _check_cost(cost: Mapping[str, Decimal]) -> None:
    if set(cost) != set(BASE_COST) or any(
            not isinstance(value, Decimal) or not value.is_finite() or value < 0
            for value in cost.values()):
        raise ValueError("invalid versioned cost")
    if cost["half_spread"] + cost["slippage"] >= 1:
        raise ValueError("sell price would be nonpositive")


def _index_bars(bars: Mapping[str, Sequence[HourlyBar]]) -> dict[str, dict[datetime, HourlyBar]]:
    if tuple(bars) != MARKETS:
        raise ValueError("fixed five-market order required")
    indexed: dict[str, dict[datetime, HourlyBar]] = {}
    common_start = common_end = None
    for market in MARKETS:
        series = bars[market]
        if not series:
            raise ValueError("empty market history")
        lookup: dict[datetime, HourlyBar] = {}
        previous = None
        for bar in series:
            _check_time(bar.start)
            if previous is not None and bar.start != previous + HOUR:
                raise ValueError("missing, duplicate or reordered hourly bar")
            if (any(not isinstance(price, Decimal) or not price.is_finite() or price <= 0
                    for price in (bar.open, bar.high, bar.low, bar.close))
                    or bar.high < max(bar.open, bar.close)
                    or bar.low > min(bar.open, bar.close)):
                raise ValueError("invalid hourly price")
            lookup[bar.start] = bar
            previous = bar.start
        if common_start is None:
            common_start, common_end = series[0].start, series[-1].start
        elif (series[0].start, series[-1].start) != (common_start, common_end):
            raise ValueError("five-market hourly window differs")
        indexed[market] = lookup
    return indexed


def rank(closes: Mapping[str, Sequence[Decimal]]) -> tuple[str, tuple[Decimal, ...]]:
    """Rank exactly 60 closed daily log returns; exact ties keep plan order."""
    if tuple(closes) != MARKETS or any(len(closes[market]) != 61 for market in MARKETS):
        raise ValueError("all five markets need 61 daily closes")
    volatilities = []
    with localcontext() as context:
        context.prec = 50
        for market in MARKETS:
            prices = closes[market]
            if any(not isinstance(price, Decimal) or not price.is_finite() or price <= 0
                   for price in prices):
                raise ValueError("invalid daily close")
            returns = [(prices[index] / prices[index - 1]).ln()
                       for index in range(1, 61)]
            mean = sum(returns) / Decimal(60)
            variance = sum((value - mean) ** 2 for value in returns) / Decimal(59)
            volatilities.append(+variance.sqrt())
    selected = min(range(5), key=lambda index: volatilities[index])
    return MARKETS[selected], tuple(volatilities)


def replay(bars: Mapping[str, Sequence[HourlyBar]], first_signal: datetime,
           terminal_signal: datetime, cost: Mapping[str, Decimal] = BASE_COST,
           *, initial_cash: Decimal = INITIAL_CASH,
           sell_outcome: str = "filled", fill_hour: int = 1,
           extra_adverse: Decimal = Decimal(0)) -> Replay:
    """Full-fill hypothetical replay. Terminal inventory is marked, not liquidated.

    `sell_outcome` is a synthetic fault probe. A failed, partial or ambiguous
    sale raises before any replacement purchase; no retry is modeled.
    """
    _check_cost(cost)
    for when in (first_signal, terminal_signal):
        _check_time(when)
        if when.day != 1 or when.hour != 0:
            raise ValueError("signals must be monthly 00:00 UTC")
    if first_signal >= terminal_signal or _month_after(first_signal) > terminal_signal:
        raise ValueError("at least one complete monthly hold required")
    if (not isinstance(initial_cash, Decimal) or not initial_cash.is_finite()
            or initial_cash <= 0):
        raise ValueError("invalid initial cash")
    if sell_outcome not in {"filled", "failed", "partial", "ambiguous"}:
        raise ValueError("unknown sell outcome")
    if (fill_hour not in {1, 2} or not isinstance(extra_adverse, Decimal)
            or not extra_adverse.is_finite() or extra_adverse < 0):
        raise ValueError("invalid fill sensitivity")
    indexed = _index_bars(bars)
    # The 61st daily close occurs exactly at the first signal.
    needed_start = first_signal - 60 * DAY - HOUR
    if next(iter(indexed[MARKETS[0]])) > needed_start:
        raise ValueError("missing 60-return warmup")
    if terminal_signal + HOUR not in indexed[MARKETS[0]]:
        raise ValueError("missing terminal mark bar")
    cash, market, quantity = initial_cash, None, Decimal(0)
    fills: list[Fill] = []
    decisions: list[Decision] = []
    fees = turnover = Decimal(0)
    signal = first_signal
    adverse = cost["half_spread"] + cost["slippage"] + extra_adverse
    if adverse >= 1:
        raise ValueError("sell price would be nonpositive")
    while signal < terminal_signal:
        closes = {}
        for candidate in MARKETS:
            try:
                closes[candidate] = tuple(indexed[candidate][signal - day * DAY - HOUR].close
                                          for day in range(60, -1, -1))
            except KeyError as exc:
                raise ValueError("missing closed daily signal history") from exc
        selected, volatilities = rank(closes)
        signal_marks = {candidate: closes[candidate][-1] for candidate in MARKETS}
        equity = cash + (quantity * signal_marks[market] if market else 0)
        target = equity * SLEEVE
        decisions.append(Decision(signal, selected, volatilities, target))
        fill_time = signal + fill_hour * HOUR
        try:
            open_price = indexed[selected][fill_time].open
            if market:
                held_open = indexed[market][fill_time].open
        except KeyError as exc:
            raise ValueError("missing later execution bar") from exc
        sell_quantity = Decimal(0)
        if market:
            desired_held = (target / signal_marks[market]).quantize(UNIT, rounding=ROUND_DOWN) if market == selected else Decimal(0)
            sell_quantity = max(Decimal(0), quantity - desired_held)
        if sell_quantity:
            if sell_outcome != "filled":
                raise ValueError("sell not final; replacement buy blocked")
            price = held_open * (1 - adverse)
            fee = sell_quantity * price * cost["fee"]
            cash += sell_quantity * price - fee
            quantity -= sell_quantity
            fills.append(Fill(fill_time, market, "sell", sell_quantity, price, fee))
            fees += fee
            turnover += sell_quantity * price
            if quantity == 0:
                market = None
        desired_selected = (target / signal_marks[selected]).quantize(UNIT, rounding=ROUND_DOWN)
        owned_selected = quantity if market == selected else Decimal(0)
        buy_quantity = max(Decimal(0), desired_selected - owned_selected)
        if buy_quantity:
            price = open_price * (1 + adverse)
            affordable = (cash / (price * (1 + cost["fee"]))).quantize(UNIT, rounding=ROUND_DOWN)
            buy_quantity = min(buy_quantity, affordable)
            if buy_quantity <= 0:
                raise ValueError("target below executable quantity")
            fee = buy_quantity * price * cost["fee"]
            cash -= buy_quantity * price + fee
            quantity += buy_quantity
            market = selected
            fills.append(Fill(fill_time, selected, "buy", buy_quantity, price, fee))
            fees += fee
            turnover += buy_quantity * price
        if cash < 0 or quantity < 0:
            raise AssertionError("negative cash or inventory")
        signal = _month_after(signal)
    terminal_price = indexed[market][terminal_signal + HOUR].open if market else Decimal(0)
    terminal_equity = cash + quantity * terminal_price
    return Replay(tuple(decisions), tuple(fills), cash, market, quantity,
                  terminal_equity, fees, turnover)


def passive_fills(bars: Mapping[str, Sequence[HourlyBar]], signal: datetime,
                  cost: Mapping[str, Decimal], kind: str) -> tuple[Fill, ...]:
    """One 25% BTC or five 5% initial allocation, with no later rebalance."""
    _check_cost(cost)
    if kind not in {"btc", "equal", "cash"}:
        raise ValueError("unknown passive comparator")
    if kind == "cash":
        return ()
    indexed = _index_bars(bars)
    portions = {market: (Decimal("0.25") if kind == "btc" else Decimal("0.05"))
                for market in (MARKETS[:1] if kind == "btc" else MARKETS)}
    fills = []
    cash = INITIAL_CASH
    for market, portion in portions.items():
        mark = indexed[market][signal - HOUR].close
        price = indexed[market][signal + HOUR].open * (
            1 + cost["half_spread"] + cost["slippage"])
        desired = (INITIAL_CASH * portion / mark).quantize(UNIT, rounding=ROUND_DOWN)
        affordable = (cash / (price * (1 + cost["fee"]))).quantize(UNIT, rounding=ROUND_DOWN)
        quantity = min(desired, affordable)
        if quantity <= 0:
            raise ValueError("passive target below executable quantity")
        fee = quantity * price * cost["fee"]
        cash -= quantity * price + fee
        fills.append(Fill(signal + HOUR, market, "buy", quantity, price, fee))
    return tuple(fills)


def measure(bars: Mapping[str, Sequence[HourlyBar]], fills: Sequence[Fill],
            first_signal: datetime, terminal_signal: datetime) -> Measures:
    """Mark the same hourly path for the strategy and all passive comparators."""
    indexed = _index_bars(bars)
    cash = INITIAL_CASH
    holdings = {market: Decimal(0) for market in MARKETS}
    fees = turnover = Decimal(0)
    peak = INITIAL_CASH
    max_drawdown = Decimal(0)
    monthly_marks = []
    cursor = 0
    when = first_signal
    while when <= terminal_signal:
        if when.day == 1 and when.hour == 0:
            monthly_marks.append((when, cash + sum(
                holdings[market] * indexed[market][when - HOUR].close
                for market in MARKETS)))
        while cursor < len(fills) and fills[cursor].time == when:
            fill = fills[cursor]
            if fill.market not in holdings or fill.side not in {"buy", "sell"}:
                raise ValueError("invalid fill")
            if fill.quantity <= 0 or fill.price <= 0 or fill.fee < 0:
                raise ValueError("invalid fill arithmetic")
            notional = fill.quantity * fill.price
            if fill.side == "buy":
                cash -= notional + fill.fee
                holdings[fill.market] += fill.quantity
            else:
                cash += notional - fill.fee
                holdings[fill.market] -= fill.quantity
            if cash < 0 or holdings[fill.market] < 0:
                raise ValueError("negative settled cash or inventory")
            fees += fill.fee
            turnover += notional
            cursor += 1
        value = cash + sum(holdings[market] * indexed[market][when].close
                           for market in MARKETS)
        peak = max(peak, value)
        max_drawdown = max(max_drawdown, (peak - value) / peak)
        when += HOUR
    if cursor != len(fills):
        raise ValueError("fill outside scored hourly window")
    terminal = cash + sum(holdings[market] * indexed[market][terminal_signal + HOUR].open
                          for market in MARKETS)
    peak = max(peak, terminal)
    max_drawdown = max(max_drawdown, (peak - terminal) / peak)
    return Measures((terminal - INITIAL_CASH) / INITIAL_CASH, max_drawdown,
                    terminal, cash, fees, turnover, tuple(monthly_marks))


def decision(strategy_base: Measures, strategy_stress: Measures,
             equal_base: Measures, btc_base: Measures,
             chosen: Sequence[str]) -> str:
    """Apply the frozen exploratory gate without retuning on outcomes."""
    changes = sum(a != b for a, b in zip(chosen, chosen[1:]))
    if (strategy_base.net_return <= max(Decimal(0), equal_base.net_return,
                                        btc_base.net_return)
            or strategy_stress.net_return <= 0
            or strategy_base.max_drawdown > equal_base.max_drawdown
            or len(set(chosen)) < 2 or changes < 3):
        return "rejected"
    return "survived_for_further_observation"
