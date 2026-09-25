"""Read-only, coverage-only audit for a preregistered market universe.

No prices or strategy results are read. Coverage eligibility is not a data-rights
decision, a candidate ranking, or evidence of executable liquidity.
"""

from __future__ import annotations

import calendar
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

from tidelab.domain import isoformat_utc, parse_utc


_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_PLAN_FIELDS = {"schema_version", "plan_id", "venue", "source", "start", "end",
                "minimum_contiguous_months", "instruments"}
_HOUR = timedelta(hours=1)


def _hour(value: str) -> datetime:
    moment = parse_utc(value)
    if moment.tzinfo != timezone.utc or moment.minute or moment.second or moment.microsecond:
        raise ValueError("plan bounds must be exact UTC hours")
    return moment


def _months_after(value: datetime, months: int) -> datetime:
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    month += 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _gaps(hours: set[datetime], start: datetime, end: datetime) -> list[dict[str, str | int]]:
    gaps: list[dict[str, str | int]] = []
    cursor = start
    while cursor < end:
        if cursor in hours:
            cursor += _HOUR
            continue
        first = cursor
        while cursor < end and cursor not in hours:
            cursor += _HOUR
        gaps.append({"start": isoformat_utc(first), "end": isoformat_utc(cursor),
                     "hours": int((cursor - first) / _HOUR)})
    return gaps


def _longest(hours: set[datetime]) -> tuple[datetime | None, datetime | None, int]:
    best_start = best_end = run_start = previous = None
    best_count = run_count = 0
    for moment in sorted(hours):
        if previous is None or moment != previous + _HOUR:
            run_start, run_count = moment, 1
        else:
            run_count += 1
        previous = moment
        if run_count > best_count:
            best_start, best_end, best_count = run_start, moment + _HOUR, run_count
    return best_start, best_end, best_count


def _valid_native(raw: str) -> bool:
    try:
        native = json.loads(raw)
    except (TypeError, ValueError):
        return False
    return (isinstance(native, dict)
            and isinstance(native.get("archive_sha256"), str)
            and _DIGEST.fullmatch(native["archive_sha256"]) is not None
            and native.get("minute_rows") == 60
            and isinstance(native.get("archive_period"), str)
            and bool(native["archive_period"]))


def audit_universe_coverage(database: str | Path, plan_path: str | Path) -> dict[str, Any]:
    """Audit existing exact-source bars without creating or changing the database."""
    plan_bytes = Path(plan_path).read_bytes()
    plan = json.loads(plan_bytes)
    if not isinstance(plan, dict) or set(plan) != _PLAN_FIELDS or plan["schema_version"] != 1:
        raise ValueError("unsupported or incomplete universe plan")
    for name in ("plan_id", "venue", "source"):
        if not isinstance(plan[name], str) or not plan[name]:
            raise ValueError(f"invalid {name}")
    instruments = plan["instruments"]
    if (not isinstance(instruments, list) or not instruments
            or any(not isinstance(item, str) or not item.startswith(plan["venue"] + ":") for item in instruments)
            or len(set(instruments)) != len(instruments)):
        raise ValueError("plan instruments must be distinct exact venue instruments")
    months = plan["minimum_contiguous_months"]
    if type(months) is not int or months < 1:
        raise ValueError("minimum_contiguous_months must be positive")
    start, end = _hour(plan["start"]), _hour(plan["end"])
    if end <= start or _months_after(start, months) > end:
        raise ValueError("plan window cannot contain the minimum continuity period")
    path = Path(database)
    if not path.is_file():
        raise FileNotFoundError(f"existing local database required: {path}")

    markets = []
    eligible_hour_sets: list[set[datetime]] = []
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        for instrument in instruments:
            rows = connection.execute(
                """SELECT event_time_utc, source, closed, native_json FROM market_events
                   WHERE venue=? AND instrument_id=? AND event_type='bar'
                     AND interval_seconds=3600 AND event_time_utc>=? AND event_time_utc<?
                   ORDER BY event_time_utc, event_id""",
                (plan["venue"], instrument, isoformat_utc(start), isoformat_utc(end)),
            )
            hours: set[datetime] = set()
            invalid_rows = other_source_rows = 0
            for row in rows:
                if row["source"] != plan["source"]:
                    other_source_rows += 1
                    continue
                try:
                    moment = _hour(row["event_time_utc"])
                except (TypeError, ValueError):
                    invalid_rows += 1
                    continue
                if (moment < start or moment >= end or moment in hours
                        or row["closed"] != 1 or not _valid_native(row["native_json"])):
                    invalid_rows += 1
                    continue
                hours.add(moment)
            gaps = _gaps(hours, start, end)
            run_start, run_end, run_hours = _longest(hours)
            if invalid_rows:
                status = "excluded_invalid_source_rows"
            elif not hours:
                status = "excluded_no_exact_source_bars"
            elif run_start is None or run_end is None or _months_after(run_start, months) > run_end:
                status = "excluded_short_continuity"
            else:
                status = "coverage_eligible"
                eligible_hour_sets.append(hours)
            markets.append({
                "instrument": instrument,
                "status": status,
                "exact_source_hours": len(hours),
                "missing_hours": sum(gap["hours"] for gap in gaps),
                "gaps": gaps,
                "longest_run": None if run_start is None else {
                    "start": isoformat_utc(run_start), "end": isoformat_utc(run_end), "hours": run_hours,
                },
                "invalid_source_rows": invalid_rows,
                "other_source_rows_ignored": other_source_rows,
            })
    common_start = common_end = None
    common_hours = 0
    if len(eligible_hour_sets) >= 2:
        common_start, common_end, common_hours = _longest(set.intersection(*eligible_hour_sets))
    comparable = (common_start is not None and common_end is not None
                  and _months_after(common_start, months) <= common_end)
    return {
        "schema_version": 1,
        "plan_id": plan["plan_id"],
        "plan_sha256": sha256(plan_bytes).hexdigest(),
        "purpose": "private_coverage_only",
        "window": {"start": isoformat_utc(start), "end": isoformat_utc(end)},
        "minimum_contiguous_months": months,
        "comparable_coverage": comparable,
        "common_contiguous_window": None if common_start is None else {
            "start": isoformat_utc(common_start), "end": isoformat_utc(common_end),
            "hours": common_hours,
        },
        "markets": markets,
    }
