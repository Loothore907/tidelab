"""Independent calendar/accounting expectations on invented prices only."""
from dataclasses import replace
from datetime import timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import sqlite3

import pytest

from tidelab import btc_monday as monday, historical_batch as batch, rsi_private as rsi
from tidelab.domain import isoformat_utc, parse_utc
from tidelab.historical_batch_demo import create_demo
from tidelab.package_lean_parity import validate_input, run_parity
from tidelab.strategy_batch import parse_package, replay_package, signal_trace, UnsupportedPackage

ROOT = Path(__file__).resolve().parents[1]


def record():
    return batch.read(ROOT / "research/examples/btc-monday-synthetic-record-v1.json")


def fixture(start="2023-12-31T23:00:00Z", count=26):
    first = parse_utc(start)
    return {"kind": "tidelab_synthetic", "interval_seconds": 3600, "bars": [
        {"start_utc": isoformat_utc(first + timedelta(hours=i)),
         "open": "200" if i == 1 else "50" if i == 25 else "100", "close": "100"}
        for i in range(count)]}


def replay(data=None, **kwargs):
    strategy, bars = validate_input(monday.package(record()), record(), data or fixture())
    trace = []
    replay_package(strategy, bars, emit=trace.append, **kwargs)
    return trace


@pytest.mark.parametrize("start", ["2023-12-31T23:00:00Z", "2024-02-25T23:00:00Z",
                                     "2024-03-10T23:00:00Z", "2024-11-03T23:00:00Z"])
def test_close_clock_next_open_and_independent_accounting(start):
    data = fixture(start)
    trace = replay(data)
    assert [i for i, r in enumerate(trace) if r["action"] == "buy"] == [0]
    assert [i for i, r in enumerate(trace) if r["action"] == "sell"] == [24]
    assert trace[0]["fill"] is None
    buy, sell = trace[1]["fill"], trace[25]["fill"]
    assert buy["utc"] == data["bars"][1]["start_utc"]
    assert sell["utc"] == data["bars"][25]["start_utc"]
    assert Decimal(buy["quantity"]) == Decimal("12.45637155")
    assert Decimal(buy["price"]) == Decimal("200.2")
    assert Decimal(buy["fee"]) == Decimal("6.2344139607750")
    assert Decimal(sell["price"]) == Decimal("49.95")
    assert Decimal(trace[-1]["cash"]) == Decimal("8120.64027125441875")
    assert trace[-1]["units"] == "0"


def test_full_leap_year_no_catchup_or_forced_sale():
    trace = replay(fixture("2024-01-01T00:00:00Z", 8784))
    fills = [r["fill"] for r in trace if r["fill"]]
    assert len(fills) == 104
    assert fills[0]["utc"] == "2024-01-08T00:00:00Z"
    assert fills[-1]["utc"] == "2024-12-31T00:00:00Z"
    assert trace[0]["action"] == trace[-1]["action"] == "hold"
    assert trace[-1]["units"] == "0"
    terminal = replay(fixture(count=25))
    assert terminal[-1]["action"] == "hold"
    assert Decimal(terminal[-1]["units"]) > 0
    assert replay(fixture("2023-12-31T21:00:00Z", count=3))[-1]["action"] == "hold"


def test_readiness_and_price_independent_signal():
    strategy, bars = validate_input(monday.package(record()), record(), fixture())
    assert (strategy.warmup, strategy.preceding_warmup) == (1, 0)
    original = signal_trace(strategy, bars)
    changed = [replace(b, open=Decimal("999"), close=Decimal("1")) for b in bars]
    assert signal_trace(strategy, changed) == original
    assert signal_trace(strategy, bars[:3]) == original[:2]


@pytest.mark.parametrize("field,value", [("weekday", 0), ("weekday", 8), ("weekday", True),
    ("hour", -1), ("hour", 24), ("hour", False), ("extra", 1)])
def test_invalid_calendar_slots_fail_closed(field, value):
    candidate = monday.package(record())
    candidate["rule"]["entry"][field] = value
    with pytest.raises(UnsupportedPackage):
        parse_package(candidate, record())


@pytest.mark.parametrize("schema", [1, 2, 3])
def test_old_schemas_cannot_admit_calendar(schema):
    candidate = monday.package(record())
    candidate["schema_version"] = schema
    with pytest.raises(UnsupportedPackage):
        parse_package(candidate, record())


@pytest.mark.parametrize("damage", ["naive", "offset", "minute", "gap"])
def test_invalid_clock_before_fill(damage):
    strategy, bars = validate_input(monday.package(record()), record(), fixture())
    bars = list(bars)
    when = bars[1].start
    when = {"naive": when.replace(tzinfo=None), "offset": when.astimezone(timezone(timedelta(hours=1))),
            "minute": when + timedelta(minutes=1), "gap": when + timedelta(hours=1)}[damage]
    bars[1] = replace(bars[1], start=when)
    with pytest.raises(ValueError, match="complete UTC hours"):
        replay_package(strategy, bars, emit=lambda r: pytest.fail("emitted before rejection"))


def test_private_admission_stays_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: pytest.fail("database access"))
    for function in (monday.prepare_private, monday.execute_private, monday.UnapprovedMondayPolicy.preflight,
                     monday.UnapprovedMondayPolicy.package, monday.UnapprovedMondayPolicy.read_partition):
        with pytest.raises(ValueError, match="monday_trial_authority_ungranted"):
            function(tmp_path / "authority.json", grant="consumed-rsi", registry=tmp_path / "alternate.sqlite3")


def test_shared_six_job_inventory_and_recovery(tmp_path):
    plan, snapshot, database = create_demo(tmp_path / "fixture", monday=True)
    output, registry = tmp_path / "attempt", tmp_path / "trials.sqlite3"
    result = batch.run(plan, snapshot, database, registry, output)
    assert result["status"] == "completed", result
    assert len(result["jobs"]) == result["attempt_count"] == 6
    assert result["strategy_jobs"] == 2 and result["benchmark_jobs"] == 4
    assert all(r["status"] == "completed" and r["metrics"]["scored_bars"] == 8784 for r in result["jobs"])
    assert all(r["metrics"]["round_trips"] == 52 for r in result["jobs"][:2])
    assert batch.recover(output, registry) == result
    with sqlite3.connect(registry) as db:
        assert db.execute("SELECT COUNT(*) FROM trial_attempts").fetchone()[0] == 6


@pytest.mark.skipif(not os.environ.get("TIDELAB_LEAN_ROOT"), reason="requires pinned LEAN; exercised in CI")
@pytest.mark.parametrize("case", ["gap", "leap", "spring", "fall", "terminal", "stress", "full_year"])
def test_actual_native_lean_monday(tmp_path, case):
    start = {"leap": "2024-02-25T23:00:00Z", "spring": "2024-03-10T23:00:00Z",
             "fall": "2024-11-03T23:00:00Z", "full_year": "2024-01-01T00:00:00Z"}.get(case, "2023-12-31T23:00:00Z")
    data = fixture(start, 8784 if case == "full_year" else 25 if case == "terminal" else 26)
    for name, value in (("package", monday.package(record())), ("record", record()), ("fixture", data)):
        batch.write(tmp_path / f"{name}.json", value)
    result = run_parity(tmp_path / "package.json", tmp_path / "record.json", tmp_path / "fixture.json",
        Path(os.environ["TIDELAB_LEAN_ROOT"]), os.environ.get("TIDELAB_DOTNET", "dotnet"), tmp_path / "attempt",
        cost=rsi.COSTS["stress" if case == "stress" else "baseline"], score_start=0)
    assert result["status"] == "matched", result
