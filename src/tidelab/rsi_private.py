"""One owner-approved private RSI experiment, behind shared batch execution.

This module is deliberately not a general third-party-data authorization API.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
import sys
from tidelab import private_workflow
import subprocess
from uuid import uuid4

from tidelab import historical_batch as batch
from tidelab import private_history
from tidelab.batch_review import review_scenarios
from tidelab.strategy_batch import SYNTHETIC_COST, parse_json_bytes
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
    return private_history.canonical_registry(ROOT, GRANT, AUTHORITY_HASH, PROPOSAL, RECORD_HASH)


def package(record: dict) -> dict:
    rsi = {"op": "rsi_wilder", "period": 14, "lag": 0}
    return {"schema_version": 2, "strategy_id": "lean-rsi-long-cash-hourly", "version": 1,
        "source": {"candidate_id": record["candidate_id"], "version": record["version"], "record_sha256": record_digest(record)},
        "requirements": {"interval_seconds": 3600, "product_class": "spot", "position_mode": "long_cash"},
        "rule": {"entry": {"op": "lt", "left": rsi, "right": {"op": "number", "value": "30"}},
                 "exit": {"op": "gt", "left": dict(rsi), "right": {"op": "number", "value": "70"}}, "target_fraction": "0.25"}}


def validate_rows(rows, market):
    return private_history.validate_rows(rows, market, private_history.Window(FIRST, END, ROWS))


def rows_for(db, market):
    return private_history.rows_for(db, market, private_history.Window(FIRST, END, ROWS))


def file_hash(path):
    result = sha256()
    with path.open("rb") as handle:
        for raw in iter(lambda: handle.read(1024 * 1024), b""): result.update(raw)
    return result.hexdigest()


def make_plan(descriptor: dict, record: dict) -> dict:
    return private_workflow.make_plan(sys.modules[__name__], descriptor, record)


def prepare(reviewed: str) -> dict:
    return private_workflow.prepare(sys.modules[__name__], reviewed)


class ApprovedRSIPolicy(private_workflow.ApprovedPolicy):
    def __init__(self, record, descriptor):
        super().__init__(sys.modules[__name__], record, descriptor)


def review(summary: dict) -> dict:
    return review_scenarios(summary, MARKETS, minimum_round_trips=20)


def execute(reviewed: str) -> dict:
    return private_workflow.execute(sys.modules[__name__], reviewed)

# Frozen binding values used by the shared snapshot/batch mechanics.
FAMILY = "lean-rsi-long-cash-hourly"
PACKAGE_ID = "rsi14"
RIGHTS = "okx-personal-rsi-v1"
WARMUP = 336
policy = ApprovedRSIPolicy
