"""Test-only join between a durable TideLab intent and a local LEAN broker report.

The report file is the sole writer's authoritative order source in this probe.
Absence here says nothing about any external process, account, or brokerage.
"""

from __future__ import annotations

from contextlib import closing
from decimal import Decimal
import json
from pathlib import Path

from tidelab.paper_intent import PaperIntent, PaperIntentStore


CLIENT_ID = "TL001A-JOINED-CLIENT-1"
BROKER_ID = "TL001A-BROKER-ORDER-1"
EXECUTION_ID = "TL001A-JOINED-EXEC-1"
REVISION = "lean-report-1"


class LeanSyntheticPaperJoin:
    """One fixed invented LEAN fixture, with SQLite order and execution identity."""

    def __init__(self, database: str | Path, report: str | Path):
        self.intents = PaperIntentStore(database)
        self.report = Path(report)

    def initialize(self) -> None:
        self.intents.initialize()
        with closing(self.intents._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS lean_paper_order (
                client_id TEXT PRIMARY KEY REFERENCES paper_intents(client_id),
                lean_order_id INTEGER NOT NULL, broker_id TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL, report_revision INTEGER NOT NULL,
                cash TEXT NOT NULL, holding TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS lean_paper_execution_events (
                client_id TEXT NOT NULL REFERENCES paper_intents(client_id),
                report_revision INTEGER NOT NULL, event_kind TEXT NOT NULL,
                execution_id TEXT NOT NULL, quantity TEXT NOT NULL,
                price TEXT NOT NULL, fee TEXT NOT NULL,
                PRIMARY KEY(client_id, report_revision, event_kind))""")

    def prepare(self) -> None:
        self.intents.prepare(PaperIntent(
            CLIENT_ID, "synthetic:TL001ASYN", "buy", "1", "90", REVISION
        ))

    def claim(self) -> bool:
        """Persist the unknown state before the mock LEAN brokerage writes."""
        return self.intents.claim_once(CLIENT_ID, REVISION)

    def reconcile(self) -> str:
        """Import a complete local report, or rearm only on definitive local absence."""
        if self.report.with_suffix(self.report.suffix + ".next").exists():
            raise RuntimeError("torn broker report")
        if not self.report.exists():
            with closing(self.intents._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    row = db.execute("SELECT state FROM paper_intents WHERE client_id=?",
                                     (CLIENT_ID,)).fetchone()
                    if row is None:
                        raise RuntimeError("missing intent")
                    if db.execute("SELECT 1 FROM lean_paper_order WHERE client_id=?",
                                  (CLIENT_ID,)).fetchone():
                        raise RuntimeError("order report disappeared")
                    if row["state"] == "submission_unknown":
                        db.execute("UPDATE paper_intents SET state='prepared' WHERE client_id=?",
                                   (CLIENT_ID,))
                        result = "absent_rearmed"
                    else:
                        result = "prepared"
                    db.commit()
                    return result
                except BaseException:
                    db.rollback()
                    raise

        report = json.loads(self.report.read_text(encoding="utf-8"), parse_float=Decimal)
        self._validate(report)
        revision = report["Revision"]
        with closing(self.intents._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                intent = db.execute("SELECT * FROM paper_intents WHERE client_id=?",
                                    (CLIENT_ID,)).fetchone()
                if intent is None or intent["state"] != "submission_unknown":
                    raise RuntimeError("broker report lacks claimed intent")
                if (intent["instrument_id"], intent["side"], intent["quantity"],
                    intent["limit_price"], intent["source_revision"]) != (
                    "synthetic:TL001ASYN", "buy", "1", "90", REVISION):
                    raise RuntimeError("broker report conflicts with intent")
                existing = db.execute("SELECT * FROM lean_paper_order WHERE client_id=?",
                                      (CLIENT_ID,)).fetchone()
                if existing is None:
                    db.execute("""INSERT INTO lean_paper_order VALUES (?, ?, ?, ?, ?, ?, ?)""",
                               (CLIENT_ID, report["LeanOrderId"], BROKER_ID,
                                report["BrokerStatus"], revision,
                                str(report["Cash"]), str(report["Holding"])))
                else:
                    if (existing["lean_order_id"], existing["broker_id"]) != (
                        report["LeanOrderId"], BROKER_ID
                    ) or revision < existing["report_revision"] or revision > existing["report_revision"] + 1:
                        raise RuntimeError("broker order identity or revision conflict")
                    if revision == existing["report_revision"] and (
                        existing["status"], Decimal(existing["cash"]),
                        Decimal(existing["holding"])
                    ) != (report["BrokerStatus"], report["Cash"], report["Holding"]):
                        raise RuntimeError("broker report changed without revision")
                    db.execute("""UPDATE lean_paper_order SET status=?, report_revision=?,
                        cash=?, holding=? WHERE client_id=?""",
                        (report["BrokerStatus"], revision, str(report["Cash"]),
                         str(report["Holding"]), CLIENT_ID))
                if revision == 2:
                    self._event(db, 2, "fill", Decimal("0.4"), Decimal("89.91"), Decimal("0.035964"))
                elif revision == 3:
                    self._event(db, 3, "reverse", Decimal("-0.4"), Decimal("89.91"), Decimal("-0.035964"))
                    self._event(db, 3, "replacement", Decimal("0.4"), Decimal("89.92"), Decimal("0.035968"))
                events = db.execute("""SELECT quantity, price, fee FROM lean_paper_execution_events
                    WHERE client_id=? ORDER BY report_revision, CASE event_kind
                    WHEN 'reverse' THEN 0 ELSE 1 END""", (CLIENT_ID,)).fetchall()
                cash = Decimal("10000") - sum((Decimal(e["quantity"]) * Decimal(e["price"]) +
                    Decimal(e["fee"]) for e in events), Decimal(0))
                holding = sum((Decimal(e["quantity"]) for e in events), Decimal(0))
                if (cash, holding) != (report["Cash"], report["Holding"]):
                    raise RuntimeError("execution journal differs from broker account")
                db.commit()
                return f"present_hold revision={revision} events={len(events)} cash={cash} holding={holding}"
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _event(db, revision: int, kind: str, quantity: Decimal, price: Decimal, fee: Decimal) -> None:
        values = (CLIENT_ID, revision, kind, EXECUTION_ID, str(quantity), str(price), str(fee))
        old = db.execute("""SELECT client_id, report_revision, event_kind, execution_id,
            quantity, price, fee FROM lean_paper_execution_events
            WHERE client_id=? AND report_revision=? AND event_kind=?""",
            (CLIENT_ID, revision, kind)).fetchone()
        if old is not None and tuple(old) != values:
            raise RuntimeError("execution event changed")
        if old is None:
            db.execute("INSERT INTO lean_paper_execution_events VALUES (?, ?, ?, ?, ?, ?, ?)", values)

    @staticmethod
    def _validate(r: dict) -> None:
        expected = {1: ("Submitted", None, "0", "0", "0", "10000", "0"),
                    2: ("PartiallyFilled", EXECUTION_ID, "0.4", "89.91", "0.035964", "9964.000036", "0.4"),
                    3: ("PartiallyFilled", EXECUTION_ID, "0.4", "89.92", "0.035968", "9963.996032", "0.4"),
                    4: ("Canceled", EXECUTION_ID, "0.4", "89.92", "0.035968", "9963.996032", "0.4")}
        try:
            status, execution, executed, price, fee, cash, holding = expected[r["Revision"]]
            actual = (r["BrokerStatus"], r.get("ExecutionId"),
                      *(Decimal(str(r.get(key, 0))) for key in
                        ("ExecutedQuantity", "FillPrice", "Fee", "Cash", "Holding")))
            wanted = (status, execution, *(Decimal(value) for value in
                      (executed, price, fee, cash, holding)))
            if (r["LeanOrderId"] <= 0 or r["SymbolTicker"] != "TL001ASYN" or
                r["BrokerId"] != BROKER_ID or Decimal(str(r["Quantity"])) != 1 or
                Decimal(str(r["LimitPrice"])) != 90 or actual != wanted):
                raise ValueError("mismatch")
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("broker report identity, fill or account mismatch") from exc
