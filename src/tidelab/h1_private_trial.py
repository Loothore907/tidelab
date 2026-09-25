"""Prepare ignored, exact-source OKX H1 development or validation inputs."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3

from tidelab.domain import canonical_json, decimal_text, isoformat_utc, parse_utc
from tidelab.experiment_identity import build_experiment_identity, export_experiment_identity


SOURCE = "okx.historical_archive.candlesticks.1m"
INSTRUMENT = "okx:BTC-USDT"
TERMS_URL = "https://www.okx.com/en-us/help/historicaldata-terms-and-conditions"
US_TERMS_URL = "https://www.okx.com/en-us/help/terms-of-service-us"
COVERAGE_START = datetime(2023, 6, 30, 16, tzinfo=timezone.utc)
COVERAGE_END = datetime(2026, 9, 23, 16, tzinfo=timezone.utc)
SCORE_START = datetime(2023, 7, 7, 16, tzinfo=timezone.utc)
SCORE_END = datetime(2025, 1, 1, tzinfo=timezone.utc)
VALIDATION_START = SCORE_END
VALIDATION_END = datetime(2026, 1, 1, tzinfo=timezone.utc)
ENGINE_REVISION = "88bce0fc6fe282378ee73c54cef1090d0d7a73ee"
EXPECTED_ARCHIVES = 61
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _framed(hasher, value: str | bytes) -> None:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    hasher.update(len(payload).to_bytes(8, "big"))
    hasher.update(payload)


def cost_digest(root: Path) -> str:
    hasher = sha256()
    for name in ("TideLabH1V1ResearchReplay.cs",
                 "TideLabH1ConservativeExecution.cs",
                 "TideLabH1V1TrialAccounting.cs"):
        payload = (root / "scripts" / "lean_fallback" / name).read_bytes()
        hasher.update(name.encode("utf-8") + b"\0")
        hasher.update(len(payload).to_bytes(8, "big"))
        hasher.update(payload)
    return hasher.hexdigest()


def read_source(database: Path, archive_dir: Path, *,
                score_start: datetime | None = None,
                score_end: datetime | None = None) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Recheck the entire selected store and every source ZIP before slicing it."""
    score_start = SCORE_START if score_start is None else score_start
    score_end = SCORE_END if score_end is None else score_end
    if not (COVERAGE_START + timedelta(hours=168) <= score_start < score_end <= COVERAGE_END):
        raise ValueError("H1 partition exceeds selected source coverage")
    if not database.is_file() or not archive_dir.is_dir():
        raise ValueError("selected local OKX store or archive directory is missing")
    uri = database.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT event_id, event_time_utc, event_type, interval_seconds,
                      closed, payload_json, native_json
               FROM market_events WHERE venue='okx' AND instrument_id=?
                 AND source=? ORDER BY event_time_utc""", (INSTRUMENT, SOURCE)
        ).fetchall()
    expected = int((COVERAGE_END - COVERAGE_START) / timedelta(hours=1))
    if len(rows) != expected:
        raise ValueError(f"OKX hourly source coverage differs: {len(rows)}/{expected}")
    hasher = sha256()
    periods: dict[str, str] = {}
    bars: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        when = parse_utc(row["event_time_utc"])
        if when != COVERAGE_START + timedelta(hours=index) or (
            row["event_type"], row["interval_seconds"], row["closed"]
        ) != ("bar", 3600, 1):
            raise ValueError("OKX source has a gap, duplicate, or nonclosed hourly event")
        payload = json.loads(row["payload_json"])
        native = json.loads(row["native_json"])
        if set(payload) != {"open", "high", "low", "close", "volume"}:
            raise ValueError("OKX bar payload differs from the selected OHLCV schema")
        prices = {key: Decimal(decimal_text(payload[key], key))
                  for key in ("open", "high", "low", "close")}
        volume = Decimal(decimal_text(payload["volume"], "volume"))
        if min(prices.values()) <= 0 or volume < 0 or (
            prices["high"] < max(prices["open"], prices["close"]) or
            prices["low"] > min(prices["open"], prices["close"])
        ):
            raise ValueError("OKX stored OHLCV values violate importer invariants")
        archive_day = (when + timedelta(hours=8)).date()
        expected_month = archive_day.strftime("%Y-%m")
        expected_day = archive_day.isoformat()
        period = native.get("archive_month", native.get("archive_period"))
        if period not in (expected_month, expected_day) or (
            period == expected_month and "archive_period" in native
        ) or (period == expected_day and "archive_month" in native):
            raise ValueError("OKX archive period does not match the UTC hour")
        digest = native.get("archive_sha256")
        if native.get("minute_rows") != 60 or not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
            raise ValueError("OKX archive provenance is incomplete")
        previous = periods.setdefault(period, digest)
        if previous != digest:
            raise ValueError("OKX archive period has conflicting stored hashes")
        for field in (row["event_id"], row["event_time_utc"],
                      row["payload_json"], row["native_json"]):
            _framed(hasher, field)
        if score_start - timedelta(hours=168) <= when <= score_end:
            bars.append({"start_utc": isoformat_utc(when),
                         "open": decimal_text(payload["open"], "open"),
                         "close": decimal_text(payload["close"], "close"),
                         "closed": True})
    if len(periods) != EXPECTED_ARCHIVES or len(bars) != 168 + int((score_end - score_start) / timedelta(hours=1)) + 1:
        raise ValueError("OKX archive set or scored partition differs")
    archives = []
    for period, expected_digest in sorted(periods.items()):
        path = archive_dir / f"BTC-USDT-candlesticks-{period}.zip"
        if not path.is_file():
            raise ValueError(f"selected OKX archive is missing: {period}")
        file_hasher = sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                file_hasher.update(block)
        if file_hasher.hexdigest() != expected_digest:
            raise ValueError(f"selected OKX archive hash differs: {period}")
        archives.append({"period": period, "sha256": expected_digest})
    return bars, {"source_id": SOURCE, "instrument_id": INSTRUMENT,
                  "coverage_start_utc": isoformat_utc(COVERAGE_START),
                  "coverage_end_utc": isoformat_utc(COVERAGE_END),
                  "coverage_bars": expected, "hourly_store_sha256": hasher.hexdigest(),
                  "archives": archives}


def prepare_development(root: Path, database: Path, archive_dir: Path,
                        destination: Path, code_revision: str,
                        terms_reviewed: date) -> dict[str, str]:
    return prepare_partition(root, database, archive_dir, destination,
                             code_revision, terms_reviewed, "development")


def prepare_validation(root: Path, database: Path, archive_dir: Path,
                       destination: Path, code_revision: str,
                       terms_reviewed: date) -> dict[str, str]:
    return prepare_partition(root, database, archive_dir, destination,
                             code_revision, terms_reviewed, "validation")


def prepare_partition(root: Path, database: Path, archive_dir: Path,
                      destination: Path, code_revision: str,
                      terms_reviewed: date, phase: str) -> dict[str, str]:
    partitions = {"development": (SCORE_START, SCORE_END),
                  "validation": (VALIDATION_START, VALIDATION_END)}
    if phase not in partitions:
        raise ValueError("only development and validation are available")
    score_start, score_end = partitions[phase]
    if terms_reviewed != datetime.now(timezone.utc).date():
        raise ValueError("review the current official OKX terms on the run date")
    if destination.exists():
        raise FileExistsError("private trial destination already exists")
    bars, provenance = read_source(database, archive_dir,
                                   score_start=score_start, score_end=score_end)
    input_bytes = (canonical_json({"schema_version": 1,
        "phase": phase, "score_start_utc": isoformat_utc(score_start),
        "score_end_utc": isoformat_utc(score_end), "bars": bars}) + "\n").encode("utf-8")
    manifest = {"schema_version": 1, "phase": phase,
        "input_sha256": sha256(input_bytes).hexdigest(),
        "terms_url": TERMS_URL, "us_terms_url": US_TERMS_URL,
        "us_terms_last_updated": "2026-09-16",
        "terms_reviewed_utc_date": terms_reviewed.isoformat(),
        "rights_scope": "personal-private-strategy-development",
        **provenance}
    manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
    identity = build_experiment_identity(
        engine={"name": "lean", "version": "pinned-source",
                "source_revision": ENGINE_REVISION},
        code={"repository": "Loothore907:tidelab", "revision": code_revision},
        configuration={"id": "h1-v1-frozen-preregistration",
                       "sha256": sha256((root / "docs/experiments/H1-V1-PREREGISTRATION.md").read_bytes()).hexdigest()},
        data={"source_id": SOURCE, "revision": "btc-usdt-through-2026-09-23",
              "sha256": sha256(manifest_bytes).hexdigest(), "kind": "third_party",
              "rights_reference": f"okx-historical-terms-personal-{terms_reviewed.isoformat()}"},
        cost={"model_id": "h1-v1-research-cost", "revision": "v1",
              "sha256": cost_digest(root)},
        trial={"strategy_id": "h1", "strategy_version": "v1",
               "trial_id": f"h1-v1-okx-btc-usdt-{phase}", "sequence": 1,
               "origin": "human", "parent_trial_id": None},
    )
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "input.json").write_bytes(input_bytes)
    (destination / "source-manifest.json").write_bytes(manifest_bytes)
    export_experiment_identity(identity, destination / "identity.json")
    return {"identity_sha256": str(identity["identity_sha256"]),
            "data_sha256": sha256(manifest_bytes).hexdigest(),
            "coverage_bars": str(provenance["coverage_bars"]),
            "partition_bars": str(len(bars))}
