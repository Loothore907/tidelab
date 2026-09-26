from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from scripts import tl003_screen
from tidelab.candidate_screen import Bar, replay, passes
from tidelab.trial_registry import TrialRegistry


ZERO = {"fee": Decimal(0), "half_spread": Decimal(0), "slippage": Decimal(0)}
START = datetime(2023, 7, 1, tzinfo=timezone.utc)


def bars(count: int = 725) -> list[Bar]:
    return [Bar(START + timedelta(hours=index), Decimal(100), Decimal(100),
                Decimal(100), Decimal(100)) for index in range(count)]


def change(source: list[Bar], index: int, *, opening: str, close: str) -> None:
    old = source[index]
    op, cl = Decimal(opening), Decimal(close)
    source[index] = Bar(old.start, op, max(op, cl), min(op, cl), cl)


def test_momentum_uses_next_open_and_costed_full_round_trip() -> None:
    source = bars()
    change(source, 720, opening="100", close="101")
    change(source, 721, opening="200", close="99")
    change(source, 722, opening="150", close="100")
    result = replay(source, "momentum-720-v1", ZERO)
    assert result["round_trips"] == 1
    assert Decimal(result["net_return"]) < 0
    assert Decimal(result["fees"]) == 0
    assert Decimal(result["turnover"]) > 0


def test_reversal_remembers_entry_signal_and_exits_after_recovery() -> None:
    source = bars()
    change(source, 720, opening="100", close="90")
    change(source, 721, opening="80", close="95")
    change(source, 722, opening="120", close="120")
    result = replay(source, "reversal-24-v1", ZERO)
    assert result["round_trips"] == 1
    assert Decimal(result["net_return"]) > 0


def test_cost_stress_cannot_improve_same_trade_and_gap_fails_closed() -> None:
    source = bars()
    change(source, 720, opening="100", close="101")
    change(source, 721, opening="100", close="99")
    base = replay(source, "momentum-720-v1", ZERO)
    stressed = replay(source, "momentum-720-v1", {
        "fee": Decimal("0.005"), "half_spread": Decimal("0.001"),
        "slippage": Decimal("0.001")})
    assert Decimal(stressed["net_return"]) < Decimal(base["net_return"])
    source[300] = Bar(source[300].start + timedelta(hours=1), Decimal(100),
                      Decimal(100), Decimal(100), Decimal(100))
    with pytest.raises(ValueError, match="noncontiguous"):
        replay(source, "momentum-720-v1", ZERO)


def test_rejection_and_low_sample_are_distinct() -> None:
    primary = {"net_return": "0.01"}
    assert passes({"round_trips": 9, "net_return": "0.2", "max_drawdown": "0"},
                  {"net_return": "0.1"}, primary) == "inconclusive_low_trade_count"
    assert passes({"round_trips": 10, "net_return": "0.02", "max_drawdown": "0.16"},
                  {"net_return": "0.01"}, primary) == "rejected"
    assert passes({"round_trips": 10, "net_return": "0.02", "max_drawdown": "0.1"},
                  {"net_return": "0.01"}, primary) == "survived"


def test_private_attempt_is_recorded_before_result_and_cannot_repeat(
        tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(tl003_screen, "DATA", tmp_path)
    registry = TrialRegistry(tmp_path / "trials.sqlite3")
    registry.initialize()
    result = tl003_screen._run_one(
        registry, "okx:BTC-USDT", "momentum-720-v1", "development",
        bars(), "a" * 64, "b" * 64, "c" * 40, "d" * 64, "e" * 64,
        datetime(2026, 9, 25, tzinfo=timezone.utc).date(), None)
    assert registry.status(result["attempt_id"]) == "completed"
    assert (tmp_path / "attempts" / f"{result['attempt_id']}.json").is_file()
    with pytest.raises(RuntimeError, match="already launched"):
        tl003_screen._run_one(
            registry, "okx:BTC-USDT", "momentum-720-v1", "development",
            bars(), "a" * 64, "b" * 64, "c" * 40, "d" * 64, "e" * 64,
            datetime(2026, 9, 25, tzinfo=timezone.utc).date(), None)
