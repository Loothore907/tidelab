"""New admission and old consumed grant, using invented archives only."""
from copy import deepcopy
import sqlite3
import pytest
from tidelab import channel_private as channel, rsi_private as rsi
from tidelab import historical_batch as batch
from test_rsi_private import invented_archive, record


def setup_program(tmp_path, monkeypatch, *, archive=False):
    # Original RSI initialization on a test-only store establishes its anchor.
    monkeypatch.setattr(rsi, "ROOT", tmp_path)
    monkeypatch.setattr(rsi, "gate", lambda _: "a" * 40)
    monkeypatch.setattr(rsi, "authority", record)
    monkeypatch.setattr(channel, "ROOT", tmp_path)
    monkeypatch.setattr(channel, "_base_gate", lambda _: "a" * 40)
    monkeypatch.setattr(channel, "authority", record)
    if archive:
        monkeypatch.setattr(rsi, "FIRST", channel.FIRST)
        monkeypatch.setattr(rsi, "ROWS", channel.ROWS)
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
    assert channel.authorize("test")["prices_read"] is False
    original = channel.rows_for
    def observed(db, market):
        assert reg.access(channel.GRANT, "snapshot")
        return original(db, market)
    monkeypatch.setattr(channel, "rows_for", observed)
    assert channel.prepare("test")["status"] == "prepared"
    descriptor = batch.read(channel.study() / "snapshot.json")
    assert all(p["warmup_bars"] == 480 for p in descriptor["partitions"].values())
    assert channel.execute("test") == {"status": "reviewed", "jobs": 30, "results_private": True}
    summary = batch.read(channel.study() / "attempt/summary.json")
    assert all(x["status"] == "completed" for x in summary["jobs"])
    assert len(batch.read(channel.study() / "diagnostics.json")["jobs"]) == 30
    assert batch.read(channel.study() / "review.json")["automatic_promotion"] is False
    assert batch.recover(channel.study() / "attempt", channel.registry_path()) == summary
    for action in (channel.authorize, channel.prepare, channel.execute):
        with pytest.raises(sqlite3.IntegrityError): action("test")
    assert rsi.anchor_path().read_bytes() == anchor
    assert reg.access(rsi.GRANT, "snapshot") == {"test": "old consumed snapshot"}
    assert reg.access(rsi.GRANT, "batch") == {"test": "old consumed batch"}
    with pytest.raises(sqlite3.IntegrityError): rsi.prepare("test")


@pytest.mark.parametrize("damage", ["unapproved", "head", "store", "authority"])
def test_stop_before_snapshot_prices(tmp_path, monkeypatch, damage):
    setup_program(tmp_path, monkeypatch)
    if damage != "unapproved": channel.authorize("test")
    if damage == "head": monkeypatch.setattr(channel, "_base_gate", lambda _: "b" * 40)
    if damage == "store": channel.registry_path().rename(channel.registry_path().with_suffix(".saved"))
    if damage == "authority": monkeypatch.setattr(channel, "AUTHORITY_HASH", "0" * 64)
    with pytest.raises(ValueError): channel.prepare("test")
    assert not channel.study().exists()
    if damage == "store": assert not channel.registry_path().exists()


def test_failed_snapshot_consumes_new_grant(tmp_path, monkeypatch):
    reg = setup_program(tmp_path, monkeypatch)
    channel.authorize("test")
    with pytest.raises(sqlite3.OperationalError): channel.prepare("test")
    assert reg.access(channel.GRANT, "snapshot")
    assert (channel.study() / "preparation-failed.json").exists()
    with pytest.raises(sqlite3.IntegrityError): channel.prepare("test")
    with pytest.raises(ValueError, match="not_prepared"): channel.execute("test")


def test_plan_rejects_parameter_market_cost_and_window_drift():
    rec = record(); descriptor = {"test": "invented"}
    policy = channel.ApprovedChannelPolicy(rec, descriptor)
    plan = channel.make_plan(descriptor, rec)
    for field in ("markets", "costs", "partitions", "jobs", "budget"):
        altered = deepcopy(plan); altered[field] = None
        with pytest.raises(ValueError, match="outside_approved"): policy.preflight(altered, descriptor)
    candidate = channel.package(rec); candidate["rule"]["target_fraction"] = "0.5"
    with pytest.raises(ValueError, match="outside_selected"): policy.package(candidate, rec)


@pytest.mark.parametrize("damage", ["plan", "descriptor", "snapshot", "prepared_head"])
def test_prepared_identity_and_snapshot_fail_closed(tmp_path, monkeypatch, damage):
    # No prices needed: construct receipt identity and corrupt before execution.
    reg = setup_program(tmp_path, monkeypatch)
    channel.authorize("test"); channel.study().mkdir()
    batch.write(channel.study() / "prepared.json", {"head": "b" * 40 if damage == "prepared_head" else "a" * 40,
                                                    "snapshot_file_sha256": batch.digest(b"original")})
    batch.write(channel.study() / "snapshot.json", {})
    batch.write(channel.study() / "plan.json", {})
    reg.reserve_access(channel.GRANT, "snapshot_complete", {
        "receipt_sha256": batch.digest((channel.study() / "prepared.json").read_bytes()),
        "descriptor_sha256": batch.digest((channel.study() / "snapshot.json").read_bytes()),
        "plan_sha256": batch.digest((channel.study() / "plan.json").read_bytes())})
    if damage in ("plan", "descriptor"):
        (channel.study() / ("plan.json" if damage == "plan" else "snapshot.json")).write_text('{"changed":true}\n')
    if damage == "snapshot": (channel.study() / "snapshot.sqlite3").write_bytes(b"changed")
    with pytest.raises(ValueError): channel.execute("test")
    assert not (channel.study() / "attempt").exists()
    if damage == "snapshot":
        assert reg.access(channel.GRANT, "batch")
        with pytest.raises(sqlite3.IntegrityError): channel.execute("test")


def test_authority_hash_checked_before_intake_db(tmp_path, monkeypatch):
    monkeypatch.setattr(channel, "ROOT", tmp_path)
    folder = tmp_path / "data/strategy_intake"; folder.mkdir(parents=True)
    (folder / "CHANNEL-BREAKOUT-V1-PROPOSAL.md").write_text("changed")
    with pytest.raises(ValueError, match="authority_identity"): channel.authority()
    assert not (folder / "intake.sqlite3").exists()


def test_terms_date_gate(monkeypatch):
    monkeypatch.setattr(rsi, "integrated_head", lambda: "a" * 40)
    monkeypatch.setattr(channel, "authority", record)
    with pytest.raises(ValueError, match="current_day_terms"):
        channel._base_gate("2000-01-01")


def test_cli_hard_timeout_retains_failure_without_retry(tmp_path, monkeypatch):
    import runpy
    import subprocess
    import sys
    from pathlib import Path
    script = Path(__file__).resolve().parents[1] / "scripts/channel_private_batch.py"
    module = runpy.run_path(str(script))
    monkeypatch.setattr(channel, "ROOT", tmp_path)
    channel.study().mkdir(parents=True)
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
    assert batch.read(channel.study() / "execution-timeout.json")["no_retry"] is True
