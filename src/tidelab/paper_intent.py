"""Durable synthetic paper intent barrier. This module cannot submit an order."""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sqlite3


def _positive_decimal(value: str, name: str) -> str:
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"{name} must be a positive decimal") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{name} must be a positive decimal")
    return format(number, "f")


@dataclass(frozen=True)
class PaperIntent:
    client_id: str
    instrument_id: str
    side: str
    quantity: str
    limit_price: str
    source_revision: str

    def __post_init__(self) -> None:
        if not self.client_id or not self.instrument_id or not self.source_revision:
            raise ValueError("client, instrument and source revision are required")
        if self.side not in ("buy", "sell"):
            raise ValueError("side must be buy or sell")
        object.__setattr__(self, "quantity", _positive_decimal(self.quantity, "quantity"))
        object.__setattr__(self, "limit_price", _positive_decimal(self.limit_price, "limit_price"))


class PaperIntentStore:
    """One database per paper authority; every claim is serialized across processes.

    A successful claim is persisted as ``submission_unknown`` before the caller
    can invoke its synthetic paper source. No timeout or process restart makes
    that claim reusable. A source-specific authority must record a verified
    resolution before this database accepts another client ID.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA synchronous = FULL")
        return connection

    def initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS paper_intents (
                    client_id TEXT PRIMARY KEY,
                    instrument_id TEXT NOT NULL,
                    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
                    quantity TEXT NOT NULL,
                    limit_price TEXT NOT NULL,
                    source_revision TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (state IN ('prepared', 'submission_unknown'))
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS paper_intent_resolutions (
                    client_id TEXT PRIMARY KEY REFERENCES paper_intents(client_id),
                    source_revision TEXT NOT NULL,
                    final_report_revision INTEGER NOT NULL CHECK (final_report_revision > 0)
                )"""
            )

    def prepare(self, intent: PaperIntent) -> bool:
        """Persist one intent; return False for an identical replay.

        A different client ID is held while any intent lacks reconciliation.
        An existing client ID with changed terms is always an error.
        """
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT * FROM paper_intents WHERE client_id=?", (intent.client_id,)
                ).fetchone()
                if existing is not None:
                    fields = ("instrument_id", "side", "quantity", "limit_price", "source_revision")
                    if any(existing[field] != getattr(intent, field) for field in fields):
                        raise ValueError("client ID already has different intent terms")
                    connection.commit()
                    return False
                if connection.execute("""SELECT 1 FROM paper_intents AS i
                    LEFT JOIN paper_intent_resolutions AS r ON r.client_id=i.client_id
                    WHERE r.client_id IS NULL LIMIT 1""").fetchone():
                    raise RuntimeError("paper authority has an unresolved intent")
                connection.execute(
                    """INSERT INTO paper_intents
                    (client_id, instrument_id, side, quantity, limit_price, source_revision, state)
                    VALUES (?, ?, ?, ?, ?, ?, 'prepared')""",
                    (intent.client_id, intent.instrument_id, intent.side, intent.quantity,
                     intent.limit_price, intent.source_revision),
                )
                connection.commit()
                return True
            except BaseException:
                connection.rollback()
                raise

    def claim_once(self, client_id: str, source_revision: str) -> bool:
        """Return True to one caller with matching source revision only."""
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                updated = connection.execute(
                    """UPDATE paper_intents SET state='submission_unknown'
                    WHERE client_id=? AND source_revision=? AND state='prepared'""",
                    (client_id, source_revision),
                ).rowcount
                connection.commit()
                return updated == 1
            except BaseException:
                connection.rollback()
                raise

    def state(self, client_id: str) -> str | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """SELECT i.state, r.client_id AS resolved_id FROM paper_intents AS i
                LEFT JOIN paper_intent_resolutions AS r ON r.client_id=i.client_id
                WHERE i.client_id=?""", (client_id,)
            ).fetchone()
            return None if row is None else ("resolved" if row["resolved_id"] else str(row["state"]))
