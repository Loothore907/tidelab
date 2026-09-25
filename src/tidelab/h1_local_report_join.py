"""Test-owned H1 intent/report reconciliation; no external broker or order API."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

from tidelab.h1_paper_bridge import H1SyntheticPaperBridge
from tidelab.paper_intent import PaperIntent, PaperIntentStore, PaperProductRules


def _amount(value: object) -> Decimal:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("invalid report decimal") from exc
    if not number.is_finite():
        raise ValueError("invalid report decimal")
    return number


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True,
        separators=(",", ":"), default=str).encode()).hexdigest()


_SNAPSHOT_FIELDS = {"Version", "Source", "ObservedAtUtc", "ConsistencyToken",
                    "AccountRevision", "OrdersRevision", "ExecutionsRevision",
                    "ClientId", "BrokerId", "OrderStatus", "ReportRevision",
                    "ReportReference", "Cash", "Holding", "OpenBrokerIds",
                    "OrderFinality"}


def _stable_snapshot_pair(before_json: str | None, after_json: str | None,
                          report: dict, next_open: datetime) -> str:
    """Check a synthetic whole-account/order cursor; external proof is separate."""
    if before_json is None or after_json is None:
        raise RuntimeError("H1 handoff requires two broker snapshot reads")
    before = json.loads(before_json, parse_float=Decimal)
    after = json.loads(after_json, parse_float=Decimal)
    if before != after:
        raise RuntimeError("broker snapshot changed; hold")
    if not isinstance(before, dict) or set(before) != _SNAPSHOT_FIELDS:
        raise ValueError("broker snapshot fields are incomplete")
    token = before["ConsistencyToken"]
    try:
        observed = datetime.fromisoformat(before["ObservedAtUtc"].replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("broker snapshot observation time is invalid") from exc
    if (type(before["Version"]) is not int or before["Version"] != 1 or
            before["Source"] != "synthetic-local-broker" or
            not isinstance(token, str) or not token.strip() or
            any(before[field] != token for field in
                ("AccountRevision", "OrdersRevision", "ExecutionsRevision")) or
            observed.utcoffset() != timedelta(0) or observed != next_open or
            before["ClientId"] != report["ClientId"] or
            before["BrokerId"] != report["BrokerId"] or
            before["OrderStatus"] != report["BrokerStatus"] or
            type(before["ReportRevision"]) is not int or
            before["ReportRevision"] != report["Revision"] or
            before["ReportReference"] != "h1-report-v1:" + _digest(report) or
            _amount(before["Cash"]) != _amount(report["Cash"]) or
            _amount(before["Holding"]) != _amount(report["Holding"]) or
            before["OpenBrokerIds"] != [] or
            before["OrderFinality"] != "terminal_at_cursor"):
        raise ValueError("broker snapshot lacks consistent terminal account/order evidence")
    return _digest(before)


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
            db.execute("""CREATE TABLE IF NOT EXISTS h1_handoff_snapshots (
                client_id TEXT PRIMARY KEY REFERENCES paper_intents(client_id),
                evidence_hash TEXT NOT NULL)""")

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
        proposal_hash = _digest(proposal)
        report_hash = _digest(report)
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

    def handoff(self, proposal_json: str, report_json: str,
                next_proposal_json: str, rules: PaperProductRules, *,
                snapshot_before_json: str | None = None,
                snapshot_after_json: str | None = None) -> str:
        """Atomically retire a verified terminal fixture and prepare its next H1 intent.

        This is a single-writer synthetic report protocol. It does not establish
        finality of a real broker report or permit account-derived live orders.
        """
        # Reconcile first, so all execution and account checks apply before the
        # transaction below compares the exact persisted terminal report hash.
        self.reconcile(proposal_json, report_json)
        proposal = json.loads(proposal_json, parse_float=Decimal)
        report = json.loads(report_json, parse_float=Decimal)
        next_proposal = json.loads(next_proposal_json, parse_float=Decimal)
        if report["BrokerStatus"] not in ("Filled", "Canceled"):
            raise RuntimeError("H1 handoff requires a terminal report")
        report_hash = _digest(report)
        source_revision = "h1-report-v1:" + report_hash
        prior_open = datetime.fromisoformat(
            proposal["ObservedOpenUtc"].replace("Z", "+00:00"))
        next_open = datetime.fromisoformat(
            next_proposal["ObservedOpenUtc"].replace("Z", "+00:00"))
        cash, holding = _amount(report["Cash"]), _amount(report["Holding"])
        next_price = _amount(next_proposal["LimitPrice"])
        if (next_open != prior_open + timedelta(hours=1) or
                next_proposal["InstrumentId"] != proposal["InstrumentId"] or
                next_proposal["ExperimentId"] != proposal["ExperimentId"] or
                next_proposal["SourceRevision"] != source_revision or
                _amount(next_proposal["Cash"]) != cash or
                _amount(next_proposal["Units"]) != holding or
                _amount(next_proposal["Equity"]) != cash + holding * next_price):
            raise ValueError("next H1 proposal lacks exact report/account handoff")
        bridge = H1SyntheticPaperBridge(self.intents.path)
        intent, opening, digest = bridge.validate(next_proposal_json,
            observed_at=next_open, source_revision=source_revision, rules=rules)
        evidence_hash = _stable_snapshot_pair(snapshot_before_json,
            snapshot_after_json, report, next_open)
        prior_id = proposal["ClientId"]
        with closing(self.intents._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM paper_authority_holds").fetchone():
                    raise RuntimeError("paper authority has a durable evidence hold")
                old = db.execute("SELECT * FROM h1_local_orders WHERE client_id=?",
                                 (prior_id,)).fetchone()
                previous = db.execute("SELECT * FROM paper_intents WHERE client_id=?",
                                      (prior_id,)).fetchone()
                if (old is None or old["report_hash"] != report_hash or
                        old["revision"] != report["Revision"] or
                        old["status"] != report["BrokerStatus"] or
                        previous is None or previous["state"] != "submission_unknown"):
                    raise RuntimeError("terminal H1 report changed during handoff")
                resolved = db.execute("SELECT * FROM paper_intent_resolutions WHERE client_id=?",
                                      (prior_id,)).fetchone()
                existing = db.execute("SELECT * FROM paper_intents WHERE client_id=?",
                                      (intent.client_id,)).fetchone()
                if resolved is not None:
                    saved = db.execute("SELECT * FROM h1_paper_proposals WHERE client_id=?",
                                       (intent.client_id,)).fetchone()
                    evidence = db.execute("SELECT evidence_hash FROM h1_handoff_snapshots WHERE client_id=?",
                                          (prior_id,)).fetchone()
                    if (existing is None or saved is None or
                            evidence is None or evidence["evidence_hash"] != evidence_hash or
                            resolved["final_report_revision"] != old["revision"] or
                            resolved["source_revision"] != previous["source_revision"] or
                            saved["proposal_hash"] != digest or
                            saved["source_revision"] != source_revision):
                        raise RuntimeError("H1 handoff replay changed")
                    db.commit()
                    return f"handoff replay client={intent.client_id}"
                if existing is not None or db.execute("""SELECT 1 FROM paper_intents AS i
                    LEFT JOIN paper_intent_resolutions AS r ON r.client_id=i.client_id
                    WHERE r.client_id IS NULL AND i.client_id<>? LIMIT 1""",
                    (prior_id,)).fetchone():
                    raise RuntimeError("another H1 intent prevents handoff")
                db.execute("INSERT INTO paper_intent_resolutions VALUES (?, ?, ?)",
                           (prior_id, previous["source_revision"], old["revision"]))
                db.execute("INSERT INTO h1_handoff_snapshots VALUES (?, ?)",
                           (prior_id, evidence_hash))
                db.execute("""INSERT INTO paper_intents
                    (client_id, instrument_id, side, quantity, limit_price,
                     source_revision, rules_identity, claim_guard, state)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'h1_snapshot', 'prepared')""",
                    (intent.client_id, intent.instrument_id, intent.side,
                     intent.quantity, intent.limit_price, intent.source_revision,
                     rules.identity))
                db.execute("INSERT INTO h1_paper_proposals VALUES (?, ?, ?, ?, ?)",
                           (intent.client_id, opening.isoformat(), source_revision,
                            rules.identity, digest))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return f"handoff terminal={prior_id} next={intent.client_id} quantity={intent.quantity}"

    def observe_handoff(self, next_client_id: str, report_json: str,
                        snapshot_before_json: str | None,
                        snapshot_after_json: str | None, *,
                        claim: tuple[PaperIntent, datetime, str, PaperProductRules] | None = None
                        ) -> str:
        """Recheck an invented source before claim; latch later changes durably.

        The caller must supply fresh complete source reads. This local protocol
        cannot make an external broker read atomic with SQLite or prevent a
        correction arriving after the read.
        """
        blocked = None
        with closing(self.intents._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                if db.execute("SELECT 1 FROM paper_authority_holds").fetchone():
                    raise RuntimeError("paper authority has a durable evidence hold")
                next_intent = db.execute("SELECT * FROM paper_intents WHERE client_id=?",
                                         (next_client_id,)).fetchone()
                saved = db.execute("SELECT * FROM h1_paper_proposals WHERE client_id=?",
                                   (next_client_id,)).fetchone()
                if (next_intent is None or saved is None or
                        next_intent["claim_guard"] != "h1_snapshot" or
                        saved["source_revision"] != next_intent["source_revision"]):
                    raise RuntimeError("H1 successor lacks guarded handoff")
                parent = db.execute("""SELECT o.report_hash, s.evidence_hash
                    FROM h1_local_orders AS o
                    JOIN paper_intent_resolutions AS r ON r.client_id=o.client_id
                    JOIN h1_handoff_snapshots AS s ON s.client_id=o.client_id
                    WHERE 'h1-report-v1:' || o.report_hash=?
                    AND r.final_report_revision=o.revision""",
                    (next_intent["source_revision"],)).fetchone()
                if parent is None:
                    raise RuntimeError("H1 successor lacks resolved parent report")
                try:
                    report = json.loads(report_json, parse_float=Decimal)
                except (TypeError, ValueError):
                    report = None
                candidate_hash = (_digest(report) if isinstance(report, dict)
                                  else hashlib.sha256(str(report_json).encode()).hexdigest())
                if candidate_hash != parent["report_hash"]:
                    blocked = "late H1 report correction; hold"
                    reason = "late_h1_report_change"
                    evidence_hash = candidate_hash
                else:
                    opening = datetime.fromisoformat(saved["opening_utc"])
                    evidence_hash = _stable_snapshot_pair(snapshot_before_json,
                        snapshot_after_json, report, opening)
                    if evidence_hash != parent["evidence_hash"]:
                        blocked = "late H1 snapshot change; hold"
                        reason = "late_h1_snapshot_change"
                if blocked is not None:
                    db.execute("INSERT INTO paper_authority_holds VALUES (1, ?, ?, ?)",
                               (next_client_id, reason, evidence_hash))
                elif claim is not None:
                    intent, opening, digest, rules = claim
                    if (intent.client_id != next_client_id or
                            saved["opening_utc"] != opening.isoformat() or
                            saved["proposal_hash"] != digest or
                            saved["rules_identity"] != rules.identity or
                            next_intent["source_revision"] != intent.source_revision or
                            next_intent["rules_identity"] != rules.identity):
                        raise RuntimeError("H1 successor claim identity changed")
                    if next_intent["state"] != "prepared":
                        db.commit()
                        return "already claimed"
                    rules.validate(PaperIntent(next_intent["client_id"],
                        next_intent["instrument_id"], next_intent["side"],
                        next_intent["quantity"], next_intent["limit_price"],
                        next_intent["source_revision"]))
                    db.execute("""UPDATE paper_intents SET state='submission_unknown'
                        WHERE client_id=? AND state='prepared'""", (next_client_id,))
                db.commit()
            except BaseException:
                db.rollback()
                raise
        if blocked is not None:
            raise RuntimeError(blocked)
        return "claimed" if claim is not None else "unchanged"

    def claim_after_handoff(self, next_proposal_json: str, report_json: str,
                            snapshot_before_json: str | None,
                            snapshot_after_json: str | None,
                            rules: PaperProductRules) -> str:
        proposal = json.loads(next_proposal_json, parse_float=Decimal)
        opening = datetime.fromisoformat(
            proposal["ObservedOpenUtc"].replace("Z", "+00:00"))
        bridge = H1SyntheticPaperBridge(self.intents.path)
        intent, opening, digest = bridge.validate(next_proposal_json,
            observed_at=opening, source_revision=proposal["SourceRevision"], rules=rules)
        return self.observe_handoff(intent.client_id, report_json,
            snapshot_before_json, snapshot_after_json,
            claim=(intent, opening, digest, rules))
