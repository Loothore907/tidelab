"""Authoritative local order double for synthetic paper recovery tests only."""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import sqlite3

from tidelab.domain import stable_id
from tidelab.paper_intent import PaperIntentStore


class SyntheticLocalPaperSource:
    """Store synthetic orders beside intents so local absence is definitive.

    This is not a LEAN brokerage adapter. Never use its absence result to retry
    a request sent to an external process, exchange, or broker.
    """

    def __init__(self, path: str | Path):
        self.intents = PaperIntentStore(path)

    def initialize(self) -> None:
        self.intents.initialize()
        with closing(self.intents._connect()) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS synthetic_paper_orders (
                    client_id TEXT PRIMARY KEY REFERENCES paper_intents(client_id),
                    broker_id TEXT NOT NULL UNIQUE,
                    instrument_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    limit_price TEXT NOT NULL,
                    source_revision TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state = 'submitted')
                )"""
            )

    def submit(self, client_id: str, source_revision: str) -> bool:
        """Write one local synthetic order after the durable claim; False if present."""
        with closing(self.intents._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                intent = connection.execute(
                    "SELECT * FROM paper_intents WHERE client_id=?", (client_id,)
                ).fetchone()
                if intent is None or intent["state"] != "submission_unknown":
                    raise RuntimeError("synthetic submission requires an unknown claimed intent")
                if intent["source_revision"] != source_revision:
                    raise RuntimeError("synthetic source revision changed")
                existing = connection.execute(
                    "SELECT * FROM synthetic_paper_orders WHERE client_id=?", (client_id,)
                ).fetchone()
                if existing is not None:
                    self._check_order(intent, existing)
                    connection.commit()
                    return False
                connection.execute(
                    """INSERT INTO synthetic_paper_orders
                    (client_id, broker_id, instrument_id, side, quantity, limit_price,
                     source_revision, state)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'submitted')""",
                    (client_id, stable_id("synthetic-paper", client_id), intent["instrument_id"],
                     intent["side"], intent["quantity"], intent["limit_price"],
                     intent["source_revision"]),
                )
                connection.commit()
                return True
            except BaseException:
                connection.rollback()
                raise

    def reconcile(self, client_id: str) -> str:
        """Adopt a present order or rearm the *same ID* on definitive local absence."""
        with closing(self.intents._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                intent = connection.execute(
                    "SELECT * FROM paper_intents WHERE client_id=?", (client_id,)
                ).fetchone()
                if intent is None:
                    raise ValueError("unknown paper intent")
                order = connection.execute(
                    "SELECT * FROM synthetic_paper_orders WHERE client_id=?", (client_id,)
                ).fetchone()
                if order is not None:
                    self._check_order(intent, order)
                    if intent["state"] != "submission_unknown":
                        raise RuntimeError("synthetic order exists without a claimed intent")
                    outcome = "present_hold"
                elif intent["state"] == "submission_unknown":
                    connection.execute(
                        "UPDATE paper_intents SET state='prepared' WHERE client_id=?", (client_id,)
                    )
                    outcome = "absent_rearmed"
                else:
                    outcome = "prepared"
                connection.commit()
                return outcome
            except BaseException:
                connection.rollback()
                raise

    def order_count(self, client_id: str) -> int:
        with closing(self.intents._connect()) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM synthetic_paper_orders WHERE client_id=?", (client_id,)
            ).fetchone()
            return int(row["n"])

    @staticmethod
    def _check_order(intent: sqlite3.Row, order: sqlite3.Row) -> None:
        fields = ("client_id", "instrument_id", "side", "quantity", "limit_price", "source_revision")
        if any(intent[field] != order[field] for field in fields):
            raise RuntimeError("synthetic source conflicts with intent")
        if order["broker_id"] != stable_id("synthetic-paper", intent["client_id"]):
            raise RuntimeError("synthetic broker ID conflicts with intent")
        if order["state"] != "submitted":
            raise RuntimeError("synthetic order state is unsupported")
