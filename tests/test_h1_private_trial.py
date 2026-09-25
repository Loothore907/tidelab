"""The private H1 input must bind exact hours, archives, and identity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import pytest

from tidelab import h1_private_trial as trial


def synthetic_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    monkeypatch.setattr(trial, "COVERAGE_START", start)
    monkeypatch.setattr(trial, "COVERAGE_END", start + timedelta(hours=171))
    monkeypatch.setattr(trial, "SCORE_START", start + timedelta(hours=168))
    monkeypatch.setattr(trial, "SCORE_END", start + timedelta(hours=170))
    monkeypatch.setattr(trial, "EXPECTED_ARCHIVES", 1)
    data = tmp_path / "data"
    data.mkdir()
    archive = data / "BTC-USDT-candlesticks-2024-01.zip"
    archive.write_bytes(b"TideLab synthetic archive test")
    digest = sha256(archive.read_bytes()).hexdigest()
    database = data / "research.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("""CREATE TABLE market_events (
            event_id TEXT, venue TEXT, instrument_id TEXT, source TEXT,
            event_time_utc TEXT, event_type TEXT, interval_seconds INTEGER,
            closed INTEGER, payload_json TEXT, native_json TEXT)""")
        for index in range(171):
            when = start + timedelta(hours=index)
            connection.execute("INSERT INTO market_events VALUES (?,?,?,?,?,?,?,?,?,?)",
                (f"synthetic-{index}", "okx", trial.INSTRUMENT, trial.SOURCE,
                 when.strftime("%Y-%m-%dT%H:%M:%SZ"), "bar", 3600, 1,
                 json.dumps({"open": "100", "high": "100", "low": "100",
                             "close": "100", "volume": "1"}),
                 json.dumps({"archive_month": "2024-01",
                             "archive_sha256": digest, "minute_rows": 60})))
    return database, data


def test_private_development_binds_source_archive_and_input(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database, archives = synthetic_store(tmp_path, monkeypatch)
    bars, provenance = trial.read_source(database, archives)
    assert len(bars) == 171
    assert provenance["coverage_bars"] == 171
    assert len(provenance["archives"]) == 1
    root = tmp_path
    (root / "docs/experiments").mkdir(parents=True)
    (root / "docs/experiments/H1-V1-PREREGISTRATION.md").write_text("synthetic", encoding="utf-8")
    costs = root / "scripts/lean_fallback"
    costs.mkdir(parents=True)
    for name in ("TideLabH1V1ResearchReplay.cs", "TideLabH1ConservativeExecution.cs",
                 "TideLabH1V1TrialAccounting.cs"):
        (costs / name).write_text("synthetic", encoding="utf-8")
    bundle = root / "data/private-development"
    result = trial.prepare_development(root, database, archives, bundle,
                                       "a" * 40, datetime.now(timezone.utc).date())
    identity = json.loads((bundle / "identity.json").read_text(encoding="utf-8"))
    manifest = (bundle / "source-manifest.json").read_bytes()
    input_bytes = (bundle / "input.json").read_bytes()
    assert identity["data"]["sha256"] == sha256(manifest).hexdigest() == result["data_sha256"]
    assert json.loads(manifest)["input_sha256"] == sha256(input_bytes).hexdigest()
    assert identity["code"]["revision"] == "a" * 40


def test_private_development_rejects_gap_and_changed_archive(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    database, archives = synthetic_store(tmp_path, monkeypatch)
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM market_events WHERE event_id='synthetic-100'")
    with pytest.raises(ValueError, match="coverage differs"):
        trial.read_source(database, archives)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE market_events SET event_id='synthetic-100' WHERE event_id='synthetic-101'")
        connection.execute("INSERT INTO market_events SELECT 'synthetic-101',venue,instrument_id,source,event_time_utc,event_type,interval_seconds,closed,payload_json,native_json FROM market_events WHERE event_id='synthetic-100'")
    with pytest.raises(ValueError, match="gap, duplicate"):
        trial.read_source(database, archives)
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE market_events SET event_time_utc='2024-01-05T04:00:00Z' WHERE event_id='synthetic-101'")
    (archives / "BTC-USDT-candlesticks-2024-01.zip").write_bytes(b"changed")
    with pytest.raises(ValueError, match="archive hash differs"):
        trial.read_source(database, archives)
