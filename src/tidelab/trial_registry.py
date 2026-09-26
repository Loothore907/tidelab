"""Local append-only trial attempts around a portable experiment identity."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from typing import Mapping
from time import monotonic, sleep

from tidelab.domain import canonical_json
from tidelab.experiment_identity import build_experiment_identity


_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_PHASES = ("development", "validation", "untouched")
_OUTCOMES = ("completed", "failed", "aborted")


def _utc(value: datetime) -> str:
    if value.tzinfo != timezone.utc:
        raise ValueError("trial event time must be UTC")
    return value.isoformat()


def _identity(identity: Mapping[str, object]) -> dict[str, object]:
    if set(identity) != {"schema_version", "engine", "code", "configuration",
                         "data", "cost", "trial", "identity_sha256"}:
        raise ValueError("experiment identity fields are incomplete")
    try:
        expected = build_experiment_identity(**{
            name: identity[name] for name in
            ("engine", "code", "configuration", "data", "cost", "trial")
        })
    except (TypeError, KeyError) as exc:
        raise ValueError("invalid experiment identity") from exc
    if identity != expected:
        raise ValueError("experiment identity digest mismatch")
    return expected


class TrialRegistry:
    """Record each launch before work; a process death leaves an open attempt.

    This is a local audit record, not tamper-proof storage or a rights grant.
    Results and logs stay outside this metadata database.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA synchronous = FULL")
        return db

    def initialize(self) -> None:
        with closing(self._connect()) as db:
            # SQLite can return BUSY immediately while two connections bootstrap
            # WAL, even with busy_timeout set. Retrying this idempotent pragma
            # cannot rerun a trial or erase an admission request.
            deadline = monotonic() + 10
            while True:
                try:
                    db.execute("PRAGMA journal_mode = WAL")
                    break
                except sqlite3.OperationalError as exc:
                    if (getattr(exc, "sqlite_errorcode", 0) & 255) not in (
                            sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) or monotonic() >= deadline:
                        raise
                    sleep(0.05)
            db.execute("""CREATE TABLE IF NOT EXISTS trial_attempts (
                attempt_id TEXT PRIMARY KEY,
                identity_sha256 TEXT NOT NULL,
                identity_json TEXT NOT NULL,
                strategy_id TEXT NOT NULL,
                strategy_version TEXT NOT NULL,
                phase TEXT NOT NULL CHECK (phase IN ('development', 'validation', 'untouched')),
                started_utc TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS trial_outcomes (
                attempt_id TEXT PRIMARY KEY REFERENCES trial_attempts(attempt_id),
                outcome TEXT NOT NULL CHECK (outcome IN ('completed', 'failed', 'aborted')),
                finished_utc TEXT NOT NULL,
                reason_code TEXT,
                artifact_sha256 TEXT
            )""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_validation_identity
                ON trial_attempts(identity_sha256, phase) WHERE phase='validation'""")
            db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_untouched_strategy_version
                ON trial_attempts(strategy_id, strategy_version) WHERE phase='untouched'""")
            db.execute("""CREATE TABLE IF NOT EXISTS batch_requests (
                request_id TEXT PRIMARY KEY, plan_sha256 TEXT NOT NULL,
                received_utc TEXT NOT NULL, disposition TEXT NOT NULL, reason TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS research_batches (
                batch_id TEXT PRIMARY KEY REFERENCES batch_requests(request_id),
                family TEXT NOT NULL, generation TEXT NOT NULL, phase TEXT NOT NULL,
                plan_sha256 TEXT NOT NULL, inventory_json TEXT NOT NULL,
                retry_of TEXT REFERENCES research_batches(batch_id),
                started_utc TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS batch_job_outcomes (
                batch_id TEXT NOT NULL REFERENCES research_batches(batch_id),
                job_index INTEGER NOT NULL, result_json TEXT NOT NULL,
                PRIMARY KEY(batch_id, job_index))""")
            db.execute("""CREATE TABLE IF NOT EXISTS batch_outcomes (
                batch_id TEXT PRIMARY KEY REFERENCES research_batches(batch_id),
                outcome TEXT NOT NULL, finished_utc TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS research_access (
                grant_id TEXT NOT NULL, stage TEXT NOT NULL, identity_json TEXT NOT NULL,
                started_utc TEXT NOT NULL, PRIMARY KEY(grant_id,stage))""")
            for table in ("trial_attempts", "trial_outcomes", "batch_requests",
                          "research_batches", "batch_job_outcomes", "batch_outcomes", "research_access"):
                db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_update
                    BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable trial record'); END""")
                db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable trial record'); END""")

    def reserve_access(self, grant_id: str, stage: str, identity: dict) -> None:
        """One immutable authorization consumption before private data access."""
        with closing(self._connect()) as db:
            db.execute("INSERT INTO research_access VALUES (?,?,?,?)",
                       (grant_id, stage, canonical_json(identity), datetime.now(timezone.utc).isoformat()))

    def access(self, grant_id: str, stage: str) -> dict | None:
        import json
        with closing(self._connect()) as db:
            row = db.execute("SELECT identity_json FROM research_access WHERE grant_id=? AND stage=?",
                             (grant_id, stage)).fetchone()
        return json.loads(row[0]) if row else None

    def reserve_batch(self, batch_id: str, *, family: str, generation: str,
                      phase: str, plan_sha256: str, inventory: list[dict],
                      retry_of: str | None = None) -> str | None:
        """Atomically admit the complete inventory, or retain a rejected request.

        The caller owns source authority; only development is admitted here. Returned text is a
        rejection reason; no exception/rollback erases a concurrency loser.
        """
        if any(not isinstance(v, str) or not _TOKEN.fullmatch(v)
               for v in (batch_id, family, generation)) or not _DIGEST.fullmatch(plan_sha256):
            raise ValueError("invalid_batch_identity")
        if not inventory:
            raise ValueError("empty_inventory")
        import json
        now = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                reason = None
                if phase != "development":
                    reason = "phase_not_enabled"
                prior = db.execute("""SELECT b.* FROM research_batches b
                    WHERE family=? AND generation=? AND phase=? ORDER BY rowid DESC LIMIT 1""",
                    (family, generation, phase)).fetchone()
                if prior:
                    terminal = db.execute("SELECT outcome FROM batch_outcomes WHERE batch_id=?",
                                          (prior["batch_id"],)).fetchone()
                    if (retry_of != prior["batch_id"] or terminal is None
                            or terminal[0] not in ("aborted", "failed")
                            or prior["plan_sha256"] != plan_sha256):
                        reason = "phase_already_reserved"
                    elif [x.get("identity") for x in json.loads(prior["inventory_json"])] != [
                            x.get("identity") for x in inventory]:
                        reason = "retry_identity_changed"
                elif retry_of is not None:
                    reason = "invalid_retry_parent"
                if db.execute("""SELECT 1 FROM research_batches b LEFT JOIN batch_outcomes o
                    ON o.batch_id=b.batch_id WHERE o.batch_id IS NULL LIMIT 1""").fetchone():
                    reason = "unfinished_batch"
                db.execute("INSERT INTO batch_requests VALUES (?,?,?,?,?)",
                           (batch_id, plan_sha256, now, "rejected" if reason else "admitted", reason))
                if reason is None:
                    db.execute("INSERT INTO research_batches VALUES (?,?,?,?,?,?,?,?)",
                               (batch_id, family, generation, phase, plan_sha256,
                                canonical_json(inventory), retry_of, now))
                db.commit()
                return reason
            except BaseException:
                db.rollback()
                raise

    def batch(self, batch_id: str) -> dict:
        import json
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM research_batches WHERE batch_id=?", (batch_id,)).fetchone()
            if row is None:
                raise ValueError("unknown_batch")
            result = dict(row)
            result["inventory"] = json.loads(result.pop("inventory_json"))
            result["jobs"] = {row["job_index"]: json.loads(row["result_json"]) for row in db.execute(
                "SELECT * FROM batch_job_outcomes WHERE batch_id=?", (batch_id,))}
            terminal = db.execute("SELECT * FROM batch_outcomes WHERE batch_id=?", (batch_id,)).fetchone()
            result["terminal"] = dict(terminal) if terminal else None
            result["attempt_statuses"] = {}
            attempts = [x["attempt_id"] for x in result["inventory"] if "attempt_id" in x]
            for offset in range(0, len(attempts), 500):
                ids = attempts[offset:offset + 500]
                for attempt in db.execute(f"""SELECT a.attempt_id, o.outcome FROM trial_attempts a
                    LEFT JOIN trial_outcomes o ON o.attempt_id=a.attempt_id
                    WHERE a.attempt_id IN ({','.join('?' for _ in ids)})""", ids):
                    result["attempt_statuses"][attempt["attempt_id"]] = attempt["outcome"] or "open"
            return result

    def finish_job(self, batch_id: str, index: int, result: dict) -> None:
        import json
        encoded = canonical_json(result)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                batch = db.execute("SELECT inventory_json FROM research_batches WHERE batch_id=?", (batch_id,)).fetchone()
                if batch is None or type(index) is not int or not 0 <= index < len(json.loads(batch[0])):
                    raise ValueError("unknown_batch_job")
                old = db.execute("SELECT result_json FROM batch_job_outcomes WHERE batch_id=? AND job_index=?",
                                 (batch_id, index)).fetchone()
                if old:
                    if old[0] != encoded:
                        raise ValueError("job_already_finished_differently")
                else:
                    db.execute("INSERT INTO batch_job_outcomes VALUES (?,?,?)", (batch_id, index, encoded))
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def finish_batch(self, batch_id: str, outcome: str, artifact_sha256: str) -> None:
        import json
        if outcome not in _OUTCOMES or not _DIGEST.fullmatch(artifact_sha256):
            raise ValueError("invalid_batch_outcome")
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute("SELECT inventory_json FROM research_batches WHERE batch_id=?", (batch_id,)).fetchone()
                count = db.execute("SELECT COUNT(*) FROM batch_job_outcomes WHERE batch_id=?", (batch_id,)).fetchone()[0]
                if row is None or count != len(json.loads(row[0])):
                    raise ValueError("incomplete_batch_inventory")
                old = db.execute("SELECT outcome, artifact_sha256 FROM batch_outcomes WHERE batch_id=?", (batch_id,)).fetchone()
                if old:
                    if tuple(old) != (outcome, artifact_sha256):
                        raise ValueError("batch_already_finished_differently")
                else:
                    db.execute("INSERT INTO batch_outcomes VALUES (?,?,?,?)",
                               (batch_id, outcome, datetime.now(timezone.utc).isoformat(), artifact_sha256))
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def start(self, attempt_id: str, identity: Mapping[str, object],
              phase: str, started_at: datetime) -> bool:
        """Append before executing a trial; False for an identical replay."""
        if not isinstance(attempt_id, str) or not _TOKEN.fullmatch(attempt_id):
            raise ValueError("attempt ID must be a portable identifier")
        if phase not in _PHASES:
            raise ValueError("unknown research phase")
        checked = _identity(identity)
        started = _utc(started_at)
        trial = checked["trial"]
        fields = (attempt_id, checked["identity_sha256"], canonical_json(checked),
                  trial["strategy_id"], trial["strategy_version"], phase, started)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                existing = db.execute("SELECT * FROM trial_attempts WHERE attempt_id=?",
                                      (attempt_id,)).fetchone()
                if existing is not None:
                    if tuple(existing) != fields:
                        raise ValueError("attempt ID already has different terms")
                    db.commit()
                    return False
                if db.execute("""SELECT 1 FROM trial_attempts AS a
                    LEFT JOIN trial_outcomes AS o ON o.attempt_id=a.attempt_id
                    WHERE a.strategy_id=? AND a.strategy_version=?
                    AND o.attempt_id IS NULL LIMIT 1""",
                    (trial["strategy_id"], trial["strategy_version"])).fetchone():
                    raise RuntimeError("previous trial attempt is unfinished")
                if phase == "validation" and db.execute("""SELECT 1 FROM trial_attempts
                    WHERE identity_sha256=? AND phase='validation' LIMIT 1""",
                    (checked["identity_sha256"],)).fetchone():
                    raise RuntimeError("validation identity was already opened")
                if phase == "untouched" and db.execute("""SELECT 1 FROM trial_attempts
                    WHERE strategy_id=? AND strategy_version=? AND phase='untouched'
                    LIMIT 1""", (trial["strategy_id"],
                                 trial["strategy_version"])).fetchone():
                    raise RuntimeError("untouched strategy version was already opened")
                db.execute("""INSERT INTO trial_attempts VALUES (?, ?, ?, ?, ?, ?, ?)""",
                           fields)
                db.commit()
                return True
            except BaseException:
                db.rollback()
                raise

    def finish(self, attempt_id: str, outcome: str, finished_at: datetime,
               *, reason_code: str | None = None,
               artifact_sha256: str | None = None) -> bool:
        """Append a terminal outcome without storing results or exception text."""
        if outcome not in _OUTCOMES:
            raise ValueError("unknown trial outcome")
        if reason_code is not None and not _TOKEN.fullmatch(reason_code):
            raise ValueError("reason code must be a portable identifier")
        if artifact_sha256 is not None and not _DIGEST.fullmatch(artifact_sha256):
            raise ValueError("artifact digest must be lowercase SHA-256")
        finished = _utc(finished_at)
        fields = (attempt_id, outcome, finished, reason_code, artifact_sha256)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                started = db.execute("SELECT started_utc FROM trial_attempts WHERE attempt_id=?",
                                     (attempt_id,)).fetchone()
                if started is None:
                    raise ValueError("unknown trial attempt")
                if finished < started["started_utc"]:
                    raise ValueError("trial finished before it started")
                existing = db.execute("SELECT * FROM trial_outcomes WHERE attempt_id=?",
                                      (attempt_id,)).fetchone()
                if existing is not None:
                    if tuple(existing) != fields:
                        raise ValueError("trial outcome already recorded differently")
                    db.commit()
                    return False
                db.execute("INSERT INTO trial_outcomes VALUES (?, ?, ?, ?, ?)", fields)
                db.commit()
                return True
            except BaseException:
                db.rollback()
                raise

    def status(self, attempt_id: str) -> str | None:
        with closing(self._connect()) as db:
            row = db.execute("""SELECT o.outcome FROM trial_attempts AS a
                LEFT JOIN trial_outcomes AS o ON o.attempt_id=a.attempt_id
                WHERE a.attempt_id=?""", (attempt_id,)).fetchone()
        return None if row is None else (row["outcome"] or "open")
