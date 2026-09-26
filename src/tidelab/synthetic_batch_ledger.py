"""Append-only local accounting for synthetic source and package batch attempts.

This ledger is distinct from the real-research TrialRegistry. It grants no
market-data use, strategy selection, or execution authority.
"""

from __future__ import annotations

from contextlib import closing
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import re
import sqlite3
from uuid import uuid4

from tidelab.domain import canonical_json
from tidelab.strategy_batch import (SYNTHETIC_COST, SYNTHETIC_ENGINE,
                                    parse_json_bytes)


_SHA = re.compile(r"[0-9a-f]{64}\Z")
_KINDS = {"synthetic_strategy_batch": "package_count",
          "synthetic_pine_subset_batch": "source_count"}
_SCOPES = {"synthetic_strategy_batch": "synthetic_contract_only_no_market_claim",
           "synthetic_pine_subset_batch":
           "synthetic_contract_only_no_tradingview_or_market_claim"}
_MAX_ARTIFACT = 64 * 1024 * 1024


def cost_sha256() -> str:
    return sha256(canonical_json(SYNTHETIC_COST).encode("utf-8")).hexdigest()


def _stages(kind: str, outcome: dict) -> tuple[str, str, str]:
    status = outcome["status"]
    if status == "synthetic_contract_tested":
        if kind == "synthetic_pine_subset_batch" and outcome.get("conformance") != "matched":
            raise ValueError("Pine conformance status missing")
        return "accepted", "matched" if kind == "synthetic_pine_subset_batch" else "not_applicable", "tested"
    if status == "unsupported_pine" and kind == "synthetic_pine_subset_batch":
        return "unsupported", "not_run", "not_run"
    if status == "conformance_failed" and kind == "synthetic_pine_subset_batch":
        return "accepted", "failed", "not_run"
    if status == "unsupported_package" and kind == "synthetic_strategy_batch":
        return "unsupported", "not_applicable", "not_run"
    if status == "rejected_before_test":
        return "rejected", "not_run" if kind == "synthetic_pine_subset_batch" else "not_applicable", "not_run"
    if status == "needs_source_parser" and kind == "synthetic_strategy_batch":
        return "missing", "not_applicable", "not_run"
    raise ValueError("unknown synthetic batch outcome")


class SyntheticBatchLedger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA synchronous=FULL")
        return db

    def initialize(self) -> None:
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY, output_key TEXT NOT NULL UNIQUE,
                kind TEXT NOT NULL, fixture_sha256 TEXT NOT NULL,
                cost_sha256 TEXT NOT NULL, started_utc TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS variants (
                run_id TEXT NOT NULL REFERENCES runs(run_id), input_index INTEGER NOT NULL,
                input_sha256 TEXT NOT NULL, input_file TEXT NOT NULL,
                PRIMARY KEY(run_id, input_index)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS completions (
                run_id TEXT PRIMARY KEY REFERENCES runs(run_id),
                artifact_sha256 TEXT NOT NULL, completed_utc TEXT NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS outcomes (
                run_id TEXT NOT NULL REFERENCES runs(run_id), ordinal INTEGER NOT NULL,
                input_index INTEGER, status TEXT NOT NULL, parse_status TEXT NOT NULL,
                conformance_status TEXT NOT NULL, test_status TEXT NOT NULL,
                outcome_json TEXT NOT NULL, PRIMARY KEY(run_id, ordinal)
            )""")
            for table in ("runs", "variants", "completions", "outcomes"):
                db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_immutable_update
                    BEFORE UPDATE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable synthetic attempt'); END""")
                db.execute(f"""CREATE TRIGGER IF NOT EXISTS {table}_immutable_delete
                    BEFORE DELETE ON {table} BEGIN SELECT RAISE(ABORT, 'immutable synthetic attempt'); END""")

    def begin(self, output_key: str, kind: str, fixture_sha: str,
              inputs: list[tuple[str, str]]) -> str:
        """Durably register all numbered variants before parsing or testing."""
        if (not output_key or output_key.startswith("/") or "\\" in output_key
                or any(part in ("", ".", "..") for part in output_key.split("/"))):
            raise ValueError("output key must be relative to private data root")
        if kind not in _KINDS or not _SHA.fullmatch(fixture_sha):
            raise ValueError("invalid synthetic run identity")
        if not 1 <= len(inputs) <= 10000 or any(
                not _SHA.fullmatch(digest) or not name or "/" in name or "\\" in name
                for digest, name in inputs):
            raise ValueError("invalid numbered synthetic inputs")
        run_id = uuid4().hex
        started = datetime.now(timezone.utc).isoformat()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)",
                           (run_id, output_key, kind, fixture_sha, cost_sha256(), started))
                db.executemany("INSERT INTO variants VALUES (?,?,?,?)",
                               ((run_id, index, digest, name)
                                for index, (digest, name) in enumerate(inputs)))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return run_id

    def complete(self, output_key: str, raw: bytes) -> dict[str, object]:
        """Atomically append all outcomes; an identical retry repairs a crash gap."""
        if len(raw) > _MAX_ARTIFACT:
            raise ValueError("synthetic artifact exceeds size limit")
        body = parse_json_bytes(raw, max_bytes=_MAX_ARTIFACT)
        digest = sha256(raw).hexdigest()
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                run = db.execute("SELECT * FROM runs WHERE output_key=?", (output_key,)).fetchone()
                if run is None:
                    raise ValueError("unregistered synthetic output")
                prior = db.execute("SELECT artifact_sha256 FROM completions WHERE run_id=?",
                                   (run["run_id"],)).fetchone()
                if prior is not None:
                    if prior[0] != digest:
                        raise ValueError("completed artifact identity changed")
                    db.commit()
                    return {"run_id": run["run_id"], "artifact_sha256": digest,
                            "new_completion": False}
                if (body.get("schema_version") != 1 or body.get("kind") != run["kind"]
                        or body.get("scope") != _SCOPES[run["kind"]]
                        or body.get("engine") != SYNTHETIC_ENGINE
                        or not isinstance(body.get("cost"), dict)
                        or body.get("fixture_sha256") != run["fixture_sha256"]
                        or run["cost_sha256"] != sha256(
                            canonical_json(body["cost"]).encode("utf-8")).hexdigest()):
                    raise ValueError("synthetic artifact identity or cost differs")
                expected_count = db.execute("SELECT COUNT(*) FROM variants WHERE run_id=?",
                                            (run["run_id"],)).fetchone()[0]
                if body.get(_KINDS[run["kind"]]) != expected_count:
                    raise ValueError("synthetic input denominator differs")
                outcomes = body.get("outcomes")
                if not isinstance(outcomes, list):
                    raise ValueError("synthetic outcomes missing")
                numbered = {}
                rows = []
                for ordinal, item in enumerate(outcomes):
                    if not isinstance(item, dict) or not isinstance(item.get("status"), str):
                        raise ValueError("invalid synthetic outcome")
                    stages = _stages(run["kind"], item)
                    index = item.get("index")
                    if index is None:
                        if item["status"] != "needs_source_parser":
                            raise ValueError("numbered variant outcome missing index")
                    elif type(index) is not int or not 0 <= index < expected_count or index in numbered:
                        raise ValueError("invalid or duplicate synthetic input index")
                    else:
                        numbered[index] = item
                    rows.append((run["run_id"], ordinal, index, item["status"], *stages,
                                 canonical_json(item)))
                if set(numbered) != set(range(expected_count)):
                    raise ValueError("synthetic input outcome denominator incomplete")
                if body.get("summary") != dict(sorted(Counter(
                        item["status"] for item in outcomes).items())):
                    raise ValueError("synthetic outcome summary differs")
                variants = db.execute("SELECT * FROM variants WHERE run_id=? ORDER BY input_index",
                                      (run["run_id"],)).fetchall()
                for variant in variants:
                    item = numbered[variant["input_index"]]
                    if run["kind"] == "synthetic_pine_subset_batch":
                        if (item.get("source_sha256") != variant["input_sha256"]
                                or item.get("file") != variant["input_file"]):
                            raise ValueError("Pine source outcome differs from planned input")
                    elif item.get("file_sha256") != variant["input_sha256"]:
                        raise ValueError("package file outcome differs from planned input")
                db.executemany("INSERT INTO outcomes VALUES (?,?,?,?,?,?,?,?)", rows)
                db.execute("INSERT INTO completions VALUES (?,?,?)",
                           (run["run_id"], digest, datetime.now(timezone.utc).isoformat()))
                db.commit()
                return {"run_id": run["run_id"], "artifact_sha256": digest,
                        "new_completion": True}
            except BaseException:
                db.rollback()
                raise

    def summary(self) -> dict[str, object]:
        with closing(self._connect()) as db:
            runs = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            open_runs = db.execute("""SELECT COUNT(*) FROM runs r LEFT JOIN completions c
                ON c.run_id=r.run_id WHERE c.run_id IS NULL""").fetchone()[0]
            open_outputs = db.execute("""SELECT r.run_id, r.output_key, r.kind,
                r.started_utc, COUNT(v.input_index) AS variants FROM runs r
                LEFT JOIN completions c ON c.run_id=r.run_id
                LEFT JOIN variants v ON v.run_id=r.run_id WHERE c.run_id IS NULL
                GROUP BY r.run_id ORDER BY r.started_utc, r.run_id""").fetchall()
            rows = db.execute("SELECT status, COUNT(*) AS count FROM outcomes GROUP BY status").fetchall()
            variants = db.execute("SELECT COUNT(*) FROM variants").fetchone()[0]
            cohorts = db.execute("""SELECT kind, fixture_sha256, cost_sha256,
                COUNT(*) AS runs FROM runs GROUP BY kind, fixture_sha256, cost_sha256
                ORDER BY kind, fixture_sha256, cost_sha256""").fetchall()
        return {"runs": runs, "open_runs": open_runs, "variants": variants,
                "open_outputs": [dict(row) for row in open_outputs],
                "outcomes": {row["status"]: row["count"] for row in rows},
                "cohorts": [dict(row) for row in cohorts]}
