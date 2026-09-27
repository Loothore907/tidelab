"""New admission and old consumed grant, using invented archives only."""
from copy import deepcopy
import sqlite3
import pytest
from tidelab import monday_private as monday, rsi_private as rsi
from tidelab import historical_batch as batch
from test_rsi_private import invented_archive
from test_btc_monday import record


def setup_program(tmp_path, monkeypatch, *, archive=False):
    # Original RSI initialization on a test-only store establishes its anchor.
    monkeypatch.setattr(rsi, "ROOT", tmp_path)
    monkeypatch.setattr(rsi, "gate", lambda _: "a" * 40)
    monkeypatch.setattr(rsi, "authority", record)
    monkeypatch.setattr(monday, "ROOT", tmp_path)
    monkeypatch.setattr(monday, "_base_gate", lambda _: "a" * 40)
    monkeypatch.setattr(monday, "authority", record)
    if archive:
        monkeypatch.setattr(rsi, "FIRST", monday.FIRST)
        monkeypatch.setattr(rsi, "ROWS", monday.ROWS)
        monkeypatch.setattr(rsi, "MARKETS", monday.MARKETS)
        invented_archive(tmp_path, monkeypatch)
    else:
        (tmp_path / "data/strategy_intake").mkdir(parents=True)
    rsi.initialize("test")
    reg = rsi.canonical_registry()
    reg.reserve_access(rsi.GRANT, "snapshot", {"test": "old consumed snapshot"})
    reg.reserve_access(rsi.GRANT, "batch", {"test": "old consumed batch"})
    return reg


def test_new_grant_appends_same_store_full_once_only(tmp_path, monkeypatch):
    reg = setup_program(tmp_path, monkeypatch, archive=True)
    anchor = rsi.anchor_path().read_bytes()
    assert monday.authorize("test")["prices_read"] is False
    original = monday.rows_for
    def observed(db, market):
        assert reg.access(monday.GRANT, "snapshot")
        return original(db, market)
    monkeypatch.setattr(monday, "rows_for", observed)
    assert monday.prepare("test") == {"status": "prepared", "markets": 1}
    descriptor = batch.read(monday.study() / "snapshot.json")
    assert all(p["warmup_bars"] == 0 for p in descriptor["partitions"].values())
    assert monday.execute("test") == {"status": "reviewed", "jobs": 6, "results_private": True}
    summary = batch.read(monday.study() / "attempt/summary.json")
    assert all(x["status"] == "completed" for x in summary["jobs"])
    assert [x["metrics"]["round_trips"] for x in summary["jobs"][:2]] == [52, 52]
    assert [x["metrics"]["terminal_units"] for x in summary["jobs"][:2]] == ["0", "0"]
    assert len(batch.read(monday.study() / "diagnostics.json")["jobs"]) == 6
    assert batch.read(monday.study() / "review.json")["automatic_promotion"] is False
    assert batch.recover(monday.study() / "attempt", monday.registry_path()) == summary
    for action in (monday.authorize, monday.prepare, monday.execute):
        with pytest.raises(sqlite3.IntegrityError): action("test")
    assert rsi.anchor_path().read_bytes() == anchor
    assert reg.access(rsi.GRANT, "snapshot") == {"test": "old consumed snapshot"}
    assert reg.access(rsi.GRANT, "batch") == {"test": "old consumed batch"}
    with pytest.raises(sqlite3.IntegrityError): rsi.prepare("test")


@pytest.mark.parametrize("damage", ["unapproved", "head", "store", "authority"])
def test_stop_before_snapshot_prices(tmp_path, monkeypatch, damage):
    setup_program(tmp_path, monkeypatch)
    if damage != "unapproved": monday.authorize("test")
    if damage == "head": monkeypatch.setattr(monday, "_base_gate", lambda _: "b" * 40)
    if damage == "store": monday.registry_path().rename(monday.registry_path().with_suffix(".saved"))
    if damage == "authority": monkeypatch.setattr(monday, "AUTHORITY_HASH", "0" * 64)
    with pytest.raises(ValueError): monday.prepare("test")
    assert not monday.study().exists()
    if damage == "store": assert not monday.registry_path().exists()


def test_failed_snapshot_consumes_new_grant(tmp_path, monkeypatch):
    reg = setup_program(tmp_path, monkeypatch)
    monday.authorize("test")
    with pytest.raises(sqlite3.OperationalError): monday.prepare("test")
    assert reg.access(monday.GRANT, "snapshot")
    assert (monday.study() / "preparation-failed.json").exists()
    with pytest.raises(sqlite3.IntegrityError): monday.prepare("test")
    with pytest.raises(ValueError, match="not_prepared"): monday.execute("test")


def test_plan_rejects_parameter_market_cost_and_window_drift():
    rec = record(); descriptor = {"test": "invented"}
    policy = monday.ApprovedMondayPolicy(rec, descriptor)
    plan = monday.make_plan(descriptor, rec)
    for field in ("markets", "costs", "partitions", "jobs", "budget"):
        altered = deepcopy(plan); altered[field] = None
        with pytest.raises(ValueError, match="outside_approved"): policy.preflight(altered, descriptor)
    candidate = monday.package(rec); candidate["rule"]["target_fraction"] = "0.5"
    with pytest.raises(ValueError, match="outside_selected"): policy.package(candidate, rec)


@pytest.mark.parametrize("damage", ["plan", "descriptor", "snapshot", "prepared_head"])
def test_prepared_identity_and_snapshot_fail_closed(tmp_path, monkeypatch, damage):
    # No prices needed: construct receipt identity and corrupt before execution.
    reg = setup_program(tmp_path, monkeypatch)
    monday.authorize("test"); monday.study().mkdir()
    batch.write(monday.study() / "prepared.json", {"head": "b" * 40 if damage == "prepared_head" else "a" * 40,
                                                    "snapshot_file_sha256": batch.digest(b"original")})
    batch.write(monday.study() / "snapshot.json", {})
    batch.write(monday.study() / "plan.json", {})
    reg.reserve_access(monday.GRANT, "snapshot_complete", {
        "receipt_sha256": batch.digest((monday.study() / "prepared.json").read_bytes()),
        "descriptor_sha256": batch.digest((monday.study() / "snapshot.json").read_bytes()),
        "plan_sha256": batch.digest((monday.study() / "plan.json").read_bytes())})
    if damage in ("plan", "descriptor"):
        (monday.study() / ("plan.json" if damage == "plan" else "snapshot.json")).write_text('{"changed":true}\n')
    if damage == "snapshot": (monday.study() / "snapshot.sqlite3").write_bytes(b"changed")
    with pytest.raises(ValueError): monday.execute("test")
    assert not (monday.study() / "attempt").exists()
    if damage == "snapshot":
        assert reg.access(monday.GRANT, "batch")
        with pytest.raises(sqlite3.IntegrityError): monday.execute("test")


def test_authority_hash_checked_before_intake_db(tmp_path, monkeypatch):
    monkeypatch.setattr(monday, "ROOT", tmp_path)
    folder = tmp_path / "data/strategy_intake"; folder.mkdir(parents=True)
    (folder / "BTC-MONDAY-V1-PROPOSAL.md").write_text("changed")
    with pytest.raises(ValueError, match="authority_identity"): monday.authority()
    assert not (folder / "intake.sqlite3").exists()


def test_terms_date_gate(monkeypatch):
    monkeypatch.setattr(rsi, "integrated_head", lambda: "a" * 40)
    monkeypatch.setattr(monday, "authority", record)
    with pytest.raises(ValueError, match="current_day_terms"):
        monday._base_gate("2000-01-01")


def test_cli_hard_timeout_retains_failure_without_retry(tmp_path, monkeypatch):
    import runpy
    import subprocess
    import sys
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts/monday_private_batch.py"
    module = runpy.run_path(str(script))
    monkeypatch.setattr(monday, "ROOT", tmp_path)
    monday.study().mkdir(parents=True)
    monkeypatch.setattr(sys, "argv", [str(script), "run", "--terms-reviewed-utc-date", "test"])
    calls = []
    def timeout(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 1800 and kwargs["check"] is True
        raise subprocess.TimeoutExpired(command, 1800)
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(SystemExit, match="no retry"):
        module["main"]()
    assert len(calls) == 1
    assert batch.read(monday.study() / "execution-timeout.json")["no_retry"] is True


def review_fixture():
    return {"jobs": [{"index": i, "status": "completed", "metrics": {
        "net_return": "0.02" if i < 2 else "0.01", "max_drawdown": "0.15",
        "round_trips": 52 if i < 2 else 0, "terminal_units": "0" if i < 4 else "1",
        "scored_bars": 8784}} for i in range(6)]}


@pytest.mark.parametrize("damage", ["missing", "failed", "51", "53", "terminal", "bars", "nan", "bool"])
def test_calendar_conformance_precedes_eligibility(damage):
    summary = review_fixture()
    assert monday.review(summary)["markets"][0]["status"] == "eligible_for_deeper_review"
    if damage == "missing": summary["jobs"].pop()
    elif damage == "failed": summary["jobs"][5]["status"] = "failed"
    elif damage in ("51", "53"): summary["jobs"][1]["metrics"]["round_trips"] = int(damage)
    elif damage == "terminal": summary["jobs"][1]["metrics"]["terminal_units"] = "1"
    elif damage == "bars": summary["jobs"][4]["metrics"]["scored_bars"] = 8783
    elif damage == "nan": summary["jobs"][0]["metrics"]["terminal_units"] = "NaN"
    else: summary["jobs"][0]["metrics"]["round_trips"] = True
    result = monday.review(summary)
    assert result["status"] == result["markets"][0]["status"] == "incomplete"
    assert result["eligibility_provisional"] and not result["automatic_promotion"]


@pytest.mark.parametrize("field,value", [("net_return", "0"), ("max_drawdown", "0.150001")])
def test_weak_result_closes_without_nomination(field, value):
    summary = review_fixture(); summary["jobs"][0]["metrics"][field] = value
    assert monday.review(summary)["markets"][0]["status"] == "not_nominated"


def test_one_market_exact_window_and_frozen_job_counts(monkeypatch):
    from tidelab import channel_private
    assert rsi.make_plan({}, record())["budget"] == channel_private.make_plan({}, record())["budget"] == 30
    assert monday.make_plan({}, record())["budget"] == 6
    class Query:
        def execute(self, sql, params):
            assert params == ("okx:BTC-USDT", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z")
            assert "event_time_utc>=? AND event_time_utc<?" in sql
            return self
        def fetchmany(self, n):
            assert n == 8785
            return []
    assert monday.rows_for(Query(), "okx:BTC-USDT") == []
    with pytest.raises(ValueError, match="outside_approved_market"):
        monday.rows_for(None, "okx:ETH-USDT")
    monkeypatch.setattr(monday, "MARKETS", ["okx:BTC-USDT", "okx:ETH-USDT"])
    with pytest.raises(ValueError, match="frozen_inventory"):
        monday.make_plan({}, record())
