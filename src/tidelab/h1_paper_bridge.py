"""Synthetic H1 policy proposal to durable local paper intent; no broker API."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from contextlib import closing
import hashlib
import json
from pathlib import Path

from tidelab.paper_intent import PaperIntent, PaperIntentStore, PaperProductRules


def _hour(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("proposal requires a UTC hour") from exc
    if (parsed.tzinfo != timezone.utc or parsed.minute or parsed.second or
            parsed.microsecond):
        raise ValueError("proposal requires a UTC hour")
    return parsed


def _decimal(value: object) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError("proposal has invalid decimal") from exc
    if not result.is_finite():
        raise ValueError("proposal has invalid decimal")
    return result


class H1SyntheticPaperBridge:
    """Admit one policy-produced proposal at its invented opening instant.

    The caller owns the synthetic opening account/price snapshot and its revision.
    This bridge verifies the portable terms before using the existing SQLite
    intent barrier. It cannot establish a real broker's snapshot consistency.
    """

    def __init__(self, database: str | Path):
        self.intents = PaperIntentStore(database)

    def initialize(self) -> None:
        self.intents.initialize()
        with closing(self.intents._connect()) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS h1_paper_proposals (
                client_id TEXT PRIMARY KEY REFERENCES paper_intents(client_id),
                opening_utc TEXT NOT NULL,
                source_revision TEXT NOT NULL,
                rules_identity TEXT NOT NULL,
                proposal_hash TEXT NOT NULL
            )""")

    def prepare(self, proposal_json: str, *, observed_at: datetime,
                source_revision: str, rules: PaperProductRules) -> PaperIntent:
        proposal = json.loads(proposal_json, parse_float=Decimal)
        if not isinstance(proposal, dict) or proposal.get("Policy") != "H1-v1":
            raise ValueError("expected H1 v1 policy proposal")
        signal = _hour(proposal["SignalClosedUtc"])
        opening = _hour(proposal["ObservedOpenUtc"])
        if (signal != opening or observed_at != opening or
                observed_at.tzinfo != timezone.utc or
                proposal["SourceRevision"] != source_revision):
            raise ValueError("stale opening or account revision")
        experiment = proposal["ExperimentId"]
        instrument = proposal["InstrumentId"]
        side = proposal["Side"]
        if not isinstance(experiment, str) or not experiment.strip() or not isinstance(
                instrument, str) or not instrument.strip() or side not in ("buy", "sell"):
            raise ValueError("invalid proposal identity or side")
        if (type(proposal["ClosedHours"]) is not int or
                proposal["ClosedHours"] < 168 or
                proposal["DecisionIntent"] !=
                (1 if side == "buy" else 2) or
                proposal["Risk"] not in (0, 1) or
                type(proposal["EntriesHalted"]) is not bool):
            raise ValueError("invalid H1 policy decision")
        identity = (f"H1-v1|{experiment}|{instrument}|"
                    f"{signal:%Y-%m-%dT%H:%M:%S}.0000000Z|{side}")
        client_id = "H1V1-" + hashlib.sha256(identity.encode()).hexdigest().upper()
        if proposal["ClientId"] != client_id:
            raise ValueError("proposal client identity mismatch")
        price = _decimal(proposal["LimitPrice"])
        equity = _decimal(proposal["Equity"])
        cash = _decimal(proposal["Cash"])
        units = _decimal(proposal["Units"])
        quantity = _decimal(proposal["Quantity"])
        target = _decimal(proposal["TargetGrossExposure"])
        if price <= 0 or equity <= 0 or cash < 0 or units < 0:
            raise ValueError("invalid proposal account mark")
        if side == "buy":
            expected = (equity * Decimal("0.25") / price).quantize(
                Decimal("0.00000001"), rounding=ROUND_DOWN)
            if (proposal["Risk"] != 0 or proposal["EntriesHalted"] or
                    target != Decimal("0.25") or units != 0 or
                    cash < equity * Decimal("0.25") or quantity != expected or
                    quantity * price > cash):
                raise ValueError("H1 entry sizing or account mismatch")
        elif (target != 0 or units <= 0 or quantity != units or
              (proposal["Risk"] == 1) != proposal["EntriesHalted"]):
            raise ValueError("H1 exit inventory mismatch")
        intent = PaperIntent(client_id, instrument, side, str(quantity),
                             str(price), source_revision)
        self.intents.prepare(intent, rules)
        canonical = json.dumps(proposal, sort_keys=True, separators=(",", ":"),
                               default=str)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        with closing(self.intents._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                db.execute("""INSERT OR IGNORE INTO h1_paper_proposals
                    VALUES (?, ?, ?, ?, ?)""",
                    (client_id, opening.isoformat(), source_revision,
                     rules.identity, digest))
                stored = db.execute("SELECT * FROM h1_paper_proposals WHERE client_id=?",
                                    (client_id,)).fetchone()
                if (stored["opening_utc"], stored["source_revision"],
                    stored["rules_identity"], stored["proposal_hash"]) != (
                    opening.isoformat(), source_revision, rules.identity, digest):
                    raise ValueError("proposal changed for stable client identity")
                db.commit()
            except BaseException:
                db.rollback()
                raise
        return intent

    def claim_once(self, client_id: str, *, observed_at: datetime,
                   opening_utc: datetime, source_revision: str,
                   rules: PaperProductRules) -> bool:
        if (observed_at != opening_utc or observed_at.tzinfo != timezone.utc or
                opening_utc.minute or opening_utc.second or opening_utc.microsecond):
            raise ValueError("paper proposal is no longer at its opening instant")
        with closing(self.intents._connect()) as db:
            row = db.execute("SELECT * FROM h1_paper_proposals WHERE client_id=?",
                             (client_id,)).fetchone()
        if (row is None or row["opening_utc"] != opening_utc.isoformat() or
                row["source_revision"] != source_revision or
                row["rules_identity"] != rules.identity):
            raise ValueError("stored H1 proposal does not match claim")
        return self.intents.claim_once(client_id, source_revision, rules)
