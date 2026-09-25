"""Local append-only trial attempts around a portable experiment identity."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
from typing import Mapping

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
            db.execute("PRAGMA journal_mode = WAL")
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
            for table in ("trial_attempts", "trial_outcomes"):
                db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_update
                    BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable trial record'); END""")
                db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_no_delete
                    BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable trial record'); END""")

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
