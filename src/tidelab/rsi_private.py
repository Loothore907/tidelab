"""One owner-approved private RSI experiment, behind shared batch execution.

This module is deliberately not a general third-party-data authorization API.
"""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import subprocess
from uuid import uuid4

from tidelab import historical_batch as batch
from tidelab.candidate_screen import _bar
from tidelab.domain import canonical_json, isoformat_utc, parse_utc
from tidelab.historical_input import FIELDS, row_digest
from tidelab.package_lean_parity import _domain, validate_package_domain
from tidelab.storage import TideStore
from tidelab.strategy_batch import Bar, SYNTHETIC_COST, parse_json_bytes
from tidelab.strategy_intake import IntakeRegistry, record_digest
from tidelab.trial_registry import TrialRegistry

ROOT = batch.ROOT
GRANT = "owner-approval-20260926-rsi-batch-v1"
PROPOSAL = "9deef941caef52e3b9deea6aaa0988882ef538107c349fccd2fde56fe1a2f48e"
AUTHORITY_HASH = "2dc35d643753938c2c6556a497a0de1d0e93a9aa149d9ee4f41e98bb42edde7c"
RECORD_HASH = "e0f0174ee79a6d19bc9bd37375fbe93d3766070dcd942f0f085316a550a064d9"
MARKETS = ["okx:" + name + "-USDT" for name in ("BTC", "ETH", "BNB", "XRP", "SOL")]
SOURCE = "okx.historical_archive.candlesticks.1m"
FIRST = "2023-12-18T00:00:00Z"
START = "2024-01-01T00:00:00Z"
END = "2025-01-01T00:00:00Z"
ROWS = 9120
COSTS = {"baseline": dict(SYNTHETIC_COST), "stress": {**SYNTHETIC_COST, "fee_rate": "0.005", "adverse_rate": "0.002"}}


def home(): return ROOT / "data/research_program"
def registry_path(): return home() / "trials.sqlite3"
def anchor_path(): return ROOT / "data/strategy_intake/RSI-BATCH-V1-STORE.json"
def study(): return home() / "rsi-v1"


def integrated_head() -> str:
    def command(*args):
        return subprocess.check_output(args, cwd=ROOT, text=True, encoding="utf-8").strip()
    if command("git", "status", "--porcelain") or command("git", "branch", "--show-current") != "main":
        raise ValueError("clean_integrated_main_required")
    head = command("git", "rev-parse", "HEAD")
    if head != command("git", "rev-parse", "origin/main") or head != command("git", "ls-remote", "origin", "refs/heads/main").split()[0]:
        raise ValueError("fresh_main_required")
    runs = json.loads(command("gh", "run", "list", "--repo", "Loothore907/tidelab", "--commit", head,
                              "--json", "headSha,workflowName,status,conclusion", "--limit", "20"))
    if not any(x["headSha"] == head and x["workflowName"] == "CI" and x["status"] == "completed" and x["conclusion"] == "success" for x in runs):
        raise ValueError("exact_head_ci_required")
    return head


def authority() -> dict:
    base = ROOT / "data/strategy_intake"
    if batch.digest((base / "RSI-BATCH-V1-PROPOSAL.md").read_bytes()) != PROPOSAL:
        raise ValueError("proposal_identity_changed")
    raw = (base / "RSI-BATCH-V1-AUTHORITY.json").read_bytes()
    if batch.digest(raw) != AUTHORITY_HASH:
        raise ValueError("authority_identity_changed")
    receipt = parse_json_bytes(raw)
    record = batch.read(base / "lean-rsi-long-cash-hourly-v2.json")
    if receipt["selected_record_sha256"] != RECORD_HASH or record_digest(record) != RECORD_HASH:
        raise ValueError("selected_record_changed")
    IntakeRegistry(base / "intake.sqlite3").check_implementation_record(record)
    return record


def gate(reviewed: str) -> str:
    head = integrated_head()
    authority()
    if reviewed != datetime.now(timezone.utc).date().isoformat():
        raise ValueError("current_day_terms_review_required")
    return head


def initialize(reviewed: str) -> None:
    head = gate(reviewed)
    if anchor_path().exists() or registry_path().exists():
        raise ValueError("program_already_initialized_or_partial")
    home().mkdir(parents=True, exist_ok=True)
    # Anchor lives outside the registry directory; missing established DB fails closed.
    store_id = uuid4().hex
    batch.write(anchor_path(), {"store_id": store_id, "grant": GRANT, "authority_sha256": AUTHORITY_HASH})
    reg = TrialRegistry(registry_path()); reg.initialize()
    reg.reserve_access(GRANT, "authorization", {"store_id": store_id, "proposal_sha256": PROPOSAL,
        "record_sha256": RECORD_HASH, "authority_sha256": AUTHORITY_HASH, "head": head,
        "exposure": "Existing archive is exposed exploratory development; no untouched allocation.",
        "budget": {"snapshot_attempts": 1, "batch_attempts": 1, "jobs": 30}, "terms_reviewed": reviewed})


def canonical_registry() -> TrialRegistry:
    if not anchor_path().exists() or not registry_path().exists():
        raise ValueError("canonical_program_store_missing")
    anchor = batch.read(anchor_path())
    reg = TrialRegistry(registry_path())
    receipt = reg.access(GRANT, "authorization")
    if (not receipt or receipt["store_id"] != anchor["store_id"]
            or anchor.get("grant") != GRANT or anchor.get("authority_sha256") != AUTHORITY_HASH
            or receipt["authority_sha256"] != AUTHORITY_HASH or receipt["proposal_sha256"] != PROPOSAL
            or receipt["record_sha256"] != RECORD_HASH):
        raise ValueError("program_store_identity_mismatch")
    return reg


def package(record: dict) -> dict:
    rsi = {"op": "rsi_wilder", "period": 14, "lag": 0}
    return {"schema_version": 2, "strategy_id": "lean-rsi-long-cash-hourly", "version": 1,
        "source": {"candidate_id": record["candidate_id"], "version": record["version"], "record_sha256": record_digest(record)},
        "requirements": {"interval_seconds": 3600, "product_class": "spot", "position_mode": "long_cash"},
        "rule": {"entry": {"op": "lt", "left": rsi, "right": {"op": "number", "value": "30"}},
                 "exit": {"op": "gt", "left": dict(rsi), "right": {"op": "number", "value": "70"}}, "target_fraction": "0.25"}}


def validate_rows(rows, market):
    if len(rows) != ROWS: raise ValueError("window_count_mismatch")
    bars, archives = [], {}
    for index, row in enumerate(rows):
        when = parse_utc(FIRST) + timedelta(hours=index)
        if (row["event_time_utc"] != isoformat_utc(when) or row["source"] != SOURCE or row["closed"] != 1
                or row["schema_version"] != 1 or row["venue"] != "okx" or row["instrument_id"] != market
                or row["event_type"] != "bar" or row["interval_seconds"] != 3600):
            raise ValueError("source_continuity_mismatch")
        payload = parse_json_bytes(row["payload_json"].encode())
        bar = _bar(when, canonical_json(payload))
        _domain(str(bar.open)); _domain(str(bar.close))
        native = parse_json_bytes(row["native_json"].encode())
        day = (when + timedelta(hours=8)).date()
        period = native.get("archive_period", native.get("archive_month"))
        digest = native.get("archive_sha256")
        if (period not in (day.isoformat(), day.strftime("%Y-%m")) or native.get("minute_rows") != 60
                or not isinstance(digest, str) or not batch.DIGEST.fullmatch(digest)
                or ("archive_period" in native and "archive_month" in native)
                or (len(period) == 10 and "archive_period" not in native)):
            raise ValueError("archive_provenance_mismatch")
        name = f"{market.removeprefix('okx:')}-candlesticks-{period}.zip"
        if name in archives and archives[name] != digest: raise ValueError("conflicting_archive_identity")
        archives[name] = digest
        bars.append(Bar(when, bar.open, bar.close))
    return tuple(bars), archives


def rows_for(db, market):
    return db.execute(f"""SELECT {','.join(FIELDS)} FROM market_events WHERE venue='okx'
        AND instrument_id=? AND event_type='bar' AND interval_seconds=3600
        AND event_time_utc>=? AND event_time_utc<? ORDER BY event_time_utc,event_id""",
        (market, FIRST, END)).fetchmany(ROWS + 1)


def file_hash(path):
    result = sha256()
    with path.open("rb") as handle:
        for raw in iter(lambda: handle.read(1024 * 1024), b""): result.update(raw)
    return result.hexdigest()


def make_plan(descriptor: dict, record: dict) -> dict:
    refs = [{"id": "rsi14", "package": "package.json", "record": "record.json",
             "package_sha256": batch.digest((canonical_json(package(record)) + "\n").encode()),
             "record_sha256": batch.digest((canonical_json(record) + "\n").encode())}]
    jobs = [{"package": "rsi14", "market": m, "cost": c, "benchmark": b}
            for m in MARKETS for b in (None, "cash", "passive") for c in ("baseline", "stress")]
    return {"schema_version": 1, "kind": "third_party", "family": "lean-rsi-long-cash-hourly", "generation": "v1",
        "parent_experiment": None, "phase": "development", "issue": 95, "authority": GRANT,
        "markets": MARKETS, "partitions": {"development": {"start": START, "end": END}},
        "packages": refs, "jobs": jobs, "costs": COSTS, "budget": 30, "max_bars": 10000,
        "benchmark_allocation": "0.25", "metrics": batch.METRICS, "selection": "none", "retention": "retain_all_local",
        "snapshot_sha256": batch.digest((canonical_json(descriptor) + "\n").encode())}


def prepare(reviewed: str) -> dict:
    head = gate(reviewed); reg = canonical_registry(); record = authority()
    reg.reserve_access(GRANT, "snapshot", {"head": head, "authority_sha256": AUTHORITY_HASH,
        "source": SOURCE, "markets": MARKETS, "first": FIRST, "end": END, "terms_reviewed": reviewed})
    study().mkdir(exist_ok=False)
    batch.write(study() / "preparation.json", {"head": head, "status": "started", "started_utc": batch.now()})
    try:
        snapshot = study() / "snapshot.sqlite3"
        TideStore(snapshot).initialize()
        descriptor = {"schema_version": 1, "kind": "third_party", "source": SOURCE, "venue": "okx",
            "interval_seconds": 3600, "rights_reference": "okx-personal-rsi-v1", "receipt": GRANT, "partitions": {}}
        archives = {}
        # One consistent source transaction; no query includes an outside-window payload.
        source = ROOT / "data/okx/research.sqlite3"
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as db, closing(sqlite3.connect(snapshot)) as target:
            db.row_factory = sqlite3.Row; db.execute("BEGIN")
            for market in MARKETS:
                rows = rows_for(db, market)
                _, market_archives = validate_rows(rows, market)
                archives.update(market_archives)
                target.executemany(f"INSERT INTO market_events ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})",
                                   [tuple(row[k] for k in FIELDS) for row in rows])
                descriptor["partitions"][market] = {"start": START, "end": END, "warmup_bars": 336, "sha256": row_digest(rows)}
            target.commit()
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            target.execute("PRAGMA journal_mode=DELETE")
        for name, expected in archives.items():
            if file_hash(ROOT / "data/okx" / name) != expected: raise ValueError("archive_bytes_changed")
        batch.write(study() / "snapshot.json", descriptor)
        batch.write(study() / "record.json", record)
        batch.write(study() / "package.json", package(record))
        batch.write(study() / "plan.json", make_plan(descriptor, record))
        result = {"status": "prepared", "head": head, "grant": GRANT, "terms_reviewed": reviewed,
                  "snapshot_file_sha256": file_hash(snapshot), "archives": archives,
                  "completed_utc": batch.now()}
        batch.write(study() / "prepared.json", result)
        reg.reserve_access(GRANT, "snapshot_complete", {"receipt_sha256": batch.digest((study() / "prepared.json").read_bytes()),
            "descriptor_sha256": batch.digest((study() / "snapshot.json").read_bytes()),
            "plan_sha256": batch.digest((study() / "plan.json").read_bytes())})
        return {"status": "prepared", "markets": 5}
    except Exception as exc:
        batch.write(study() / "preparation-failed.json", {"status": "failed", "reason": type(exc).__name__, "detail": str(exc)})
        raise


class ApprovedRSIPolicy:
    def __init__(self, record, descriptor): self.record, self.descriptor = record, descriptor
    def preflight(self, plan, descriptor):
        if descriptor != self.descriptor or plan != make_plan(descriptor, self.record):
            raise ValueError("outside_approved_plan")
    def package(self, candidate, record):
        if record != self.record or candidate != package(self.record): raise ValueError("outside_selected_candidate")
        return validate_package_domain(candidate, record, synthetic_only=False)
    def read_partition(self, database, descriptor, market, *, capture=None):
        if database.resolve() != (study() / "snapshot.sqlite3").resolve() or market not in MARKETS:
            raise ValueError("outside_approved_snapshot")
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row; db.execute("BEGIN")
            rows = rows_for(db, market); bars, _ = validate_rows(rows, market)
            if row_digest(rows) != descriptor["partitions"][market]["sha256"]: raise ValueError("snapshot_rows_changed")
        if capture: capture([dict(row) for row in rows])
        return bars


def review(summary: dict) -> dict:
    markets = []
    for m_index, market in enumerate(MARKETS):
        rows = summary["jobs"][m_index * 6:(m_index + 1) * 6]
        if (len(summary["jobs"]) != 30 or len(rows) != 6
                or any(x.get("index") != m_index * 6 + i or x["status"] != "completed" for i, x in enumerate(rows))):
            markets.append({"market": market, "status": "incomplete"}); continue
        base, stress, cash, cash_stress, passive, passive_stress = [x["metrics"] for x in rows]
        excess = Decimal(base["net_return"]) - Decimal(passive["net_return"])
        if base["round_trips"] < 20: status = "inconclusive"
        elif (Decimal(base["net_return"]) > 0 and excess > 0 and Decimal(stress["net_return"]) > 0
              and Decimal(base["max_drawdown"]) <= Decimal("0.15")): status = "eligible_for_deeper_review"
        else: status = "not_nominated"
        markets.append({"market": market, "status": status, "baseline_excess_return": str(excess)})
    incomplete = any(x["status"] == "incomplete" for x in markets)
    return {"status": "incomplete" if incomplete else "reviewed", "markets": markets,
            "eligibility_provisional": incomplete, "automatic_promotion": False,
            "scope": "exposed_history_exploratory_triage_not_edge_evidence"}


def execute(reviewed: str) -> dict:
    head = gate(reviewed); reg = canonical_registry(); record = authority()
    receipt = reg.access(GRANT, "snapshot_complete")
    if not receipt: raise ValueError("snapshot_not_prepared")
    if (batch.digest((study() / "prepared.json").read_bytes()) != receipt["receipt_sha256"]
            or batch.digest((study() / "snapshot.json").read_bytes()) != receipt["descriptor_sha256"]
            or batch.digest((study() / "plan.json").read_bytes()) != receipt["plan_sha256"]):
        raise ValueError("preparation_identity_changed")
    prepared = batch.read(study() / "prepared.json")
    if prepared["head"] != head: raise ValueError("code_changed_since_preparation")
    descriptor = batch.read(study() / "snapshot.json")
    # The grant is consumed before verifying snapshot bytes or executing any trial.
    reg.reserve_access(GRANT, "batch", {"head": head, "snapshot_receipt": receipt, "terms_reviewed": reviewed})
    if file_hash(study() / "snapshot.sqlite3") != prepared["snapshot_file_sha256"]:
        raise ValueError("snapshot_file_changed")
    result = batch.run(study() / "plan.json", study() / "snapshot.json", study() / "snapshot.sqlite3",
        registry_path(), study() / "attempt", _policy=ApprovedRSIPolicy(record, descriptor))
    if "jobs" not in result or len(result["jobs"]) != 30: raise ValueError("batch_incomplete")
    verdict = review(result)
    batch.write(study() / "review.json", verdict)
    reg.reserve_access(GRANT, "review", {"review_sha256": batch.digest((study() / "review.json").read_bytes()),
                                       "batch_id": result["batch_id"]})
    return {"status": verdict["status"], "jobs": len(result["jobs"]), "results_private": True}
