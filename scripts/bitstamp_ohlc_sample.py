"""Fetch a bounded Bitstamp BTC/USD hourly research sample into ignored local data/.

This is a TL-001B technical and data-quality probe, not a trading adapter.
The resulting market data and manifest must not be committed or published.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import urlopen

URL = "https://www.bitstamp.net/api/v2/ohlc/btcusd/"
HOUR = timedelta(hours=1)
PAGE_SIZE = 1000


def parse_hour(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() != timedelta(0) or result.minute or result.second or result.microsecond:
        raise ValueError("start and end must be UTC whole-hour timestamps")
    return result


def fetch_page(start: datetime, limit: int) -> list[dict[str, str]]:
    query = urlencode({"step": 3600, "limit": limit, "start": int(start.timestamp()), "exclude_current_candle": "true"})
    with urlopen(f"{URL}?{query}", timeout=30) as response:
        payload = json.load(response)
    if payload.get("data", {}).get("pair") != "BTC/USD":
        raise ValueError("unexpected Bitstamp pair")
    return payload["data"]["ohlc"]


def collect(start: datetime, end: datetime) -> tuple[list[dict[str, str]], list[str]]:
    if not start < end <= datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0):
        raise ValueError("require a positive, fully closed UTC interval")
    rows: list[dict[str, str]] = []
    cursor = start
    while cursor < end:
        page = fetch_page(cursor, min(PAGE_SIZE, int((end - cursor) / HOUR)))
        if not page:
            raise ValueError(f"empty response at {cursor.isoformat()}")
        for row in page:
            stamp = datetime.fromtimestamp(int(row["timestamp"]), timezone.utc)
            if stamp != cursor:
                raise ValueError(f"missing, duplicate, or out-of-window hour: expected {cursor}, got {stamp}")
            from decimal import Decimal

            opening, high, low, closing, volume = (
                Decimal(row[key]) for key in ("open", "high", "low", "close", "volume")
            )
            if not all(value.is_finite() for value in (opening, high, low, closing, volume)):
                raise ValueError(f"non-finite value at {stamp}")
            if low <= 0 or volume < 0 or not low <= opening <= high or not low <= closing <= high:
                raise ValueError(f"invalid OHLCV at {stamp}")
            rows.append(row)
            cursor += HOUR
            if cursor >= end:
                break
        if len(page) < PAGE_SIZE and cursor < end:
            raise ValueError(f"short response before end at {cursor}")
        time.sleep(0.1)
    return rows, []


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="UTC closed-hour start, inclusive")
    parser.add_argument("--end", required=True, help="UTC closed-hour end, exclusive")
    parser.add_argument("--output", type=Path, required=True, help="CSV under ignored data/")
    args = parser.parse_args()
    start, end = parse_hour(args.start), parse_hour(args.end)
    output = args.output.resolve()
    data_root = (Path(__file__).resolve().parents[1] / "data").resolve()
    if data_root not in output.parents or output.suffix.lower() != ".csv":
        raise ValueError("output must be a .csv inside repository data/")
    if output.exists():
        raise FileExistsError(output)
    rows, gaps = collect(start, end)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(("timestamp_utc", "open", "high", "low", "close", "volume"))
        for row in rows:
            writer.writerow((
                datetime.fromtimestamp(int(row["timestamp"]), timezone.utc).isoformat().replace("+00:00", "Z"),
                row["open"], row["high"], row["low"], row["close"], row["volume"],
            ))
    manifest = {
        "source": URL,
        "market": "BTC/USD",
        "interval_seconds": 3600,
        "start_inclusive_utc": start.isoformat().replace("+00:00", "Z"),
        "end_exclusive_utc": end.isoformat().replace("+00:00", "Z"),
        "rows": len(rows),
        "expected_rows": int((end - start) / HOUR),
        "gaps": gaps,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "acquired_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "use_scope": "local noncommercial research only; no raw or derived publication",
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), **manifest}, indent=2))


if __name__ == "__main__":
    main()
