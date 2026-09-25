"""An independent private audit catches altered H1 account evidence."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D, ROUND_DOWN

import pytest

from tidelab.h1_trial_review import _benchmark, _metrics, review_case


def synthetic_round_trip():
    first = datetime(2026, 1, 1, tzinfo=timezone.utc)
    score_start = first + timedelta(hours=168)
    score_end = score_start + timedelta(hours=2)
    bars = [{"start_utc": (first + timedelta(hours=index)).isoformat(),
             "open": "102" if index == 169 else "98" if index == 170 else "100",
             "close": "102" if index == 168 else "98" if index == 169 else "100",
             "closed": True} for index in range(171)]
    buy, sell, rate = D("102.102"), D("97.902"), D("0.0025")
    units = (D("2500") * D("100000000") / buy).to_integral_value(rounding=ROUND_DOWN) / D("100000000")
    buy_fee, sell_fee = units * buy * rate, units * sell * rate
    cash_after_buy = D("10000") - units * buy - buy_fee
    final = cash_after_buy + units * sell - sell_fee
    mark_after_buy = cash_after_buy + units * D("98")
    exposure = units * D("98") / mark_after_buy
    replay = {"Cash": final, "Units": D(0), "TotalFees": buy_fee + sell_fee,
        "Fills": [
            {"SignalClosedUtc": bars[169]["start_utc"],
             "FilledAtUtc": bars[169]["start_utc"], "Intent": "EnterLong",
             "Units": units, "FillPrice": buy, "Fee": buy_fee,
             "CashAfter": cash_after_buy, "UnitsAfter": units, "Terminal": False},
            {"SignalClosedUtc": bars[170]["start_utc"],
             "FilledAtUtc": bars[170]["start_utc"], "Intent": "ExitToCash",
             "Units": units, "FillPrice": sell, "Fee": sell_fee,
             "CashAfter": final, "UnitsAfter": D(0), "Terminal": False}],
        "Decisions": [{"ClosedAtUtc": bars[169]["start_utc"], "Intent": "EnterLong",
                       "Risk": "Clear", "EntriesHalted": False, "ClosedHours": 169,
                       "Mean": (D("16700") + D("102")) / D("168"),
                       "TargetGrossExposure": D("0.25")},
                      {"ClosedAtUtc": bars[170]["start_utc"], "Intent": "ExitToCash",
                       "Risk": "Clear", "EntriesHalted": False, "ClosedHours": 170,
                       "Mean": D("100"), "TargetGrossExposure": D(0)}],
        "Marks": [{"ClosedAtUtc": bars[169]["start_utc"], "Cash": D("10000"),
                   "Units": D(0), "Equity": D("10000"), "GrossExposure": D(0)},
                  {"ClosedAtUtc": bars[170]["start_utc"], "Cash": cash_after_buy,
                   "Units": units, "Equity": mark_after_buy,
                   "GrossExposure": exposure}]}
    metrics = {"Strategy": _metrics([D("10000"), mark_after_buy, final],
        [D(0), exposure], final, units * (buy + sell) / D("10000"),
        buy_fee + sell_fee, 1, final - D("10000")),
        "Cash": _metrics([D("10000")] * 3, [D(0)] * 2, D("10000"),
            D(0), D(0), 0, D(0)),
        "QuarterHold": _benchmark(bars, D("0.25"), D("0.001"), rate),
        "FullHold": _benchmark(bars, D(1), D("0.001"), rate)}
    return bars, score_start, score_end, replay, metrics


def test_independent_review_accepts_a_settled_synthetic_round_trip() -> None:
    bars, start, end, replay, metrics = synthetic_round_trip()
    review_case(bars, start, end, replay, metrics, D("0.001"), D("0.0025"))


def test_independent_review_rejects_changed_fee_and_mark() -> None:
    bars, start, end, replay, metrics = synthetic_round_trip()
    changed = deepcopy(replay)
    changed["Fills"][0]["Fee"] += D("0.01")
    with pytest.raises(ValueError, match="fill fee"):
        review_case(bars, start, end, changed, metrics, D("0.001"), D("0.0025"))
    changed = deepcopy(replay)
    changed["Marks"][1]["Equity"] += D("1")
    with pytest.raises(ValueError, match="marked equity"):
        review_case(bars, start, end, changed, metrics, D("0.001"), D("0.0025"))
