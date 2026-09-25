"""Variable H1 proposal against a complete synthetic local LEAN report."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from scripts.h1_lean_report_bridge import complete_report
from tidelab.h1_local_report_join import H1LocalReportJoin, _digest, _stable_snapshot_pair
from tidelab.h1_paper_bridge import H1SyntheticPaperBridge
from tidelab.paper_intent import PaperProductRules


OPEN = datetime(2026, 1, 8, 2, tzinfo=timezone.utc)
RULES = PaperProductRules("synthetic:BTC-USDT", "synthetic-h1-rules-1",
                          "0.00000001", "0.01", "0.00000001", "1")


def test_torn_report_candidate_holds_reconciliation(tmp_path: Path) -> None:
    report = tmp_path / "h1.json"
    report.write_text('{"Revision":2}', encoding="utf-8")
    assert complete_report(report) == '{"Revision":2}'
    candidate = tmp_path / "h1.json.next"
    candidate.write_text('{"Revision":3}', encoding="utf-8")
    with pytest.raises(RuntimeError, match="torn H1 report candidate"):
        complete_report(report)


def _proposal(open_at: datetime = OPEN, side: str = "buy") -> dict:
    identity = (f"H1-v1|synthetic-h1-check|synthetic:BTC-USDT|"
                f"{open_at:%Y-%m-%dT%H:%M:%S}.0000000Z|{side}")
    return dict(Policy="H1-v1", ExperimentId="synthetic-h1-check",
                InstrumentId="synthetic:BTC-USDT",
                ClientId="H1V1-" + hashlib.sha256(identity.encode()).hexdigest().upper(),
                SourceRevision="account-rev-1", SignalClosedUtc=open_at.isoformat(),
                ObservedOpenUtc=open_at.isoformat(), ClosedHours=169,
                DecisionIntent=1 if side == "buy" else 2, Risk=0,
                EntriesHalted=False, Side=side,
                Quantity="25" if side == "buy" else "2.5",
                LimitPrice="100", Equity="10000",
                Cash="10000" if side == "buy" else "9750",
                Units="0" if side == "buy" else "2.5",
                TargetGrossExposure="0.25" if side == "buy" else "0")


def _setup(tmp_path: Path, proposal: dict) -> tuple[H1SyntheticPaperBridge, H1LocalReportJoin]:
    database = tmp_path / "paper.sqlite3"
    bridge = H1SyntheticPaperBridge(database)
    bridge.initialize()
    bridge.prepare(json.dumps(proposal), observed_at=OPEN,
                   source_revision="account-rev-1", rules=RULES)
    assert bridge.claim_once(proposal["ClientId"], observed_at=OPEN,
                             opening_utc=OPEN, source_revision="account-rev-1", rules=RULES)
    join = H1LocalReportJoin(database)
    join.initialize()
    return bridge, join


def _report(proposal: dict, revision: int, status: str,
            executions: list[dict], cash: str, holding: str) -> dict:
    return dict(Version=1, ClientId=proposal["ClientId"],
                InstrumentId=proposal["InstrumentId"],
                SourceRevision=proposal["SourceRevision"], LeanOrderId=7,
                BrokerId="LOCAL-H1-7", Revision=revision, BrokerStatus=status,
                Quantity=proposal["Quantity"] if proposal["Side"] == "buy" else "-2.5",
                LimitPrice=proposal["LimitPrice"], Executions=executions,
                Cash=cash, Holding=holding)


def _fill(quantity: str = "10", price: str = "99", fee: str = "0.1") -> dict:
    return dict(ExecutionId="EX-1", Quantity=quantity, Price=price, Fee=fee)


def _snapshot(report: dict, next_open: datetime) -> dict:
    token = "H1-MOCK-LOCAL-H1-7-3"
    return dict(Version=1, Source="synthetic-local-broker",
                ObservedAtUtc=next_open.isoformat(), ConsistencyToken=token,
                AccountRevision=token, OrdersRevision=token,
                ExecutionsRevision=token, ClientId=report["ClientId"],
                BrokerId=report["BrokerId"], OrderStatus=report["BrokerStatus"],
                ReportRevision=report["Revision"],
                ReportReference="h1-report-v1:" + _digest(report),
                Cash=report["Cash"], Holding=report["Holding"],
                OpenBrokerIds=[], OrderFinality="terminal_at_cursor")


def test_snapshot_contract_rejects_mixed_or_incomplete_reads() -> None:
    report = _report(_proposal(), 3, "Canceled", [_fill()], "9009.9", "10")
    next_open = OPEN + timedelta(hours=1)
    snapshot = _snapshot(report, next_open)
    assert _stable_snapshot_pair(json.dumps(snapshot), json.dumps(snapshot),
                                 report, next_open) == _digest(snapshot)
    with pytest.raises(RuntimeError, match="requires two"):
        _stable_snapshot_pair(None, json.dumps(snapshot), report, next_open)
    with pytest.raises(RuntimeError, match="changed"):
        _stable_snapshot_pair(json.dumps(snapshot),
            json.dumps(snapshot | {"ConsistencyToken": "new"}), report, next_open)
    changes = ({"OrdersRevision": "different"}, {"Cash": "9009.8"},
               {"OpenBrokerIds": ["OTHER"]}, {"OrderStatus": "Filled"},
               {"ReportReference": "wrong"},
               {"ObservedAtUtc": (next_open + timedelta(hours=1)).isoformat()},
               {"OrderFinality": "unknown"})
    for change in changes:
        invalid = json.dumps(snapshot | change)
        with pytest.raises(ValueError, match="consistent terminal"):
            _stable_snapshot_pair(invalid, invalid, report, next_open)


def test_partial_cancel_restart_and_next_intent_gate(tmp_path: Path) -> None:
    proposal = _proposal()
    bridge, join = _setup(tmp_path, proposal)
    payload = json.dumps(proposal)
    submitted = _report(proposal, 1, "Submitted", [], "10000", "0")
    assert join.reconcile(payload, json.dumps(submitted)).startswith("hold revision=1")
    partial = _report(proposal, 2, "PartiallyFilled", [_fill()], "9009.9", "10")
    assert "executions=1" in join.reconcile(payload, json.dumps(partial))
    restarted = H1LocalReportJoin(bridge.intents.path)
    assert "executions=1" in restarted.reconcile(payload, json.dumps(partial))
    later = _proposal(OPEN + timedelta(hours=1))
    with pytest.raises(RuntimeError, match="unresolved"):
        bridge.prepare(json.dumps(later), observed_at=OPEN + timedelta(hours=1),
                       source_revision="account-rev-1", rules=RULES)
    canceled = _report(proposal, 3, "Canceled", [_fill()], "9009.9", "10")
    restarted.reconcile(payload, json.dumps(canceled))
    assert bridge.intents.state(proposal["ClientId"]) == "submission_unknown"
    with pytest.raises(RuntimeError, match="unresolved"):
        bridge.prepare(json.dumps(later), observed_at=OPEN + timedelta(hours=1),
                       source_revision="account-rev-1", rules=RULES)
    changed_after_close = _report(proposal, 4, "Canceled", [_fill()], "9009.9", "10")
    with pytest.raises(RuntimeError, match="closed"):
        restarted.reconcile(payload, json.dumps(changed_after_close))
    with sqlite3.connect(bridge.intents.path) as db:
        assert db.execute("SELECT COUNT(*) FROM h1_local_executions").fetchone()[0] == 1


def test_correction_duplicate_and_late_revision_hold_without_ledger_change(tmp_path: Path) -> None:
    proposal = _proposal()
    bridge, join = _setup(tmp_path, proposal)
    payload = json.dumps(proposal)
    first_skipped = _report(proposal, 2, "PartiallyFilled", [_fill()], "9009.9", "10")
    with pytest.raises(RuntimeError, match="first H1 report"):
        join.reconcile(payload, json.dumps(first_skipped))
    partial = _report(proposal, 1, "PartiallyFilled", [_fill()], "9009.9", "10")
    join.reconcile(payload, json.dumps(partial))
    altered = _report(proposal, 2, "PartiallyFilled", [_fill(price="98")], "9019.9", "10")
    with pytest.raises(RuntimeError, match="corrected"):
        join.reconcile(payload, json.dumps(altered))
    duplicate = _report(proposal, 2, "PartiallyFilled", [_fill(), _fill()], "8019.8", "20")
    with pytest.raises(ValueError, match="repeated"):
        join.reconcile(payload, json.dumps(duplicate))
    changed_same_revision = _report(proposal, 1, "Canceled", [_fill()], "9009.9", "10")
    with pytest.raises(RuntimeError, match="content changed"):
        join.reconcile(payload, json.dumps(changed_same_revision))
    skipped = _report(proposal, 3, "Canceled", [_fill()], "9009.9", "10")
    with pytest.raises(RuntimeError, match="revision"):
        join.reconcile(payload, json.dumps(skipped))
    with sqlite3.connect(bridge.intents.path) as db:
        assert db.execute("SELECT revision FROM h1_local_orders").fetchone()[0] == 1
        assert db.execute("SELECT price FROM h1_local_executions").fetchone()[0] == "99"


def test_sell_account_and_report_identity_must_match(tmp_path: Path) -> None:
    proposal = _proposal(side="sell")
    bridge, join = _setup(tmp_path, proposal)
    payload = json.dumps(proposal)
    filled = _report(proposal, 1, "Filled", [_fill("2.5", "99", "0.1")],
                     "9997.4", "0")
    wrong = filled | {"ClientId": "other"}
    with pytest.raises(ValueError, match="identity"):
        join.reconcile(payload, json.dumps(wrong))
    wrong = filled | {"Cash": "9998"}
    with pytest.raises(ValueError, match="account"):
        join.reconcile(payload, json.dumps(wrong))
    assert "status=Filled" in join.reconcile(payload, json.dumps(filled))
    assert bridge.intents.state(proposal["ClientId"]) == "submission_unknown"


def test_two_partial_executions_close_only_at_exact_quantity(tmp_path: Path) -> None:
    proposal = _proposal()
    bridge, join = _setup(tmp_path, proposal)
    payload = json.dumps(proposal)
    first = _report(proposal, 1, "PartiallyFilled", [_fill()], "9009.9", "10")
    join.reconcile(payload, json.dumps(first))
    second_fill = dict(ExecutionId="EX-2", Quantity="15", Price="98", Fee="0.15")
    final = _report(proposal, 2, "Filled", [_fill(), second_fill], "7539.75", "25")
    assert "executions=2" in join.reconcile(payload, json.dumps(final))
    assert "executions=2" in join.reconcile(payload, json.dumps(final))
    later = _report(proposal, 3, "Filled", [_fill(), second_fill], "7539.75", "25")
    with pytest.raises(RuntimeError, match="closed"):
        join.reconcile(payload, json.dumps(later))
    assert bridge.intents.state(proposal["ClientId"]) == "submission_unknown"
    with sqlite3.connect(bridge.intents.path) as db:
        assert db.execute("SELECT COUNT(*) FROM h1_local_executions").fetchone()[0] == 2


def test_terminal_report_handoff_prepares_next_exit_atomically(tmp_path: Path) -> None:
    proposal = _proposal()
    bridge, join = _setup(tmp_path, proposal)
    payload = json.dumps(proposal)
    join.reconcile(payload, json.dumps(_report(proposal, 1, "Submitted", [], "10000", "0")))
    join.reconcile(payload, json.dumps(_report(proposal, 2, "PartiallyFilled",
                                            [_fill()], "9009.9", "10")))
    terminal = _report(proposal, 3, "Canceled", [_fill()], "9009.9", "10")
    next_open = OPEN + timedelta(hours=1)
    following = _proposal(next_open, side="sell") | {
        "SourceRevision": "h1-report-v1:" + _digest(terminal),
        "Quantity": "10", "LimitPrice": "98", "Cash": "9009.9",
        "Units": "10", "Equity": "9989.9"}
    next_payload = json.dumps(following)
    snapshot = _snapshot(terminal, next_open)
    snapshot_json = json.dumps(snapshot)
    with pytest.raises(RuntimeError, match="terminal"):
        join.handoff(payload, json.dumps(_report(proposal, 2, "PartiallyFilled",
                                              [_fill()], "9009.9", "10")),
                     next_payload, RULES)
    with pytest.raises(ValueError, match="report/account handoff"):
        join.handoff(payload, json.dumps(terminal),
                     json.dumps(following | {"Cash": "9009.8"}), RULES)
    assert bridge.intents.state(proposal["ClientId"]) == "submission_unknown"
    with pytest.raises(RuntimeError, match="two broker snapshot reads"):
        join.handoff(payload, json.dumps(terminal), next_payload, RULES)
    with pytest.raises(RuntimeError, match="snapshot changed"):
        join.handoff(payload, json.dumps(terminal), next_payload, RULES,
            snapshot_before_json=snapshot_json,
            snapshot_after_json=json.dumps(snapshot | {"ConsistencyToken": "new"}))
    assert bridge.intents.state(proposal["ClientId"]) == "submission_unknown"
    with sqlite3.connect(bridge.intents.path) as db:
        assert db.execute("SELECT COUNT(*) FROM paper_intents").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM paper_intent_resolutions").fetchone()[0] == 0
    assert "quantity=10" in join.handoff(payload, json.dumps(terminal),
        next_payload, RULES, snapshot_before_json=snapshot_json,
        snapshot_after_json=snapshot_json)
    assert "replay" in join.handoff(payload, json.dumps(terminal),
        next_payload, RULES, snapshot_before_json=snapshot_json,
        snapshot_after_json=snapshot_json)
    changed_token = "different-cursor"
    changed = snapshot | {"ConsistencyToken": changed_token,
                          "AccountRevision": changed_token,
                          "OrdersRevision": changed_token,
                          "ExecutionsRevision": changed_token}
    with pytest.raises(RuntimeError, match="handoff replay changed"):
        join.handoff(payload, json.dumps(terminal), next_payload, RULES,
            snapshot_before_json=json.dumps(changed),
            snapshot_after_json=json.dumps(changed))
    assert bridge.intents.state(proposal["ClientId"]) == "resolved"
    assert bridge.intents.state(following["ClientId"]) == "prepared"
    assert bridge.claim_once(following["ClientId"], observed_at=next_open,
                             opening_utc=next_open,
                             source_revision=following["SourceRevision"], rules=RULES)
    assert not bridge.claim_once(following["ClientId"], observed_at=next_open,
                                 opening_utc=next_open,
                                 source_revision=following["SourceRevision"], rules=RULES)
    with sqlite3.connect(bridge.intents.path) as db:
        assert db.execute("SELECT COUNT(*) FROM paper_intent_resolutions").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM paper_intents").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM h1_handoff_snapshots").fetchone()[0] == 1
