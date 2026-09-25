"""Independent, private ledger review for one frozen H1 historical result."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN, getcontext
from hashlib import sha256
import json
from pathlib import Path

from tidelab.experiment_identity import build_experiment_identity


STARTING_CASH = Decimal("10000")
SCALE = Decimal("100000000")
getcontext().prec = 50
COSTS = {"base": (Decimal("0.001"), Decimal("0.0025")),
         "stress": (Decimal("0.002"), Decimal("0.005"))}


def _number(value: object) -> Decimal:
    return Decimal(str(value))


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("review expected UTC timestamps")
    return parsed


def _same(actual: object, expected: Decimal, name: str,
          tolerance: Decimal = Decimal("1e-20")) -> None:
    if abs(_number(actual) - expected) > tolerance:
        raise ValueError(f"private H1 {name} does not reconcile")


def _metrics(equities: list[Decimal], exposures: list[Decimal], final: Decimal,
             turnover: Decimal, fees: Decimal, round_trips: int,
             largest: Decimal) -> dict[str, Decimal | int]:
    peak = STARTING_CASH
    maximum = Decimal(0)
    longest = current = total = 0
    for index, equity in enumerate(equities):
        if equity >= peak:
            peak, current = equity, 0
        else:
            maximum = max(maximum, (peak - equity) / peak)
            if index < len(equities) - 1:
                current += 1
                total += 1
            longest = max(longest, current)
    return {"FinalCash": final, "NetReturn": (final - STARTING_CASH) / STARTING_CASH,
            "MaximumDrawdown": maximum, "UnderwaterHours": total,
            "LongestUnderwaterHours": longest,
            "AverageGrossExposure": sum(exposures, Decimal(0)) / len(exposures),
            "Turnover": turnover, "Fees": fees, "ClosedRoundTrips": round_trips,
            "LargestRoundTripPnl": largest,
            "NetWithoutLargestRoundTrip": final - STARTING_CASH - largest}


def _compare(actual: dict[str, object], expected: dict[str, Decimal | int], name: str) -> None:
    if set(actual) != set(expected):
        raise ValueError(f"private H1 {name} metric fields differ")
    for field, value in expected.items():
        _same(actual[field], Decimal(value), f"{name}.{field}")


def _benchmark(bars: list[dict[str, object]], allocation: Decimal,
               adverse: Decimal, fee_rate: Decimal) -> dict[str, Decimal | int]:
    buy = _number(bars[168]["open"]) * (1 + adverse)
    terminal = _number(bars[-1]["open"]) * (1 - adverse)
    target = STARTING_CASH * allocation
    affordable = STARTING_CASH / (buy * (1 + fee_rate))
    units = (min(target / buy, affordable) * SCALE).to_integral_value(rounding=ROUND_DOWN) / SCALE
    fee_buy = units * buy * fee_rate
    cash = STARTING_CASH - units * buy - fee_buy
    if cash < 0 or units <= 0:
        raise ValueError("private H1 benchmark would borrow")
    marks = [cash + units * _number(bar["close"]) for bar in bars[168:-1]]
    exposure = [units * _number(bar["close"]) / equity
                for bar, equity in zip(bars[168:-1], marks)]
    fee_sell = units * terminal * fee_rate
    final = cash + units * terminal - fee_sell
    return _metrics(marks + [final], exposure, final,
                    units * (buy + terminal) / STARTING_CASH,
                    fee_buy + fee_sell, 1, final - STARTING_CASH)


def review_case(bars: list[dict[str, object]], score_start: datetime,
                score_end: datetime, replay: dict[str, object],
                reported: dict[str, dict[str, object]],
                adverse: Decimal, fee_rate: Decimal) -> None:
    hours = int((score_end - score_start) / timedelta(hours=1))
    if len(bars) != 168 + hours + 1 or len(replay["Decisions"]) != hours or (
        len(replay["Marks"]) != hours
    ):
        raise ValueError("private H1 scored hour count differs")
    by_open = {_utc(bar["start_utc"]): bar for bar in bars}
    fills = replay["Fills"]
    decisions = replay["Decisions"]
    marks = replay["Marks"]
    cash, units, fees = STARTING_CASH, Decimal(0), Decimal(0)
    entry_cost: Decimal | None = None
    round_trips = 0
    largest = Decimal(0)
    turnover = Decimal(0)
    if [_utc(fill["FilledAtUtc"]) for fill in fills] != sorted(
        _utc(fill["FilledAtUtc"]) for fill in fills
    ):
        raise ValueError("private H1 fills are out of order")
    for fill in fills:
        opened = _utc(fill["FilledAtUtc"])
        signal = _utc(fill["SignalClosedUtc"])
        if opened not in by_open or opened < score_start or opened > score_end:
            raise ValueError("private H1 fill time is outside the partition")
        terminal = bool(fill["Terminal"])
        if terminal:
            if opened != score_end or fill["Intent"] != "ExitToCash":
                raise ValueError("private H1 terminal exit differs")
        elif opened != signal:
            raise ValueError("private H1 fill did not follow its signal")
        quantity = _number(fill["Units"])
        if quantity <= 0 or quantity * SCALE != (quantity * SCALE).to_integral_value():
            raise ValueError("private H1 fill quantity violates eight decimals")
        entering = fill["Intent"] == "EnterLong"
        if not entering and fill["Intent"] != "ExitToCash":
            raise ValueError("private H1 hold became a fill")
        price = _number(by_open[opened]["open"]) * (1 + adverse if entering else 1 - adverse)
        fee = quantity * price * fee_rate
        _same(fill["FillPrice"], price, "fill price")
        _same(fill["Fee"], fee, "fill fee")
        if entering:
            if units != 0 or entry_cost is not None:
                raise ValueError("private H1 entry overlaps inventory")
            expected_quantity = ((cash * Decimal("0.25") * SCALE / price)
                                 .to_integral_value(rounding=ROUND_DOWN) / SCALE)
            if quantity != expected_quantity:
                raise ValueError("private H1 entry quantity differs")
            entry_cost = quantity * price + fee
            cash -= entry_cost
            units += quantity
        else:
            if entry_cost is None or quantity != units:
                raise ValueError("private H1 exit lacks exact inventory")
            proceeds = quantity * price - fee
            pnl = proceeds - entry_cost
            if round_trips == 0 or pnl > largest:
                largest = pnl
            round_trips += 1
            cash += proceeds
            units -= quantity
            entry_cost = None
        fees += fee
        turnover += quantity * price / STARTING_CASH
        if cash < 0 or units < 0:
            raise ValueError("private H1 account borrowed")
        _same(fill["CashAfter"], cash, "fill cash")
        _same(fill["UnitsAfter"], units, "fill units")
    if units != 0 or entry_cost is not None:
        raise ValueError("private H1 account did not settle")
    _same(replay["Cash"], cash, "final cash")
    _same(replay["Units"], units, "final units")
    _same(replay["TotalFees"], fees, "total fees")

    # Reconstruct each mark from fills at or before that hour's opening.
    marked_cash, marked_units = STARTING_CASH, Decimal(0)
    next_fill = 0
    equities: list[Decimal] = []
    exposures: list[Decimal] = []
    closes = [_number(bar["close"]) for bar in bars]
    peak = STARTING_CASH
    halted = False
    for index, (decision, mark) in enumerate(zip(decisions, marks)):
        bar = bars[168 + index]
        opened = _utc(bar["start_utc"])
        closed = opened + timedelta(hours=1)
        if _utc(decision["ClosedAtUtc"]) != closed or _utc(mark["ClosedAtUtc"]) != closed:
            raise ValueError("private H1 decision/mark clock differs")
        while next_fill < len(fills) and _utc(fills[next_fill]["FilledAtUtc"]) == opened:
            marked_cash = _number(fills[next_fill]["CashAfter"])
            marked_units = _number(fills[next_fill]["UnitsAfter"])
            next_fill += 1
        equity = marked_cash + marked_units * _number(bar["close"])
        exposure = marked_units * _number(bar["close"]) / equity
        _same(mark["Cash"], marked_cash, "marked cash")
        _same(mark["Units"], marked_units, "marked units")
        _same(mark["Equity"], equity, "marked equity")
        _same(mark["GrossExposure"], exposure, "marked exposure")
        if equity <= 0 or exposure > 1:
            raise ValueError("private H1 marked account invalid")
        equities.append(equity)
        exposures.append(exposure)
        peak = max(peak, equity)
        if equity <= peak * Decimal("0.8"):
            halted = True
        mean = sum(closes[index + 1:index + 169], Decimal(0)) / Decimal(168)
        close = closes[index + 168]
        expected_intent = ("ExitToCash" if marked_units > 0 else "Hold") if halted else (
            "ExitToCash" if marked_units > 0 and close <= mean else
            "EnterLong" if marked_units == 0 and close > mean else "Hold")
        expected_risk = "DrawdownHalt" if halted else "Clear"
        target = (Decimal("0.25") if expected_intent == "EnterLong" else
                  Decimal(0) if expected_intent == "ExitToCash" else None)
        if (decision["Intent"] != expected_intent or
            decision["Risk"] != expected_risk or
            decision["EntriesHalted"] != halted or
            decision["ClosedHours"] != index + 169):
            raise ValueError("private H1 frozen signal or risk decision differs")
        _same(decision["Mean"], mean, "168-hour mean")
        if (target is None and decision["TargetGrossExposure"] is not None) or (
            target is not None and _number(decision["TargetGrossExposure"]) != target
        ):
            raise ValueError("private H1 target exposure differs")
        if decision["Intent"] != "Hold" and not any(
            fill["Intent"] == decision["Intent"] and
            _utc(fill["SignalClosedUtc"]) == closed and not fill["Terminal"]
            for fill in fills
        ):
            raise ValueError("private H1 proposal lacks a following-open fill")
    if any(_utc(fill["FilledAtUtc"]) != score_end for fill in fills[next_fill:]):
        raise ValueError("private H1 unmarked fill precedes the terminal open")
    _compare(reported["Strategy"], _metrics(equities + [cash], exposures,
        cash, turnover, fees, round_trips, largest), "strategy")
    _compare(reported["Cash"], _metrics([STARTING_CASH] * (hours + 1),
        [Decimal(0)] * hours, STARTING_CASH, Decimal(0), Decimal(0), 0,
        Decimal(0)), "cash")
    _compare(reported["QuarterHold"], _benchmark(bars, Decimal("0.25"),
        adverse, fee_rate), "quarter hold")
    _compare(reported["FullHold"], _benchmark(bars, Decimal(1),
        adverse, fee_rate), "full hold")


def review_bundle(bundle: Path, registry: Path, attempt_id: str) -> str:
    """Return a hash only after source, record, replay, and metrics agree."""
    import sqlite3

    input_bytes = (bundle / "input.json").read_bytes()
    result_bytes = (bundle / "result.json").read_bytes()
    source_bytes = (bundle / "source-manifest.json").read_bytes()
    fixture = json.loads(input_bytes)
    result = json.loads(result_bytes, parse_float=Decimal)
    manifest = json.loads(source_bytes)
    identity = json.loads((bundle / "identity.json").read_bytes())
    if identity != build_experiment_identity(**{
        name: identity[name] for name in
        ("engine", "code", "configuration", "data", "cost", "trial")
    }):
        raise ValueError("private H1 experiment identity is invalid")
    result_hash = sha256(result_bytes).hexdigest()
    if (identity["data"]["sha256"] != sha256(source_bytes).hexdigest() or
        manifest["input_sha256"] != sha256(input_bytes).hexdigest() or
        result["input_sha256"] != manifest["input_sha256"] or
        result["identity_sha256"] != identity["identity_sha256"] or
        result["phase"] != fixture["phase"] or
        manifest["phase"] != fixture["phase"] or
        identity["trial"]["trial_id"] !=
        f"h1-v1-okx-btc-usdt-{fixture['phase']}" or
        _utc(result["score_start_utc"]) != _utc(fixture["score_start_utc"]) or
        _utc(result["score_end_utc"]) != _utc(fixture["score_end_utc"]) or
        f"result_sha256={result_hash}" not in (bundle / "attempt.log").read_text()):
        raise ValueError("private H1 identity or result log differs")
    with sqlite3.connect(registry.resolve().as_uri() + "?mode=ro", uri=True) as db:
        row = db.execute("""SELECT a.identity_sha256,a.phase,o.outcome
            FROM trial_attempts a LEFT JOIN trial_outcomes o ON a.attempt_id=o.attempt_id
            WHERE a.attempt_id=?""", (attempt_id,)).fetchone()
    if row != (identity["identity_sha256"], result["phase"], "completed"):
        raise ValueError("private H1 attempt is not completed under this identity")
    start = _utc(fixture["score_start_utc"])
    end = _utc(fixture["score_end_utc"])
    partitions = {"development": ("2023-07-07T16:00:00Z", "2025-01-01T00:00:00Z"),
                  "validation": ("2025-01-01T00:00:00Z", "2026-01-01T00:00:00Z")}
    if fixture["phase"] not in partitions or (start, end) != tuple(
        _utc(value) for value in partitions[fixture["phase"]]
    ):
        raise ValueError("private H1 partition differs from frozen registration")
    if any(_utc(bar["start_utc"]) != start - timedelta(hours=168) +
           timedelta(hours=index) or not bar["closed"]
           for index, bar in enumerate(fixture["bars"])):
        raise ValueError("private H1 input has a gap or unclosed hour")
    for case, (adverse, fee_rate) in COSTS.items():
        review_case(fixture["bars"], start, end,
                    result[f"{case}_replay"], result[f"{case}_metrics"],
                    adverse, fee_rate)
    return result_hash
