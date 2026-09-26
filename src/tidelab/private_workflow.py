"""Shared one-shot private workflow for the frozen RSI and channel bindings.

Bindings own exact authority, package, window and review policy. This module
only performs the established snapshot/admission mechanics; it grants nothing.
"""
from contextlib import closing
from hashlib import sha256
import sqlite3
from tidelab import historical_batch as batch
from tidelab.domain import canonical_json
from tidelab.historical_input import FIELDS, row_digest
from tidelab.storage import TideStore
from tidelab.package_lean_parity import validate_package_domain


def file_hash(path):
    result = sha256()
    with path.open("rb") as handle:
        for raw in iter(lambda: handle.read(1024 * 1024), b""): result.update(raw)
    return result.hexdigest()


def make_plan(binding, descriptor: dict, record: dict) -> dict:
    refs = [{"id": binding.PACKAGE_ID, "package": "package.json", "record": "record.json",
             "package_sha256": batch.digest((canonical_json(binding.package(record)) + "\n").encode()),
             "record_sha256": batch.digest((canonical_json(record) + "\n").encode())}]
    jobs = [{"package": binding.PACKAGE_ID, "market": m, "cost": c, "benchmark": b}
            for m in binding.MARKETS for b in (None, "cash", "passive") for c in ("baseline", "stress")]
    return {"schema_version": 1, "kind": "third_party", "family": binding.FAMILY, "generation": "v1",
        "parent_experiment": None, "phase": "development", "issue": 95, "authority": binding.GRANT,
        "markets": binding.MARKETS, "partitions": {"development": {"start": binding.START, "end": binding.END}},
        "packages": refs, "jobs": jobs, "costs": binding.COSTS, "budget": 30, "max_bars": 10000,
        "benchmark_allocation": "0.25", "metrics": batch.METRICS, "selection": "none", "retention": "retain_all_local",
        "snapshot_sha256": batch.digest((canonical_json(descriptor) + "\n").encode())}



def prepare(binding, reviewed: str) -> dict:
    head = binding.gate(reviewed); reg = binding.canonical_registry(); record = binding.authority()
    reg.reserve_access(binding.GRANT, "snapshot", {"head": head, "authority_sha256": binding.AUTHORITY_HASH,
        "source": binding.SOURCE, "markets": binding.MARKETS, "first": binding.FIRST, "end": binding.END, "terms_reviewed": reviewed})
    binding.study().mkdir(exist_ok=False)
    batch.write(binding.study() / "preparation.json", {"head": head, "status": "started", "started_utc": batch.now()})
    try:
        snapshot = binding.study() / "snapshot.sqlite3"
        TideStore(snapshot).initialize()
        descriptor = {"schema_version": 1, "kind": "third_party", "source": binding.SOURCE, "venue": "okx",
            "interval_seconds": 3600, "rights_reference": binding.RIGHTS, "receipt": binding.GRANT, "partitions": {}}
        archives = {}
        # One consistent source transaction; no query includes an outside-window payload.
        source = binding.ROOT / "data/okx/research.sqlite3"
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as db, closing(sqlite3.connect(snapshot)) as target:
            db.row_factory = sqlite3.Row; db.execute("BEGIN")
            for market in binding.MARKETS:
                rows = binding.rows_for(db, market)
                _, market_archives = binding.validate_rows(rows, market)
                archives.update(market_archives)
                target.executemany(f"INSERT INTO market_events ({','.join(FIELDS)}) VALUES ({','.join('?' for _ in FIELDS)})",
                                   [tuple(row[k] for k in FIELDS) for row in rows])
                descriptor["partitions"][market] = {"start": binding.START, "end": binding.END, "warmup_bars": binding.WARMUP, "sha256": row_digest(rows)}
            target.commit()
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            target.execute("PRAGMA journal_mode=DELETE")
        for name, expected in archives.items():
            if file_hash(binding.ROOT / "data/okx" / name) != expected: raise ValueError("archive_bytes_changed")
        batch.write(binding.study() / "snapshot.json", descriptor)
        batch.write(binding.study() / "record.json", record)
        batch.write(binding.study() / "package.json", binding.package(record))
        batch.write(binding.study() / "plan.json", binding.make_plan(descriptor, record))
        result = {"status": "prepared", "head": head, "grant": binding.GRANT, "terms_reviewed": reviewed,
                  "snapshot_file_sha256": file_hash(snapshot), "archives": archives,
                  "completed_utc": batch.now()}
        batch.write(binding.study() / "prepared.json", result)
        reg.reserve_access(binding.GRANT, "snapshot_complete", {"receipt_sha256": batch.digest((binding.study() / "prepared.json").read_bytes()),
            "descriptor_sha256": batch.digest((binding.study() / "snapshot.json").read_bytes()),
            "plan_sha256": batch.digest((binding.study() / "plan.json").read_bytes())})
        return {"status": "prepared", "markets": 5}
    except Exception as exc:
        batch.write(binding.study() / "preparation-failed.json", {"status": "failed", "reason": type(exc).__name__, "detail": str(exc)})
        raise



def execute(binding, reviewed: str) -> dict:
    head = binding.gate(reviewed); reg = binding.canonical_registry(); record = binding.authority()
    receipt = reg.access(binding.GRANT, "snapshot_complete")
    if not receipt: raise ValueError("snapshot_not_prepared")
    if (batch.digest((binding.study() / "prepared.json").read_bytes()) != receipt["receipt_sha256"]
            or batch.digest((binding.study() / "snapshot.json").read_bytes()) != receipt["descriptor_sha256"]
            or batch.digest((binding.study() / "plan.json").read_bytes()) != receipt["plan_sha256"]):
        raise ValueError("preparation_identity_changed")
    prepared = batch.read(binding.study() / "prepared.json")
    if prepared["head"] != head: raise ValueError("code_changed_since_preparation")
    descriptor = batch.read(binding.study() / "snapshot.json")
    # The grant is consumed before verifying snapshot bytes or executing any trial.
    reg.reserve_access(binding.GRANT, "batch", {"head": head, "snapshot_receipt": receipt, "terms_reviewed": reviewed})
    if file_hash(binding.study() / "snapshot.sqlite3") != prepared["snapshot_file_sha256"]:
        raise ValueError("snapshot_file_changed")
    result = batch.run(binding.study() / "plan.json", binding.study() / "snapshot.json", binding.study() / "snapshot.sqlite3",
        binding.registry_path(), binding.study() / "attempt", _policy=binding.policy(record, descriptor))
    if "jobs" not in result or len(result["jobs"]) != 30: raise ValueError("batch_incomplete")
    verdict = binding.review(result)
    batch.write(binding.study() / "review.json", verdict)
    reg.reserve_access(binding.GRANT, "review", {"review_sha256": batch.digest((binding.study() / "review.json").read_bytes()),
                                       "batch_id": result["batch_id"]})
    return {"status": verdict["status"], "jobs": len(result["jobs"]), "results_private": True}



class ApprovedPolicy:
    def __init__(self, binding, record, descriptor):
        self.binding, self.record, self.descriptor = binding, record, descriptor
    def preflight(self, plan, descriptor):
        if descriptor != self.descriptor or plan != self.binding.make_plan(descriptor, self.record):
            raise ValueError("outside_approved_plan")
    def package(self, candidate, record):
        if record != self.record or candidate != self.binding.package(self.record): raise ValueError("outside_selected_candidate")
        return validate_package_domain(candidate, record, synthetic_only=False)
    def read_partition(self, database, descriptor, market, *, capture=None):
        if database.resolve() != (self.binding.study() / "snapshot.sqlite3").resolve() or market not in self.binding.MARKETS:
            raise ValueError("outside_approved_snapshot")
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row; db.execute("BEGIN")
            rows = self.binding.rows_for(db, market); bars, _ = self.binding.validate_rows(rows, market)
            if row_digest(rows) != descriptor["partitions"][market]["sha256"]: raise ValueError("snapshot_rows_changed")
        if capture: capture([dict(row) for row in rows])
        return bars
