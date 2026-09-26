"""Source-backed strategy intake records, before strategy code or market trials.

Records contain metadata and interpretation only. This module never retrieves
sources, executes third-party code, reads market data, or grants authority.
"""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping

from tidelab.domain import canonical_json


KINDS = {"paper", "repository", "tradingview_script", "other", "synthetic_example"}
STAGES = {"captured", "specified", "implementation_selected", "retired"}
RIGHTS = {"unknown", "documented", "blocked"}
_ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_ISSUE = re.compile(r"https://github\.com/Loothore907/tidelab/issues/[1-9][0-9]*\Z")
_TRANSITIONS = {
    "captured": {"captured", "specified", "retired"},
    "specified": {"specified", "implementation_selected", "retired"},
    "implementation_selected": {"specified", "retired"},
    "retired": set(),
}


def _fields(value: Any, expected: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{name} requires exactly {', '.join(sorted(expected))}")
    return value


def _text(value: Any, name: str, *, limit: int = 500, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be nonempty text within {limit} characters")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{name} contains control characters")


def _texts(value: Any, name: str, *, limit: int = 500) -> None:
    if (not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() or len(item) > limit
            or any(ord(character) < 32 for character in item)
            for item in value) or len(value) != len(set(value))):
        raise ValueError(f"{name} must contain distinct nonempty strings")


def _utc(value: Any) -> None:
    _text(value, "source.accessed_utc", limit=35)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("source.accessed_utc must be an ISO UTC timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError("source.accessed_utc must be UTC")


def validate_record(record: Any) -> dict[str, Any]:
    """Validate one strict metadata record without calling any outside service."""
    item = _fields(record, {"schema_version", "candidate_id", "version", "stage",
                            "source", "claim", "interpretation", "rights", "decision"},
                   "intake record")
    if type(item["schema_version"]) is not int or item["schema_version"] != 1 or type(item["version"]) is not int or item["version"] < 1:
        raise ValueError("unsupported schema or candidate version")
    if not isinstance(item["candidate_id"], str) or not _ID.fullmatch(item["candidate_id"]):
        raise ValueError("candidate_id must be a lowercase portable slug")
    if not isinstance(item["stage"], str) or item["stage"] not in STAGES:
        raise ValueError("unknown intake stage")

    source = _fields(item["source"], {"kind", "title", "authors", "locator", "revision",
                                      "content_sha256", "accessed_utc"}, "source")
    if not isinstance(source["kind"], str) or source["kind"] not in KINDS:
        raise ValueError("unknown source kind")
    for name in ("title", "locator", "revision"):
        _text(source[name], f"source.{name}")
    _texts(source["authors"], "source.authors")
    if not source["authors"]:
        raise ValueError("source.authors cannot be empty")
    if source["kind"] == "synthetic_example":
        if not source["locator"].startswith("urn:tidelab:synthetic:"):
            raise ValueError("synthetic example must use its TideLab URN")
    elif not source["locator"].startswith("https://"):
        raise ValueError("external source locator must use HTTPS")
    if source["content_sha256"] is not None and (
            not isinstance(source["content_sha256"], str)
            or _DIGEST.fullmatch(source["content_sha256"]) is None):
        raise ValueError("source.content_sha256 must be a lowercase SHA-256")
    _utc(source["accessed_utc"])

    claim = _fields(item["claim"], {"attributed_summary", "economic_rationale"}, "claim")
    _text(claim["attributed_summary"], "claim.attributed_summary", limit=1000)
    _text(claim["economic_rationale"], "claim.economic_rationale", limit=1000,
          nullable=True)

    interpretation = _fields(item["interpretation"],
                             {"product_scope", "timeframe", "required_data",
                              "required_capabilities", "entry", "exit", "sizing",
                              "timing", "open_questions"}, "interpretation")
    for name in ("product_scope", "timeframe", "entry", "exit", "sizing", "timing"):
        _text(interpretation[name], f"interpretation.{name}", limit=2000, nullable=True)
    for name in ("required_data", "required_capabilities", "open_questions"):
        _texts(interpretation[name], f"interpretation.{name}", limit=1000)

    rights = _fields(item["rights"], {"implementation_use", "redistribution",
                                      "evidence_reference"}, "rights")
    if (not isinstance(rights["implementation_use"], str)
            or not isinstance(rights["redistribution"], str)
            or rights["implementation_use"] not in RIGHTS
            or rights["redistribution"] not in RIGHTS):
        raise ValueError("unknown rights status")
    _text(rights["evidence_reference"], "rights.evidence_reference", nullable=True)
    if (rights["implementation_use"] == "documented" or rights["redistribution"] == "documented") and not rights["evidence_reference"]:
        raise ValueError("documented rights require an evidence reference")

    decision = _fields(item["decision"], {"issue_url", "authority_reference",
                                          "authorized_scope", "retirement_reason"}, "decision")
    for name in decision:
        _text(decision[name], f"decision.{name}", limit=1000, nullable=True)
    if decision["issue_url"] is not None and _ISSUE.fullmatch(decision["issue_url"]) is None:
        raise ValueError("decision.issue_url must identify a TideLab issue")

    if item["stage"] in {"specified", "implementation_selected"}:
        required = ("product_scope", "timeframe", "entry", "exit", "sizing", "timing")
        if (any(interpretation[name] is None for name in required)
                or not interpretation["required_data"] or not interpretation["required_capabilities"]
                or interpretation["open_questions"] or claim["economic_rationale"] is None
                or source["revision"] == "unverified"):
            raise ValueError("specified candidate has missing or ambiguous rules")
        if source["kind"] == "repository" and re.fullmatch(r"[0-9a-f]{40}", source["revision"]) is None:
            raise ValueError("repository source must pin a full commit SHA")
        if source["kind"] == "tradingview_script" and source["content_sha256"] is None:
            raise ValueError("TradingView source needs a content hash before specification")
        if (source["kind"] == "tradingview_script"
                and source["revision"] != f"sha256:{source['content_sha256']}"):
            raise ValueError("TradingView source revision must equal its content hash")
    if item["stage"] == "implementation_selected":
        if (rights["implementation_use"] != "documented" or decision["issue_url"] is None
                or decision["authority_reference"] is None
                or decision["authorized_scope"] is None):
            raise ValueError("implementation selection lacks rights or exact authority")
    elif decision["authority_reference"] is not None or decision["authorized_scope"] is not None:
        raise ValueError("only implementation_selected can carry implementation authority")
    if item["stage"] == "retired":
        if decision["retirement_reason"] is None:
            raise ValueError("retired candidate requires a reason")
    elif decision["retirement_reason"] is not None:
        raise ValueError("retirement reason requires retired stage")
    return dict(item)


def load_record(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if target.stat().st_size > 64 * 1024:
        raise ValueError("intake record is too large; do not embed source content")
    def unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return validate_record(json.loads(target.read_text(encoding="utf-8"),
                                      object_pairs_hook=unique_keys))


def record_digest(record: Mapping[str, Any]) -> str:
    return sha256(canonical_json(record).encode("utf-8")).hexdigest()


class IntakeRegistry:
    """Append-only local metadata registry. It does not verify cited authority."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = FULL")
            db.execute("""CREATE TABLE IF NOT EXISTS intake_versions (
                candidate_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                stage TEXT NOT NULL,
                digest TEXT NOT NULL,
                body_json TEXT NOT NULL,
                registered_utc TEXT NOT NULL,
                PRIMARY KEY (candidate_id, version)
            )""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS intake_no_update
                BEFORE UPDATE ON intake_versions
                BEGIN SELECT RAISE(ABORT, 'immutable intake record'); END""")
            db.execute("""CREATE TRIGGER IF NOT EXISTS intake_no_delete
                BEFORE DELETE ON intake_versions
                BEGIN SELECT RAISE(ABORT, 'immutable intake record'); END""")

    def latest(self, candidate_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as db:
            row = db.execute("""SELECT body_json FROM intake_versions
                WHERE candidate_id=? ORDER BY version DESC LIMIT 1""",
                (candidate_id,)).fetchone()
        return None if row is None else json.loads(row["body_json"])

    def list_latest(self) -> list[dict[str, Any]]:
        with closing(self._connect()) as db:
            rows = db.execute("""SELECT a.body_json FROM intake_versions AS a
                WHERE a.version=(SELECT MAX(b.version) FROM intake_versions AS b
                                 WHERE b.candidate_id=a.candidate_id)
                ORDER BY a.candidate_id""").fetchall()
        return [{"candidate_id": item["candidate_id"], "version": item["version"],
                 "stage": item["stage"], "source_kind": item["source"]["kind"],
                 "source_title": item["source"]["title"]}
                for item in (json.loads(row["body_json"]) for row in rows)]

    def register(self, record: Mapping[str, Any]) -> bool:
        checked = validate_record(dict(record))
        if (checked["source"]["kind"] == "tradingview_script"
                and checked["stage"] in {"specified", "implementation_selected"}):
            from tidelab.pine_source import verify_pine
            verify_pine(checked, self.path.parent / "pine_sources")
        digest = record_digest(checked)
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                rows = db.execute("""SELECT version, stage, digest, body_json
                    FROM intake_versions WHERE candidate_id=? ORDER BY version DESC LIMIT 1""",
                    (checked["candidate_id"],)).fetchall()
                previous = rows[0] if rows else None
                if previous is not None and checked["version"] == previous["version"]:
                    if digest != previous["digest"]:
                        raise ValueError("registered candidate version cannot change")
                    db.commit()
                    return False
                if checked["version"] != (1 if previous is None else previous["version"] + 1):
                    raise ValueError("candidate versions must be consecutive")
                if previous is None:
                    if checked["stage"] not in {"captured", "specified"}:
                        raise ValueError("first candidate version must be captured or specified")
                else:
                    prior = json.loads(previous["body_json"])
                    if checked["stage"] not in _TRANSITIONS[previous["stage"]]:
                        raise ValueError("invalid intake stage transition")
                    if (checked["source"]["kind"], checked["source"]["locator"]) != (
                            prior["source"]["kind"], prior["source"]["locator"]):
                        raise ValueError("a different source requires a new candidate ID")
                    if checked["stage"] == "implementation_selected" and any(
                            checked[name] != prior[name] for name in ("source", "claim", "interpretation")):
                        raise ValueError("selection cannot silently change the specified candidate")
                db.execute("""INSERT INTO intake_versions VALUES (?, ?, ?, ?, ?, ?)""",
                           (checked["candidate_id"], checked["version"], checked["stage"],
                            digest, canonical_json(checked), datetime.now(timezone.utc).isoformat()))
                db.commit()
                return True
            except BaseException:
                db.rollback()
                raise

    def check_implementation_record(self, record: Mapping[str, Any]) -> str:
        checked = validate_record(dict(record))
        if checked["stage"] != "implementation_selected":
            raise ValueError("candidate has not reached implementation_selected")
        if checked["source"]["kind"] == "tradingview_script":
            from tidelab.pine_source import verify_pine
            verify_pine(checked, self.path.parent / "pine_sources")
        latest = self.latest(checked["candidate_id"])
        if latest is None or record_digest(latest) != record_digest(checked):
            raise ValueError("selected record is not the latest registered version")
        return record_digest(checked)
