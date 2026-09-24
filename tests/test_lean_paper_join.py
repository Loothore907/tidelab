"""Failure boundaries for the test-only LEAN local report authority."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from tidelab.lean_paper_join import LeanSyntheticPaperJoin
from tidelab.paper_intent import PaperIntent


def _join(tmp_path: Path) -> LeanSyntheticPaperJoin:
    join = LeanSyntheticPaperJoin(tmp_path / "paper.sqlite3", tmp_path / "report.json")
    join.initialize()
    join.prepare()
    return join


def _report(revision: int = 1) -> dict:
    report = dict(Revision=1, LeanOrderId=7, SymbolTicker="TL001ASYN",
                  BrokerId="TL001A-BROKER-ORDER-1", BrokerStatus="Submitted",
                  ExecutionId=None, Cash=10000, Holding=0, Quantity=1,
                  ExecutedQuantity=0, LimitPrice=90, FillPrice=0, Fee=0)
    if revision >= 2:
        report.update(Revision=2, BrokerStatus="PartiallyFilled",
                      ExecutionId="TL001A-JOINED-EXEC-1", Cash=9964.000036,
                      Holding=0.4, ExecutedQuantity=0.4, FillPrice=89.91,
                      Fee=0.035964)
    if revision >= 3:
        report.update(Revision=3, Cash=9963.996032, FillPrice=89.92,
                      Fee=0.035968)
    if revision >= 4:
        report.update(Revision=4, BrokerStatus="Canceled")
    return report


def _sell_report(revision: int = 1) -> dict:
    report = dict(Version=1, Revision=1, ClientId="TL002-SELL-CLIENT-1",
                  BrokerId="TL002-SELL-BROKER-1", LeanOrderId=8,
                  Quantity=-0.4, LimitPrice=89.79, BrokerStatus="Submitted",
                  ExecutionId=None, ExecutedQuantity=0, FillPrice=0, Fee=0,
                  Cash=9963.996032, Holding=0.4)
    if revision == 2:
        report.update(Revision=2, BrokerStatus="Filled",
                      ExecutionId="TL002-SELL-EXEC-1", ExecutedQuantity=-0.4,
                      FillPrice=89.79, Fee=0.035916, Cash=9999.876116,
                      Holding=0)
    return report


def test_claim_before_report_rearms_only_on_local_absence(tmp_path: Path) -> None:
    join = _join(tmp_path)
    assert join.claim()
    assert join.reconcile() == "absent_rearmed"
    assert join.claim()
    join.report.write_text(json.dumps(_report()), encoding="utf-8")
    assert join.reconcile().startswith("present_hold revision=1")
    assert join.reconcile().startswith("present_hold revision=1")
    assert join.claim() is False
    join.report.unlink()
    with pytest.raises(RuntimeError, match="disappeared"):
        join.reconcile()


def test_bad_account_and_changed_execution_hold_without_journal_write(tmp_path: Path) -> None:
    join = _join(tmp_path)
    assert join.claim()
    join.report.write_text(json.dumps(_report()), encoding="utf-8")
    join.reconcile()
    bad = _report(2)
    bad["Cash"] = 9999
    join.report.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(RuntimeError, match="mismatch"):
        join.reconcile()
    with sqlite3.connect(join.intents.path) as db:
        assert db.execute("SELECT COUNT(*) FROM lean_paper_execution_events").fetchone()[0] == 0
    join.report.write_text(json.dumps(_report(2)), encoding="utf-8")
    assert "events=1" in join.reconcile()
    assert "events=1" in join.reconcile()
    with sqlite3.connect(join.intents.path) as db:
        db.execute("UPDATE lean_paper_execution_events SET price='88' WHERE report_revision=2")
    with pytest.raises(RuntimeError, match="event changed"):
        join.reconcile()


def test_forward_sell_requires_closed_buy_and_reconciles_signed_execution(tmp_path: Path) -> None:
    join = _join(tmp_path)
    assert join.claim()
    join.report.write_text(json.dumps(_report()), encoding="utf-8")
    join.reconcile()
    with pytest.raises(RuntimeError, match="not closed"):
        join.prepare_sell()
    for revision in (2, 3, 4):
        join.report.write_text(json.dumps(_report(revision)), encoding="utf-8")
        join.reconcile()
    assert join.prepare_sell()
    assert join.intents.state("TL001A-JOINED-CLIENT-1") == "resolved"
    assert join.prepare_sell() is False
    assert join.claim_sell()
    assert join.reconcile_sell() == "sell_absent_rearmed"
    assert join.claim_sell()
    join.sell_report.write_text(json.dumps(_sell_report()), encoding="utf-8")
    assert "revision=1 events=3" in join.reconcile_sell()
    assert join.claim_sell() is False
    join.sell_report.write_text(json.dumps(_sell_report(2)), encoding="utf-8")
    assert "revision=2 events=4 cash=9999.876116 holding=0" in join.reconcile_sell()
    assert "revision=2 events=4" in join.reconcile_sell()
    assert join.prepare_sell() is False
    with pytest.raises(RuntimeError, match="unresolved"):
        join.intents.prepare(PaperIntent("third-client", "synthetic:TL001ASYN",
                                         "buy", "0.4", "90", "next-report"))
    with sqlite3.connect(join.intents.path) as db:
        assert db.execute("SELECT COUNT(*) FROM lean_paper_execution_events").fetchone()[0] == 4
    bad = _sell_report(2)
    bad["Cash"] = 10000
    join.sell_report.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(RuntimeError, match="mismatch"):
        join.reconcile_sell()
    join.sell_report.unlink()
    with pytest.raises(RuntimeError, match="sell report disappeared"):
        join.reconcile_sell()
