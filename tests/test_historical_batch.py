"""End-to-end synthetic acceptance, independent arithmetic and crash boundaries."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from tidelab import historical_batch as batch
from tidelab.historical_batch_demo import create_demo
from tidelab.historical_input import read_partition
from tidelab.package_lean_parity import run_parity, validate_package_domain
from tidelab.strategy_batch import Bar, replay_package, validate_cost, SYNTHETIC_COST
from tidelab.trial_registry import TrialRegistry


def change(path, mutate):
    value = json.loads(path.read_bytes())
    mutate(value)
    path.write_text(json.dumps(value), encoding="utf-8")


def setup(tmp_path):
    plan, snapshot, database = create_demo(tmp_path / "fixture")
    return plan, snapshot, database, tmp_path / "trials.sqlite3", tmp_path / "attempt"


def test_complete_batch_reserved_before_price_reads_and_market_cache(tmp_path, monkeypatch):
    args = setup(tmp_path)
    calls = []
    original = batch.read_partition
    def read_after_admission(*a, **kw):
        with sqlite3.connect(args[3]) as db:
            assert db.execute("SELECT COUNT(*) FROM trial_attempts").fetchone()[0] == 16
            assert len(json.loads(db.execute("SELECT inventory_json FROM research_batches").fetchone()[0])) == 19
        calls.append(a[2])
        return original(*a, **kw)
    monkeypatch.setattr(batch, "read_partition", read_after_admission)
    result = batch.run(*args)
    assert result["status"] == "completed"
    assert len(calls) == 2
    assert result["submitted_jobs"] == 19 and result["attempt_count"] == 16
    assert [x["status"] for x in result["jobs"][-3:]] == ["invalid", "unsupported", "duplicate"]
    assert batch.recover(args[-1], args[-2]) == result
    assert (args[-1] / "market-0.json").exists()
    registry = TrialRegistry(args[-2])
    for job in result["jobs"][:16]:
        assert registry.status(job["attempt_id"]) == "completed"
        rows = [json.loads(x) for x in (args[-1] / job["artifact_directory"] / "trace.jsonl").read_text().splitlines()]
        assert rows[0]["index"] == 3 and rows[-1]["index"] == 11
        assert len(rows) == 9
    assert result["jobs"][8]["metrics"]["net_return"] == "0"  # cash benchmark
    assert result["jobs"][9]["metrics"]["fill_count"] == 1  # passive benchmark
    rejected = batch.run(*args[:-1], tmp_path / "repeat")
    assert rejected["reason"] == "phase_already_reserved"
    with sqlite3.connect(args[-2]) as db:
        assert db.execute("SELECT COUNT(*) FROM batch_requests").fetchone()[0] == 2


@pytest.mark.parametrize("mutation,reason", [
    (lambda p: p.update(kind="third_party"), "real_data_not_enabled"),
    (lambda p: p.update(authority=""), "missing_synthetic_authority"),
    (lambda p: p.update(phase="validation"), "phase_not_enabled"),
    (lambda p: p.update(phase="untouched"), "phase_not_enabled"),
    (lambda p: p.update(budget=1), "budget_or_bar_limit"),
    (lambda p: p.update(max_bars=10001), "budget_or_bar_limit"),
    (lambda p: p["costs"]["baseline"].update(fee_rate="1"), "invalid_cost"),
    (lambda p: p["costs"]["baseline"].update(quantity_unit="0.000000001"), "outside_cost_domain"),
])
def test_preflight_never_reads_prices(tmp_path, monkeypatch, mutation, reason):
    args = setup(tmp_path)
    change(args[0], mutation)
    monkeypatch.setattr(batch, "read_partition", lambda *a, **kw: pytest.fail("price access"))
    result = batch.run(*args)
    assert result["status"] == "blocked" and result["reason"] == reason
    assert len(result["jobs"]) == 19


@pytest.mark.parametrize("damage", ["gap", "duplicate", "digest", "provenance", "nonfinite", "null", "array", "duplicate_key"])
def test_partition_failures_are_retained_and_other_market_completes(tmp_path, damage):
    args = setup(tmp_path)
    with sqlite3.connect(args[2]) as db:
        if damage == "gap":
            db.execute("DELETE FROM market_events WHERE event_id='synthetic:ALPHA-USD-0'")
        elif damage == "duplicate":
            row = list(db.execute("SELECT * FROM market_events WHERE event_id='synthetic:ALPHA-USD-0'").fetchone())
            row[0] = "duplicate"
            db.execute("INSERT INTO market_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", row)
        elif damage == "digest":
            db.execute("UPDATE market_events SET received_at_utc='2026-01-01T00:00:01Z' WHERE event_id='synthetic:ALPHA-USD-0'")
        elif damage == "provenance":
            db.execute("UPDATE market_events SET source='unknown' WHERE event_id='synthetic:ALPHA-USD-0'")
        elif damage in ("null", "array", "duplicate_key"):
            payload = {"null": "null", "array": "[]", "duplicate_key": '{"open":"1","open":"2"}'}[damage]
            db.execute("UPDATE market_events SET payload_json=? WHERE event_id='synthetic:ALPHA-USD-0'", (payload,))
        else:
            db.execute("UPDATE market_events SET payload_json=? WHERE event_id='synthetic:ALPHA-USD-0'",
                       (json.dumps(dict(open="NaN", close="1", high="1", low="1", volume="1")),))
    result = batch.run(*args)
    assert result["status"] == "failed"
    assert result["jobs"][0]["status"] == "failed"
    assert result["jobs"][2]["status"] == "completed"
    assert (args[-1] / "job-0/failure.json").exists()


def test_reader_does_not_request_future_rows(tmp_path):
    args = setup(tmp_path)
    descriptor = batch.read(args[1])
    with sqlite3.connect(args[2]) as db:
        row = list(db.execute("SELECT * FROM market_events LIMIT 1").fetchone())
        row[0], row[5], row[10] = "future", "2026-01-01T12:00:00Z", "not JSON"
        db.execute("INSERT INTO market_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", row)
    bars = read_partition(args[2], descriptor, "synthetic:ALPHA-USD")
    assert len(bars) == 12 and bars[-1].start.hour == 11


def golden():
    root = batch.ROOT / "research/examples"
    package = batch.read(root / "strategy-batch-packages/synthetic-sma-3-v1.json")
    strategy = validate_package_domain(package, batch.read(root / "strategy-batch-synthetic-record-v1.json"))
    # Warmup alone would issue a buy in the old unpartitioned path. No fill may escape it.
    prices = [(100, 100), (100, 101), (101, 102), (102, 103), (200, 90), (50, 50)]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return strategy, [Bar(start + timedelta(hours=i), Decimal(o), Decimal(c)) for i, (o, c) in enumerate(prices)]


def test_independent_gap_metrics_warmup_and_actual_unit_multiple():
    import io
    strategy, bars = golden()
    stream = io.StringIO()
    metrics = batch.Metrics(Decimal(10000), stream)
    replay_package(strategy, bars, **validate_cost(SYNTHETIC_COST), score_start=3, emit=metrics.emit)
    trace = [json.loads(x) for x in stream.getvalue().splitlines()]
    assert trace[0]["fill"] is None and trace[0]["index"] == 3
    assert Decimal(trace[1]["fill"]["quantity"]) == Decimal("12.45637155")
    assert Decimal(trace[2]["cash"]) == Decimal("8120.64027125441875")
    result = metrics.result()
    assert result["fill_count"] == 2 and result["round_trips"] == 1
    assert Decimal(result["fees"]) == Decimal("7.78990335808125")
    assert Decimal(result["net_return"]) == Decimal("-0.187935972874558125")
    assert Decimal(result["max_drawdown"]) == Decimal("0.187935972874558125")
    assert Decimal(result["exposure"]) == Decimal(1) / 3
    trace = []
    replay_package(strategy, bars, quantity_unit=Decimal("0.03"), score_start=3, emit=trace.append)
    assert Decimal(trace[1]["fill"]["quantity"]) == Decimal("12.45")
    assert Decimal(trace[1]["fill"]["quantity"]) % Decimal("0.03") == 0
    terminal = []
    replay_package(strategy, bars[:-1], score_start=3, emit=terminal.append)
    assert Decimal(terminal[-1]["units"]) > 0 and terminal[-1]["action"] == "hold"
    for i in range(3):
        bars[i] = Bar(bars[i].start, Decimal(500), Decimal(500))
    trace = []
    replay_package(strategy, bars, score_start=3, emit=trace.append)
    assert trace[0]["fill"] is None


@pytest.mark.parametrize("point", ["reserved", "started", "artifact", "last_artifact"])
def test_process_death_recovery_never_replays(tmp_path, monkeypatch, point):
    args = setup(tmp_path)
    code = '''import os, sys
from pathlib import Path
from tidelab.historical_batch import run
point = sys.argv[1]
count = 0
def checkpoint(value):
 global count
 if value == "artifact": count += 1
 if value == point or (point == "last_artifact" and count == 19): os._exit(73)
run(*[Path(x) for x in sys.argv[2:]], checkpoint=checkpoint)
'''
    env = {**os.environ, "PYTHONPATH": str(batch.ROOT / "src")}
    child = subprocess.run([sys.executable, "-c", code, point, *map(str, args)], env=env, timeout=60)
    assert child.returncode == 73
    monkeypatch.setattr(batch, "read_partition", lambda *a, **kw: pytest.fail("recovery read prices"))
    monkeypatch.setattr(batch, "replay_package", lambda *a, **kw: pytest.fail("recovery replayed"))
    if point != "last_artifact":
        with pytest.raises(ValueError, match="explicit_abort"):
            batch.recover(args[-1], args[-2])
    result = batch.recover(args[-1], args[-2], abort=point != "last_artifact")
    assert len(result["jobs"]) == 19
    assert result["reserved_executable_jobs"] == 16
    assert result["attempt_count"] == (0 if point == "reserved" else 16)
    assert result["terminal_attempt_count"] == result["attempt_count"]
    assert result["status"] == ("completed" if point == "last_artifact" else "aborted")
    assert batch.recover(args[-1], args[-2]) == result
    registry = TrialRegistry(args[-2])
    assert all(registry.status(job["attempt_id"]) in (None, "completed", "aborted") for job in result["jobs"] if job["attempt_id"])


def test_concurrent_batch_admission_retains_loser(tmp_path):
    args = setup(tmp_path)
    results = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(batch.run, *args[:-1], tmp_path / f"attempt-{i}") for i in range(2)]
        results = [f.result() for f in futures]
    assert sorted(r["status"] for r in results) == ["blocked", "completed"]
    with sqlite3.connect(args[-2]) as db:
        assert db.execute("SELECT COUNT(*) FROM batch_requests").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM research_batches").fetchone()[0] == 1


def test_tampered_artifact_fails_recovery_and_lock_blocks_active_writer(tmp_path):
    args = setup(tmp_path)
    batch.run(*args)
    with batch.exclusive(args[-1]):
        with pytest.raises(OSError):
            batch.recover(args[-1], args[-2])
    (args[-1] / "job-0/trace.jsonl").write_text("changed")
    with pytest.raises(ValueError, match="digest_mismatch"):
        batch.recover(args[-1], args[-2])


@pytest.mark.skipif(not os.environ.get("TIDELAB_LEAN_ROOT"), reason="actual pinned LEAN CI")
@pytest.mark.parametrize("package_index,cost_name", [(0,"baseline"), (1,"baseline"), (0,"stress"), (1,"stress")])
def test_partition_cost_path_matches_actual_lean(tmp_path, package_index, cost_name):
    args = setup(tmp_path)
    result = batch.run(*args)
    assert result["status"] == "completed"
    plan, descriptor = batch.read(args[0]), batch.read(args[1])
    bars = read_partition(args[2], descriptor, plan["markets"][0])
    fixture = tmp_path / "bars.json"
    batch.write(fixture, {"kind": "tidelab_synthetic", "interval_seconds": 3600,
                         "bars": [{"start_utc": bar.start.isoformat().replace("+00:00", "Z"),
                                   "open": str(bar.open), "close": str(bar.close)} for bar in bars]})
    ref = plan["packages"][package_index]
    parity = run_parity(args[0].parent / ref["package"], args[0].parent / ref["record"], fixture,
                        Path(os.environ["TIDELAB_LEAN_ROOT"]), os.environ.get("TIDELAB_DOTNET", "dotnet"),
                        tmp_path / "lean-attempt", cost=plan["costs"][cost_name], score_start=3)
    assert parity["status"] == "matched", parity
    index = package_index * 4 + (cost_name == "stress")
    actual = batch.read(tmp_path / "lean-attempt/python.json")["trace"]
    historical = [json.loads(x) for x in (args[-1] / f"job-{index}/trace.jsonl").read_text().splitlines()]
    assert actual == historical


def test_linked_retry_preserves_failed_attempts(tmp_path):
    args = setup(tmp_path)
    class Crash(BaseException):
        pass
    def stop(stage):
        if stage == "started":
            raise Crash()
    with pytest.raises(Crash):
        batch.run(*args, checkpoint=stop)
    first = batch.recover(args[-1], args[-2], abort=True)
    retry = batch.run(*args[:-1], tmp_path / "retry", retry_of=first["batch_id"])
    assert retry["status"] == "completed"
    original_inventory = TrialRegistry(args[-2]).batch(first["batch_id"])["inventory"]
    retried_inventory = TrialRegistry(args[-2]).batch(retry["batch_id"])["inventory"]
    assert [x.get("identity") for x in original_inventory] == [x.get("identity") for x in retried_inventory]
    with sqlite3.connect(args[-2]) as db:
        assert db.execute("SELECT COUNT(*) FROM trial_attempts").fetchone()[0] == 32
        assert db.execute("SELECT COUNT(*) FROM trial_outcomes WHERE outcome='aborted'").fetchone()[0] == 16
        assert db.execute("SELECT retry_of FROM research_batches WHERE batch_id=?", (retry["batch_id"],)).fetchone()[0] == first["batch_id"]


def test_decimal_domain_and_overflow_fail_closed():
    strategy, bars = golden()
    with pytest.raises(ValueError):
        validate_cost({**SYNTHETIC_COST, "initial_cash": "Infinity"})
    # Cross-runtime portfolio overflow is explicit, not rounded into a result.
    bars[4] = Bar(bars[4].start, Decimal("0.00000001"), Decimal("1e9"))
    bars[5] = Bar(bars[5].start, Decimal("1e9"), Decimal("1e20"))
    with pytest.raises(ArithmeticError, match="overflow"):
        replay_package(strategy, bars, initial_cash=Decimal("1e9"), score_start=3)


def test_wal_bootstrap_busy_retry_is_bounded(tmp_path, monkeypatch):
    import contextlib
    registry = TrialRegistry(tmp_path / "registry.sqlite3")
    connection = registry._connect()
    calls = []
    class Contended:
        def execute(self, sql, *args):
            if sql == "PRAGMA journal_mode = WAL":
                calls.append(sql)
                if len(calls) <= 2:
                    error = sqlite3.OperationalError("database is locked")
                    error.sqlite_errorcode = sqlite3.SQLITE_BUSY
                    raise error
            return connection.execute(sql, *args)
        def close(self):
            connection.close()
    monkeypatch.setattr(registry, "_connect", lambda: Contended())
    registry.initialize()
    assert len(calls) == 3


def test_retry_rejects_changed_execution_identity(tmp_path, monkeypatch):
    args = setup(tmp_path)
    class Crash(BaseException): pass
    def stop(stage):
        if stage == "reserved": raise Crash()
    with pytest.raises(Crash): batch.run(*args, checkpoint=stop)
    old = batch.recover(args[-1], args[-2], abort=True)
    monkeypatch.setattr(batch.platform, "python_version", lambda: "different-runtime")
    result = batch.run(*args[:-1], tmp_path / "changed-retry", retry_of=old["batch_id"])
    assert result["status"] == "blocked" and result["reason"] == "retry_identity_changed"
