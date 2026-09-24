from __future__ import annotations

from multiprocessing import get_context
import os
from pathlib import Path
import sqlite3

import pytest

from tidelab.paper_intent import PaperIntent
from tidelab.synthetic_paper import SyntheticLocalPaperSource


CLIENT_ID = "synthetic-restart-1"
REVISION = "snapshot-7"


def _crash_after_claim(path: str, write_order: bool) -> None:
    source = SyntheticLocalPaperSource(path)
    source.initialize()
    source.intents.prepare(PaperIntent(CLIENT_ID, "synthetic:BTC-USD", "buy", "0.4", "89.91", REVISION))
    assert source.intents.claim_once(CLIENT_ID, REVISION)
    if write_order:
        assert source.submit(CLIENT_ID, REVISION)
    os._exit(0)


@pytest.mark.parametrize("write_order", [False, True])
def test_restart_distinguishes_local_absence_from_lost_ack(tmp_path: Path, write_order: bool) -> None:
    path = tmp_path / "paper.sqlite3"
    process = get_context("spawn").Process(target=_crash_after_claim, args=(str(path), write_order))
    process.start()
    process.join(timeout=15)
    assert process.exitcode == 0

    source = SyntheticLocalPaperSource(path)
    assert source.intents.state(CLIENT_ID) == "submission_unknown"
    if write_order:
        assert source.reconcile(CLIENT_ID) == "present_hold"
        assert source.reconcile(CLIENT_ID) == "present_hold"
        assert source.intents.claim_once(CLIENT_ID, REVISION) is False
        assert source.submit(CLIENT_ID, REVISION) is False
    else:
        assert source.reconcile(CLIENT_ID) == "absent_rearmed"
        assert source.intents.claim_once(CLIENT_ID, REVISION) is True
        assert source.submit(CLIENT_ID, REVISION) is True
        assert source.reconcile(CLIENT_ID) == "present_hold"
    assert source.order_count(CLIENT_ID) == 1


def test_source_requires_claim_and_blocks_conflicting_report(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    source = SyntheticLocalPaperSource(path)
    source.initialize()
    source.intents.prepare(PaperIntent(CLIENT_ID, "synthetic:BTC-USD", "sell", "0.4", "89.91", REVISION))
    with pytest.raises(RuntimeError, match="claimed intent"):
        source.submit(CLIENT_ID, REVISION)
    assert source.intents.claim_once(CLIENT_ID, REVISION)
    assert source.submit(CLIENT_ID, REVISION)

    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE synthetic_paper_orders SET quantity='0.5' WHERE client_id=?", (CLIENT_ID,)
        )
    with pytest.raises(RuntimeError, match="conflicts with intent"):
        source.reconcile(CLIENT_ID)
    assert source.intents.state(CLIENT_ID) == "submission_unknown"
    assert source.intents.claim_once(CLIENT_ID, REVISION) is False
