"""One private five-spot low-volatility phase; writes no result outside ignored data/.

Run only after the fixed preregistration and code reach clean, exact-CI main.
This is an hourly full-fill research scenario, never an order path.
"""

from __future__ import annotations

import argparse
from contextlib import closing
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import subprocess

from tidelab.candidate_screen import SOURCE, _bar, preflight
from tidelab.domain import canonical_json, parse_utc
from tidelab.experiment_identity import build_experiment_identity
from tidelab.low_vol_five_spot import (BASE_COST, STRESS_COST, HOUR, MARKETS,
                                      HourlyBar, decision, measure,
                                      passive_fills, replay)
from tidelab.strategy_intake import IntakeRegistry, load_record
from tidelab.trial_registry import TrialRegistry


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "low_vol_five_spot_v1"
DATABASE = ROOT / "data" / "okx" / "research.sqlite3"
ARCHIVES = ROOT / "data" / "okx"
PLAN = ROOT / "research" / "first-pass-universe-v1.json"
PREREG = ROOT / "docs" / "experiments" / "LOW-VOL-FIVE-SPOT-V1-PREREGISTRATION.md"
TERMS = "https://www.okx.com/en-us/help/historicaldata-terms-and-conditions"
PARTITIONS = {
    "development": (datetime(2023, 9, 1, tzinfo=timezone.utc),
                    datetime(2025, 1, 1, tzinfo=timezone.utc)),
    "validation": (datetime(2025, 1, 1, tzinfo=timezone.utc),
                   datetime(2026, 1, 1, tzinfo=timezone.utc)),
    "untouched": (datetime(2026, 1, 1, tzinfo=timezone.utc),
                  datetime(2026, 8, 1, tzinfo=timezone.utc)),
}
EXPECTED_INTAKE_SHA256 = "8203e8fc6996ec04a4d6898fe301e5d93af93ed22040dc406b48da9574ed37b9"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def _command(*args: str) -> str:
    return subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8").strip()


def integrated_head() -> str:
    if (_command("git", "branch", "--show-current") != "main"
            or _command("git", "status", "--porcelain")):
        raise RuntimeError("private trial requires clean integrated main")
    head = _command("git", "rev-parse", "HEAD")
    if (head != _command("git", "rev-parse", "origin/main")
            or head != _command("git", "ls-remote", "origin", "refs/heads/main").split()[0]):
        raise RuntimeError("integrated main differs from fresh origin")
    runs = json.loads(_command("gh", "run", "list", "--repo", "Loothore907/tidelab",
                               "--commit", head,
                               "--json", "headSha,workflowName,status,conclusion", "--limit", "20"))
    if not any(run == {"headSha": head, "workflowName": "CI", "status": "completed",
                       "conclusion": "success"} for run in runs):
        raise RuntimeError("exact-head remote CI has not passed")
    return head


def _framed(hasher, value: str) -> None:
    payload = value.encode("utf-8")
    hasher.update(len(payload).to_bytes(8, "big") + payload)


def read_phase(phase: str) -> tuple[dict[str, list[HourlyBar]], str]:
    """Verify the exact source, five complete clocks and referenced source ZIPs."""
    first, terminal = PARTITIONS[phase]
    start, end = first - 60 * timedelta(days=1) - HOUR, terminal + 2 * HOUR
    expected = int((end - start) / HOUR) + 1
    uri = DATABASE.resolve().as_uri() + "?mode=ro"
    bars = {}
    hasher = sha256()
    archives: dict[tuple[str, str], str] = {}
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.row_factory = sqlite3.Row
        for market in MARKETS:
            rows = db.execute(
                """SELECT event_id, event_time_utc, source, event_type,
                          interval_seconds, closed, payload_json, native_json
                   FROM market_events WHERE venue='okx' AND instrument_id=?
                     AND event_time_utc>=? AND event_time_utc<=?
                   ORDER BY event_time_utc, event_id""",
                (market, start.isoformat().replace("+00:00", "Z"),
                 end.isoformat().replace("+00:00", "Z")),
            ).fetchall()
            if len(rows) != expected:
                raise ValueError("missing or duplicate exact-source hourly rows")
            series = []
            for index, row in enumerate(rows):
                when = parse_utc(row["event_time_utc"])
                native = json.loads(row["native_json"])
                archive_day = (when + timedelta(hours=8)).date()
                period = native.get("archive_period", native.get("archive_month"))
                digest = native.get("archive_sha256")
                if (when != start + index * HOUR or row["source"] != SOURCE
                        or (row["event_type"], row["interval_seconds"], row["closed"])
                        != ("bar", 3600, 1)
                        or native.get("minute_rows") != 60
                        or period not in (archive_day.isoformat(), archive_day.strftime("%Y-%m"))
                        or ("archive_period" in native and "archive_month" in native)
                        or not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None):
                    raise ValueError("source, closure or archive provenance changed")
                key = (market.removeprefix("okx:"), period)
                if key in archives and archives[key] != digest:
                    raise ValueError("archive period has conflicting hashes")
                archives[key] = digest
                for field in (market, row["event_id"], row["event_time_utc"],
                              row["payload_json"], row["native_json"]):
                    _framed(hasher, field)
                parsed = _bar(when, row["payload_json"])
                series.append(HourlyBar(when, parsed.open, parsed.high,
                                        parsed.low, parsed.close))
            bars[market] = series
    for (symbol, period), digest in sorted(archives.items()):
        path = ARCHIVES / f"{symbol}-candlesticks-{period}.zip"
        if not path.is_file():
            raise ValueError("source archive missing")
        file_hash = sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                file_hash.update(block)
        if file_hash.hexdigest() != digest:
            raise ValueError("source archive hash changed")
        _framed(hasher, symbol)
        _framed(hasher, period)
        _framed(hasher, digest)
    return bars, hasher.hexdigest()


def _write_new(path: Path, body: dict) -> str:
    raw = (canonical_json(body) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as output:
        output.write(raw)
    return sha256(raw).hexdigest()


def _private_serializable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, tuple):
        return [_private_serializable(item) for item in value]
    if isinstance(value, list):
        return [_private_serializable(item) for item in value]
    if isinstance(value, dict):
        return {key: _private_serializable(item) for key, item in value.items()}
    return value


def _prior_passed(phase: str, config_hash: str, head: str) -> str | None:
    if phase == "development":
        return None
    parent_phase = "development" if phase == "validation" else "validation"
    path = DATA / f"{parent_phase}-decision.json"
    prior = json.loads(path.read_text(encoding="utf-8"))
    artifact = DATA / f"{parent_phase}-result.json"
    raw = artifact.read_bytes()
    attempt = prior["attempt_id"]
    if (prior["outcome"] != "survived_for_further_observation"
            or prior["configuration_sha256"] != config_hash
            or prior["code_revision"] != head
            or prior["artifact_sha256"] != sha256(raw).hexdigest()
            or json.loads(raw)["decision"] != prior["outcome"]
            or TrialRegistry(DATA / "trials.sqlite3").status(attempt) != "completed"):
        raise RuntimeError("prior phase did not pass its frozen gate")
    return attempt


def run(phase: str, reviewed: date) -> dict[str, object]:
    if reviewed != datetime.now(timezone.utc).date():
        raise ValueError("review official OKX terms on the UTC run date")
    head = integrated_head()
    intake_path = ROOT / "data" / "strategy_intake" / "paper-pyo-jang-low-volatility-v3.json"
    intake = load_record(intake_path)
    if (IntakeRegistry(intake_path.parent / "intake.sqlite3")
            .check_implementation_record(intake) != EXPECTED_INTAKE_SHA256):
        raise RuntimeError("selected source intake record differs")
    plan_markets, plan_hash = preflight(DATABASE, PLAN)
    if tuple(plan_markets) != MARKETS:
        raise ValueError("fixed universe differs")
    config_hash = sha256(PREREG.read_bytes()).hexdigest()
    parent_attempt = _prior_passed(phase, config_hash, head)
    if (DATA / f"{phase}-decision.json").exists():
        raise RuntimeError("partition already opened")
    bars, data_hash = read_phase(phase)
    cost_hash = sha256(canonical_json({
        "base": {key: str(value) for key, value in BASE_COST.items()},
        "stress": {key: str(value) for key, value in STRESS_COST.items()},
        "sensitivity": {"fill_hour": 2, "extra_adverse": "0.001"},
    }).encode("utf-8")).hexdigest()
    identity = build_experiment_identity(
        engine={"name": "tidelab-offline-low-vol", "version": "v1",
                "source_revision": head},
        code={"repository": "Loothore907:tidelab", "revision": head},
        configuration={"id": "low-vol-five-spot-v1", "sha256": config_hash},
        data={"source_id": SOURCE, "revision": f"{plan_hash[:12]}-{phase}",
              "sha256": data_hash, "kind": "third_party",
              "rights_reference": f"okx-historical-personal-{reviewed.isoformat()}"},
        cost={"model_id": "low-vol-five-spot-cost", "revision": "v1",
              "sha256": cost_hash},
        trial={"strategy_id": "paper-pyo-jang-low-vol-five-spot",
               "strategy_version": "v1", "trial_id": f"{phase}.low-vol-five-spot",
               "sequence": 1, "origin": "human", "parent_trial_id": parent_attempt},
    )
    attempt = f"low-vol-v1-{phase}"
    registry = TrialRegistry(DATA / "trials.sqlite3")
    registry.initialize()
    if registry.status(attempt) is not None:
        raise RuntimeError("attempt already launched")
    registry.start(attempt, identity, phase, datetime.now(timezone.utc))
    try:
        first, terminal = PARTITIONS[phase]
        scenarios = {}
        measured = {}
        for label, cost in (("base", BASE_COST), ("stress", STRESS_COST)):
            policy = replay(bars, first, terminal, cost)
            policy_metrics = measure(bars, policy.fills, first, terminal)
            if (policy_metrics.cash, policy_metrics.terminal_equity,
                    policy_metrics.fees, policy_metrics.turnover) != (
                    policy.cash, policy.terminal_equity, policy.fees, policy.turnover):
                raise AssertionError("policy and independent ledger disagree")
            equal_metrics = measure(bars, passive_fills(bars, first, cost, "equal"),
                                    first, terminal)
            btc_metrics = measure(bars, passive_fills(bars, first, cost, "btc"),
                                  first, terminal)
            measured[label] = {"policy": policy_metrics, "equal": equal_metrics,
                               "btc": btc_metrics}
            scenarios[label] = {
                "policy": {"decisions": asdict(policy)["decisions"],
                           "fills": asdict(policy)["fills"],
                           "metrics": asdict(policy_metrics)},
                "cash": asdict(measure(bars, (), first, terminal)),
                "equal": asdict(equal_metrics),
                "btc": asdict(btc_metrics),
            }
        delayed = replay(bars, first, terminal, BASE_COST, fill_hour=2,
                         extra_adverse=Decimal("0.001"))
        sensitivity = measure(bars, delayed.fills, first, terminal)
        chosen = [entry["selected"] for entry in scenarios["base"]["policy"]["decisions"]]
        verdict = decision(measured["base"]["policy"], measured["stress"]["policy"],
                           measured["base"]["equal"], measured["base"]["btc"], chosen)
        result = {"schema_version": 1, "phase": phase, "attempt_id": attempt,
                  "identity": identity, "intake_record_sha256": EXPECTED_INTAKE_SHA256,
                  "terms_url": TERMS, "terms_reviewed_utc_date": reviewed.isoformat(),
                  "source_plan_sha256": plan_hash, "data_sha256": data_hash,
                  "partition": {"first_signal": first, "terminal_signal": terminal},
                  "scenarios": scenarios, "missed_repriced_fill_sensitivity": asdict(sensitivity),
                  "decision": verdict,
                  "limitations": ["historical", "full-fill-hourly-OHLCV-assumption",
                                  "research-unit-not-venue-product-rule", "private-only"]}
        digest = _write_new(DATA / f"{phase}-result.json", _private_serializable(result))
        registry.finish(attempt, "completed", datetime.now(timezone.utc),
                        artifact_sha256=digest)
        _write_new(DATA / f"{phase}-decision.json", {
            "schema_version": 1, "phase": phase, "attempt_id": attempt,
            "code_revision": head, "configuration_sha256": config_hash,
            "artifact_sha256": digest, "outcome": verdict,
        })
    except BaseException:
        if registry.status(attempt) == "open":
            registry.finish(attempt, "failed", datetime.now(timezone.utc),
                            reason_code="evaluation-error")
        raise
    return {"phase": phase, "outcome": verdict, "artifact_sha256": digest}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=tuple(PARTITIONS), required=True)
    parser.add_argument("--terms-reviewed-utc-date", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    print(canonical_json(run(args.phase, args.terms_reviewed_utc_date)))


if __name__ == "__main__":
    main()
