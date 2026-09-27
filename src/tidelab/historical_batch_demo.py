"""TideLab-authored invented history and plans; never imports market data."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from tidelab.domain import canonical_json, isoformat_utc
from tidelab.historical_batch import AUTHORITY, METRICS, ROOT, digest, write, write_raw
from tidelab.historical_input import FIELDS, HOUR, SOURCE, row_digest
from tidelab.storage import TideStore
from tidelab.strategy_batch import SYNTHETIC_COST


def create_demo(directory: Path, *, scale: bool = False, channel: bool = False, monday: bool = False) -> tuple[Path, Path, Path]:
    if sum((scale, channel, monday)) > 1:
        raise ValueError("choose_one_demonstration")
    directory.mkdir(parents=True, exist_ok=False)
    database = directory / "synthetic.sqlite3"
    TideStore(database).initialize()
    start = datetime(2024 if monday else 2026, 1, 1, tzinfo=timezone.utc)
    bar_count = 8784 if monday else (9264 if channel else (2000 if scale else 12))
    warmup = 0 if monday else (480 if channel else 3)
    markets = ["synthetic:" + name + "-USD" for name in
               (["ALPHA"] if monday else (["ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON"] if channel else ["ALPHA", "BETA"]))]
    descriptor = {"schema_version": 1, "kind": "synthetic", "source": SOURCE, "venue": "tidelab",
                  "interval_seconds": 3600, "rights_reference": "TideLab-authored",
                  "receipt": "tidelab-synthetic-generator-v1", "partitions": {}}
    with sqlite3.connect(database) as db:
        for market_index, market in enumerate(markets):
            rows = []
            for index in range(bar_count):
                opening = Decimal(100 + (index * 7 + market_index * 11) % 31)
                close = opening + Decimal((index % 5) - 2)
                if channel:
                    # Invented long waves, distinct wick extrema and opening gaps.
                    phase = index % 1200
                    close = Decimal(200 + min(phase, 1200 - phase) + market_index * 11)
                    opening = close + Decimal(3 if index % 13 == 0 else -1)
                payload = {"open": str(opening), "close": str(close), "high": str(max(opening, close)),
                           "low": str(min(opening, close)), "volume": "1000"}
                if channel:
                    payload["high"] = str(max(opening, close) + (7 if index % 97 == 0 else 0))
                    payload["low"] = str(min(opening, close) - (5 if index % 89 == 0 else 0))
                timestamp = isoformat_utc(start + index * HOUR)
                row = dict(zip(FIELDS, [f"{market}-{index}", 1, "tidelab", market, "bar", timestamp,
                    timestamp, SOURCE, 3600, 1, canonical_json(payload),
                    canonical_json({"kind": "tidelab_synthetic", "author": "TideLab"})]))
                db.execute(f"INSERT INTO market_events ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})", tuple(row.values()))
                rows.append(row)
            descriptor["partitions"][market] = {"start": isoformat_utc(start + warmup * HOUR),
                "end": isoformat_utc(start + bar_count * HOUR), "warmup_bars": warmup, "sha256": row_digest(rows)}
    snapshot = directory / "snapshot.json"
    write(snapshot, descriptor)
    examples = ROOT / "research/examples"
    specs = [(examples / "strategy-batch-packages/synthetic-sma-3-v1.json", examples / "strategy-batch-synthetic-record-v1.json"),
             (examples / "strategy-parity-logic-v1.json", examples / "strategy-parity-logic-record-v1.json")]
    refs = []
    for index in range(1 if channel or monday else (100 if scale else 2)):
        package_path, record_path = specs[index % 2]
        package = json.loads(package_path.read_bytes())
        if channel:
            record_path = examples / "channel-breakout-synthetic-record-v1.json"
            from tidelab.channel_breakout import package as channel_package
            package = channel_package(json.loads(record_path.read_bytes()))
        if monday:
            record_path = examples / "btc-monday-synthetic-record-v1.json"
            from tidelab.btc_monday import package as monday_package
            package = monday_package(json.loads(record_path.read_bytes()))
        if scale:
            package["strategy_id"] = f"synthetic-scale-{index}"
            package["rule"]["target_fraction"] = str(Decimal(index + 1) / 100)
        package_raw = canonical_json(package).encode()
        record_raw = record_path.read_bytes()
        write_raw(directory / f"package-{index}.json", package_raw)
        write_raw(directory / f"record-{index}.json", record_raw)
        refs.append({"id": f"package-{index}", "package": f"package-{index}.json", "record": f"record-{index}.json",
                     "package_sha256": digest(package_raw), "record_sha256": digest(record_raw)})
    jobs = [{"package": ref["id"], "market": market, "cost": cost, "benchmark": None}
            for ref in refs for market in markets for cost in ("baseline", "stress")]
    jobs.extend({"package": refs[0]["id"], "market": market, "cost": cost, "benchmark": benchmark}
                for market in markets for cost in ("baseline", "stress") for benchmark in ("cash", "passive"))
    if channel or monday:
        jobs = [{"package": refs[0]["id"], "market": market, "cost": cost, "benchmark": benchmark}
                for market in markets for benchmark in (None, "cash", "passive") for cost in ("baseline", "stress")]
    # Rejections are part of the public synthetic demonstration, not hidden fixtures.
    for label, raw in (() if channel or monday else (("malformed", b'{bad'), ("unsupported", None))):
        if raw is None:
            package = json.loads(specs[0][0].read_bytes())
            package["rule"]["entry"] = {"op": "ema"}
            raw = canonical_json(package).encode()
        write_raw(directory / f"{label}.json", raw)
        refs.append({"id": label, "package": f"{label}.json", "record": "record-0.json",
                     "package_sha256": digest(raw), "record_sha256": refs[0]["record_sha256"]})
        jobs.append({"package": label, "market": markets[0], "cost": "baseline", "benchmark": None})
    if not (channel or monday):
        jobs.append(deepcopy(jobs[0]))
    end = start + bar_count * HOUR
    plan = {"schema_version": 1, "kind": "synthetic", "family": "synthetic-monday-demo" if monday else "synthetic-channel-demo" if channel else ("synthetic-batch-scale" if scale else "synthetic-batch-demo"),
            "generation": "v1", "parent_experiment": None, "phase": "development", "issue": 95, "authority": AUTHORITY,
            "markets": markets, "partitions": {
                "development": {"start": isoformat_utc(start + warmup * HOUR), "end": isoformat_utc(end)},
                "validation": {"start": isoformat_utc(end), "end": isoformat_utc(end + 10 * HOUR)},
                "untouched": {"start": isoformat_utc(end + 10 * HOUR), "end": isoformat_utc(end + 20 * HOUR)}},
            "packages": refs, "jobs": jobs, "costs": {"baseline": dict(SYNTHETIC_COST),
                "stress": {**SYNTHETIC_COST, "fee_rate": "0.005", "adverse_rate": "0.002"}},
            "budget": len(jobs), "max_bars": 10000, "benchmark_allocation": "0.25", "metrics": METRICS,
            "selection": "none", "retention": "retain_all_local", "snapshot_sha256": digest(snapshot.read_bytes())}
    path = directory / "plan.json"
    write(path, plan)
    return path, snapshot, database
