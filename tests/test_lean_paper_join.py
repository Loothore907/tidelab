"""Failure boundaries for the test-only LEAN local report authority."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from tidelab.lean_paper_join import LeanSyntheticPaperJoin


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
