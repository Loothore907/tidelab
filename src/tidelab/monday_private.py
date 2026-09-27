"""Exact owner-approved monday trial; append to the established research store.

No initializer, alternate store, market/date/parameter override or retry route.
The synthetic monday module's unapproved entrypoints remain hard stops.
"""
from datetime import datetime, timezone
from decimal import Decimal
import sys

from tidelab import historical_batch as batch, private_history, private_workflow, rsi_private
from tidelab.batch_review import review_scenarios, trace_diagnostics
from tidelab.btc_monday import package
from tidelab.package_lean_parity import validate_package_domain
from tidelab.strategy_intake import IntakeRegistry, record_digest

ROOT = batch.ROOT
GRANT = "owner-approval-20260927-monday-batch-v1"
PROPOSAL = "6096a188e443dfce437c068518a3d4262fa646c802e46d7871ae699ffec053f3"
AUTHORITY_HASH = "fddb9eaede67fbf8936619c60716d618619431d5eea2c482a3460ffec4899968"
RECORD_HASH = "6c4144cb2a9c9a33faa3c9382c34616263106c7f378d4a3797714820460b7c20"
MARKETS = ["okx:BTC-USDT"]
SOURCE = "okx.historical_archive.candlesticks.1m"
FIRST, START, END = "2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "2025-01-01T00:00:00Z"
ROWS, WARMUP = 8784, 0
JOBS = 6
FAMILY, PACKAGE_ID, RIGHTS = "caporale-plastun-btc-monday-utc", "monday", "okx-personal-monday-v1"
COSTS = {"baseline": dict(rsi_private.COSTS["baseline"]), "stress": dict(rsi_private.COSTS["stress"])}


def home(): return ROOT / "data/research_program"
def registry_path(): return home() / "trials.sqlite3"
def study(): return home() / "monday-v1"


def authority():
    base = ROOT / "data/strategy_intake"
    for name, expected in (("BTC-MONDAY-V1-PROPOSAL.md", PROPOSAL),
                           ("BTC-MONDAY-V1-TRIAL-AUTHORITY.json", AUTHORITY_HASH)):
        if batch.digest((base / name).read_bytes()) != expected:
            raise ValueError("monday_authority_identity_changed")
    receipt = batch.read(base / "BTC-MONDAY-V1-TRIAL-AUTHORITY.json")
    record = batch.read(base / "caporale-plastun-btc-monday-utc-v2.json")
    if receipt["selected_record_sha256"] != RECORD_HASH or record_digest(record) != RECORD_HASH:
        raise ValueError("selected_record_changed")
    IntakeRegistry(base / "intake.sqlite3").check_implementation_record(record)
    validate_package_domain(package(record), record, synthetic_only=False)
    return record


def canonical_registry():
    # The original store's identity stays anchored in the original RSI receipt.
    # Do not replace that anchor or initialize a fresh DB for a new hypothesis.
    return private_history.canonical_registry(ROOT, rsi_private.GRANT, rsi_private.AUTHORITY_HASH,
                                              rsi_private.PROPOSAL, rsi_private.RECORD_HASH)


def _base_gate(reviewed):
    head = rsi_private.integrated_head()
    authority()
    if reviewed != datetime.now(timezone.utc).date().isoformat():
        raise ValueError("current_day_terms_review_required")
    return head


def authorize(reviewed):
    head = _base_gate(reviewed)
    reg = canonical_registry()
    anchor = batch.read(ROOT / "data/strategy_intake/RSI-BATCH-V1-STORE.json")
    reg.reserve_access(GRANT, "authorization", {"store_id": anchor["store_id"], "head": head,
        "authority_sha256": AUTHORITY_HASH, "proposal_sha256": PROPOSAL, "record_sha256": RECORD_HASH,
        "budget": {"snapshot_attempts": 1, "batch_attempts": 1, "jobs": JOBS, "execution_seconds": 1800},
        "first": FIRST, "start": START, "end": END, "markets": MARKETS, "terms_reviewed": reviewed,
        "exposure": "Previously exposed exploratory history; no untouched allocation; no retries."})
    return {"status": "authorized", "prices_read": False}


def approved_gate(reviewed):
    head = _base_gate(reviewed)
    receipt = canonical_registry().access(GRANT, "authorization")
    if (not receipt or receipt.get("head") != head or receipt.get("authority_sha256") != AUTHORITY_HASH
            or receipt.get("proposal_sha256") != PROPOSAL or receipt.get("record_sha256") != RECORD_HASH):
        raise ValueError("monday_grant_missing_or_changed")
    return head


gate = approved_gate


def rows_for(db, market):
    if market not in MARKETS: raise ValueError("outside_approved_market")
    return private_history.rows_for(db, market, private_history.Window(FIRST, END, ROWS))


def validate_rows(rows, market):
    return private_history.validate_rows(rows, market, private_history.Window(FIRST, END, ROWS), preserve_ohlc=True)


def make_plan(descriptor, record):
    return private_workflow.make_plan(sys.modules[__name__], descriptor, record)


class ApprovedMondayPolicy(private_workflow.ApprovedPolicy):
    def __init__(self, record, descriptor):
        super().__init__(sys.modules[__name__], record, descriptor)


policy = ApprovedMondayPolicy


def review(summary):
    result = review_scenarios(summary, MARKETS, minimum_round_trips=52)
    result["policy"] = "btc-monday-v1-exact-52-closed-trips"
    try:
        jobs = summary["jobs"]
        valid = (len(jobs) == JOBS
            and all(j["status"] == "completed" and type(j["metrics"]["scored_bars"]) is int
                    and j["metrics"]["scored_bars"] == ROWS for j in jobs)
            and all(type(j["metrics"]["round_trips"]) is int and j["metrics"]["round_trips"] == 52
                    and Decimal(j["metrics"]["terminal_units"]) == 0 for j in jobs[:2]))
    except (KeyError, TypeError, ValueError, ArithmeticError):
        valid = False
    if not valid:
        result.update(status="incomplete", eligibility_provisional=True,
            markets=[{"market": MARKETS[0], "status": "incomplete", "reason": "calendar_conformance_failed"}])
    return result


def prepare(reviewed):
    return private_workflow.prepare(sys.modules[__name__], reviewed)


def execute(reviewed):
    result = private_workflow.execute(sys.modules[__name__], reviewed)
    output = study() / "attempt"
    batch.verify(output)
    summary = batch.read(output / "summary.json")
    plan = batch.read(output / "inputs/plan.json")
    diagnostics = []
    for row in summary["jobs"]:
        if row["status"] == "completed":
            index = row["index"]; cost = COSTS[plan["jobs"][index]["cost"]]
            diagnostics.append({"index": index, **trace_diagnostics(output / f"job-{index}" / "trace.jsonl",
                fee_rate=Decimal(cost["fee_rate"]), adverse_rate=Decimal(cost["adverse_rate"]))})
    batch.write(study() / "diagnostics.json", {"jobs": diagnostics})
    return result
