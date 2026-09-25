"""Test-owned H1 intent/report reconciliation; no external broker or order API."""

from __future__ import annotations

from contextlib import closing
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

from tidelab.paper_intent import PaperIntentStore


def _amount(value: object) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("invalid report decimal") from exc
    if not number.is_finite():
        raise ValueError("invalid report decimal")
    return number


class H1LocalReportJoin:
    """Join a variable H1 proposal to complete, revisioned local LEAN test reports.

    Every report contains all executions to date. Corrections to a prior
    execution hold; they need an explicit reversal/replacement protocol before
    the paper authority can resolve. The report is a synthetic single-writer
    fixture, not evidence about any external broker's finality or account.
    """

    def __init__(self, database: str | Path):
        self.intents = PaperIntentStore(database)

    def initialize(self) -> None:
        self.intents.initialize()
        with closing(self.intents._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS h1_local_orders (
                client_id TEXT PRIMARY KEY REFERENCES paper_intents(client_id),
                lean_order_id INTEGER NOT NULL, broker_id TEXT NOT NULL UNIQUE,
                revision INTEGER NOT NULL, status TEXT NOT NULL,
                report_hash TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS h1_local_executions (
                client_id TEXT NOT NULL REFERENCES paper_intents(client_id),
                execution_id TEXT NOT NULL, quantity TEXT NOT NULL,
                price TEXT NOT NULL, fee TEXT NOT NULL,
                PRIMARY KEY(client_id, execution_id))""")

    def reconcile(self, proposal_json: str, report_json: str) -> str:
        proposal = json.loads(proposal_json, parse_float=Decimal)
        report = json.loads(report_json, parse_float=Decimal)
        if not isinstance(proposal, dict) or not isinstance(report, dict):
            raise ValueError("proposal and report must be objects")
        client_id = proposal.get("ClientId")
        revision = report.get("Revision")
        status = report.get("BrokerStatus")
        lean_id = report.get("LeanOrderId")
        broker_id = report.get("BrokerId")
        if (not isinstance(client_id, str) or not client_id.startswith("H1V1-") or
                type(report.get("Version")) is not int or report["Version"] != 1 or
                type(revision) is not int or revision < 1 or
                status not in ("Submitted", "PartiallyFilled", "Filled", "Canceled") or
                type(lean_id) is not int or lean_id <= 0 or
                not isinstance(broker_id, str) or not broker_id or
                report.get("ClientId") != client_id or
                report.get("InstrumentId") != proposal.get("InstrumentId") or
                report.get("SourceRevision") != proposal.get("SourceRevision")):
            raise ValueError("H1 report identity or state mismatch")
        entries = report.get("Executions")
        if not isinstance(entries, list):
            raise ValueError("report requires complete executions")
        side = proposal.get("Side")
        if side not in ("buy", "sell"):
            raise ValueError("invalid H1 side")
        target = _amount(proposal.get("Quantity"))
        cash = _amount(proposal.get("Cash"))
        holding = _amount(proposal.get("Units"))
        if target <= 0 or cash < 0 or holding < 0:
            raise ValueError("invalid opening account")
        if (_amount(report.get("Quantity")) !=
                (target if side == "buy" else -target) or
                _amount(report.get("LimitPrice")) !=
                _amount(proposal.get("LimitPrice"))):
            raise ValueError("H1 report order terms mismatch")
        normalized = []
        seen = set()
        filled = Decimal(0)
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("invalid execution")
            execution_id = entry.get("ExecutionId")
            quantity = _amount(entry.get("Quantity"))
            price = _amount(entry.get("Price"))
            fee = _amount(entry.get("Fee"))
            if (not isinstance(execution_id, str) or not execution_id or
                    execution_id in seen or quantity <= 0 or price <= 0 or fee < 0):
                raise ValueError("invalid or repeated execution")
            seen.add(execution_id)
            normalized.append((client_id, execution_id, str(quantity), str(price), str(fee)))
            filled += quantity
            cash += (-quantity * price - fee) if side == "buy" else (quantity * price - fee)
            holding += quantity if side == "buy" else -quantity
        if (filled > target or cash < 0 or holding < 0 or
                (status == "Submitted" and filled != 0) or
                (status == "PartiallyFilled" and not (0 < filled < target)) or
                (status == "Filled" and filled != target) or
                (status == "Canceled" and filled == target) or
                cash != _amount(report.get("Cash")) or
                holding != _amount(report.get("Holding"))):
            raise ValueError("H1 report fill or account mismatch")
        proposal_hash = hashlib.sha256(json.dumps(proposal, sort_keys=True,
            separators=(",", ":"), default=str).encode()).hexdigest()
        report_hash = hashlib.sha256(json.dumps(report, sort_keys=True,
            separators=(",", ":"), default=str).encode()).hexdigest()
        with closing(self.intents._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                intent = db.execute("SELECT * FROM paper_intents WHERE client_id=?",
                                    (client_id,)).fetchone()
                saved = db.execute("SELECT * FROM h1_paper_proposals WHERE client_id=?",
                                   (client_id,)).fetchone()
                if (intent is None or intent["state"] != "submission_unknown" or
                        saved is None or saved["proposal_hash"] != proposal_hash or
                        (intent["instrument_id"], intent["side"],
                         Decimal(intent["quantity"]), Decimal(intent["limit_price"]),
                         intent["source_revision"]) !=
                        (proposal.get("InstrumentId"), side, target,
                         _amount(proposal.get("LimitPrice")), proposal.get("SourceRevision"))):
                    raise RuntimeError("H1 report lacks matching claimed proposal")
                old = db.execute("SELECT * FROM h1_local_orders WHERE client_id=?",
                                 (client_id,)).fetchone()
                if old is None and revision != 1:
                    raise RuntimeError("first H1 report revision must be 1")
                if old is not None and (old["lean_order_id"] != lean_id or
                    old["broker_id"] != broker_id or revision < old["revision"] or
                    revision > old["revision"] + 1 or
                    (revision == old["revision"] and report_hash != old["report_hash"])):
                    raise RuntimeError("H1 report identity, revision or content changed")
                if db.execute("SELECT 1 FROM paper_intent_resolutions WHERE client_id=?",
                              (client_id,)).fetchone() and (old is None or
                              revision != old["revision"]):
                    raise RuntimeError("resolved H1 report changed")
                if old is not None and old["status"] in ("Filled", "Canceled") and revision != old["revision"]:
                    raise RuntimeError("closed H1 report changed")
                prior = {row["execution_id"]: (row["quantity"], row["price"], row["fee"])
                         for row in db.execute("SELECT * FROM h1_local_executions WHERE client_id=?",
                                               (client_id,))}
                incoming = {e[1]: e[2:] for e in normalized}
                if any(incoming.get(key) != value for key, value in prior.items()):
                    raise RuntimeError("H1 execution removed or corrected; hold")
                for entry in normalized:
                    db.execute("INSERT OR IGNORE INTO h1_local_executions VALUES (?, ?, ?, ?, ?)",
                               entry)
                if old is None:
                    db.execute("INSERT INTO h1_local_orders VALUES (?, ?, ?, ?, ?, ?)",
                               (client_id, lean_id, broker_id, revision, status, report_hash))
                else:
                    db.execute("""UPDATE h1_local_orders SET revision=?, status=?, report_hash=?
                        WHERE client_id=?""", (revision, status, report_hash, client_id))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return f"hold revision={revision} status={status} executions={len(entries)}"
