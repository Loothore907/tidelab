"""The C# H1 proposal contract meeting the durable synthetic paper barrier."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from tidelab.h1_paper_bridge import H1SyntheticPaperBridge
from tidelab.paper_intent import PaperProductRules
from tidelab.synthetic_paper import SyntheticLocalPaperSource


OPEN = datetime(2026, 1, 8, 2, tzinfo=timezone.utc)
RULES = PaperProductRules("synthetic:BTC-USDT", "synthetic-h1-rules-1",
                          "0.00000001", "0.01", "0.00000001", "1")


def _proposal(*, side: str = "buy", open_at: datetime = OPEN) -> dict:
    identity = (f"H1-v1|synthetic-h1-check|synthetic:BTC-USDT|"
                f"{open_at:%Y-%m-%dT%H:%M:%S}.0000000Z|{side}")
    return dict(Policy="H1-v1", ExperimentId="synthetic-h1-check",
                InstrumentId="synthetic:BTC-USDT",
                ClientId="H1V1-" + hashlib.sha256(identity.encode()).hexdigest().upper(),
                SourceRevision="account-rev-1", SignalClosedUtc=open_at.isoformat(),
                ObservedOpenUtc=open_at.isoformat(), ClosedHours=169,
                DecisionIntent=1 if side == "buy" else 2,
                Risk=0, EntriesHalted=False, Side=side,
                Quantity="25" if side == "buy" else "2.5",
                LimitPrice="100", Equity="10000", Cash="10000" if side == "buy" else "9750",
                Units="0" if side == "buy" else "2.5",
                TargetGrossExposure="0.25" if side == "buy" else "0")


def test_h1_proposal_survives_restart_and_unknown_holds_all_new_intents(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    bridge = H1SyntheticPaperBridge(path)
    bridge.initialize()
    payload = json.dumps(_proposal())
    intent = bridge.prepare(payload, observed_at=OPEN,
                            source_revision="account-rev-1", rules=RULES)
    assert intent.quantity == "25"
    assert bridge.prepare(payload, observed_at=OPEN,
                          source_revision="account-rev-1", rules=RULES) == intent
    changed_mark = _proposal() | {"Cash": "9999"}
    with pytest.raises(ValueError, match="proposal changed"):
        bridge.prepare(json.dumps(changed_mark), observed_at=OPEN,
                       source_revision="account-rev-1", rules=RULES)
    with pytest.raises(ValueError, match="stored H1 proposal"):
        bridge.claim_once(intent.client_id, observed_at=OPEN + timedelta(hours=1),
                          opening_utc=OPEN + timedelta(hours=1),
                          source_revision="account-rev-1", rules=RULES)
    assert bridge.claim_once(intent.client_id, observed_at=OPEN, opening_utc=OPEN,
                             source_revision="account-rev-1", rules=RULES)
    restarted = H1SyntheticPaperBridge(path)
    assert restarted.claim_once(intent.client_id, observed_at=OPEN, opening_utc=OPEN,
                                source_revision="account-rev-1", rules=RULES) is False
    assert restarted.intents.state(intent.client_id) == "submission_unknown"
    later = _proposal(open_at=OPEN + timedelta(hours=1))
    with pytest.raises(RuntimeError, match="unresolved"):
        restarted.prepare(json.dumps(later), observed_at=OPEN + timedelta(hours=1),
                          source_revision="account-rev-1", rules=RULES)
    source = SyntheticLocalPaperSource(path)
    source.initialize()
    assert source.submit(intent.client_id, "account-rev-1")
    assert source.reconcile(intent.client_id) == "present_hold"
    assert source.reconcile(intent.client_id) == "present_hold"
    assert source.order_count(intent.client_id) == 1
    with sqlite3.connect(path) as db:
        db.execute("UPDATE synthetic_paper_orders SET quantity='24' WHERE client_id=?",
                   (intent.client_id,))
    with pytest.raises(RuntimeError, match="conflicts"):
        source.reconcile(intent.client_id)
    assert source.order_count(intent.client_id) == 1
    assert restarted.intents.state(intent.client_id) == "submission_unknown"


@pytest.mark.parametrize("change,reason", [
    ({"Quantity": "26"}, "sizing"),
    ({"Risk": 1, "EntriesHalted": True}, "sizing"),
    ({"ClientId": "different"}, "identity"),
    ({"SourceRevision": "account-rev-2"}, "revision"),
    ({"DecisionIntent": 2}, "decision"),
])
def test_invalid_policy_or_account_terms_never_write_intent(
        tmp_path: Path, change: dict, reason: str) -> None:
    bridge = H1SyntheticPaperBridge(tmp_path / "paper.sqlite3")
    bridge.initialize()
    proposal = _proposal() | change
    with pytest.raises(ValueError, match=reason):
        bridge.prepare(json.dumps(proposal), observed_at=OPEN,
                       source_revision="account-rev-1", rules=RULES)
    with sqlite3.connect(bridge.intents.path) as db:
        assert db.execute("SELECT COUNT(*) FROM paper_intents").fetchone()[0] == 0


def test_late_open_and_product_rules_hold_before_durable_write(tmp_path: Path) -> None:
    bridge = H1SyntheticPaperBridge(tmp_path / "paper.sqlite3")
    bridge.initialize()
    payload = json.dumps(_proposal())
    with pytest.raises(ValueError, match="stale"):
        bridge.prepare(payload, observed_at=OPEN + timedelta(seconds=1),
                       source_revision="account-rev-1", rules=RULES)
    stricter = PaperProductRules("synthetic:BTC-USDT", "other-rule-revision",
                                 "0.00000001", "0.03", "0.00000001", "1")
    with pytest.raises(ValueError, match="quote increment"):
        bridge.prepare(payload, observed_at=OPEN,
                       source_revision="account-rev-1", rules=stricter)
    assert bridge.intents.state(_proposal()["ClientId"]) is None


def test_exit_uses_full_inventory_and_cannot_be_claimed_late(tmp_path: Path) -> None:
    bridge = H1SyntheticPaperBridge(tmp_path / "paper.sqlite3")
    bridge.initialize()
    payload = json.dumps(_proposal(side="sell"))
    intent = bridge.prepare(payload, observed_at=OPEN,
                            source_revision="account-rev-1", rules=RULES)
    assert intent.side == "sell" and Decimal(intent.quantity) == Decimal("2.5")
    with pytest.raises(ValueError, match="no longer"):
        bridge.claim_once(intent.client_id, observed_at=OPEN + timedelta(seconds=1),
                          opening_utc=OPEN, source_revision="account-rev-1", rules=RULES)
    assert bridge.intents.state(intent.client_id) == "prepared"
