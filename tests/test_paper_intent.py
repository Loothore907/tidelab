from __future__ import annotations

from multiprocessing import get_context
from pathlib import Path

import pytest

from tidelab.paper_intent import PaperIntent, PaperIntentStore


def _intent(client_id: str = "synthetic-1") -> PaperIntent:
    return PaperIntent(client_id, "synthetic:BTC-USD", "buy", "0.4", "89.91", "report-7")


def _claim_worker(path: str, ready: object, results: object) -> None:
    ready.wait(timeout=10)
    results.put(PaperIntentStore(path).claim_once("synthetic-1", "report-7"))


def test_intent_survives_restart_and_never_reclaims_unknown(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    first = PaperIntentStore(path)
    first.initialize()
    assert first.prepare(_intent())
    assert PaperIntentStore(path).prepare(_intent()) is False
    assert PaperIntentStore(path).state("synthetic-1") == "prepared"

    assert PaperIntentStore(path).claim_once("synthetic-1", "report-8") is False
    assert PaperIntentStore(path).state("synthetic-1") == "prepared"
    assert PaperIntentStore(path).claim_once("synthetic-1", "report-7") is True
    assert PaperIntentStore(path).state("synthetic-1") == "submission_unknown"
    assert PaperIntentStore(path).claim_once("synthetic-1", "report-7") is False
    with pytest.raises(RuntimeError, match="unresolved"):
        PaperIntentStore(path).prepare(_intent("synthetic-2"))


def test_reused_client_id_cannot_change_order_or_source(tmp_path: Path) -> None:
    store = PaperIntentStore(tmp_path / "paper.sqlite3")
    store.initialize()
    store.prepare(_intent())
    with pytest.raises(ValueError, match="different intent"):
        store.prepare(PaperIntent("synthetic-1", "synthetic:BTC-USD", "sell", "0.4", "89.91", "report-7"))
    with pytest.raises(ValueError, match="different intent"):
        store.prepare(PaperIntent("synthetic-1", "synthetic:BTC-USD", "buy", "0.4", "89.91", "report-8"))
    assert store.state("synthetic-1") == "prepared"


@pytest.mark.parametrize("quantity,limit_price", [("0", "89"), ("NaN", "89"), ("1", "Infinity")])
def test_invalid_order_terms_hold(quantity: str, limit_price: str) -> None:
    with pytest.raises(ValueError, match="positive decimal"):
        PaperIntent("synthetic-1", "synthetic:BTC-USD", "buy", quantity, limit_price, "report-7")


def test_only_one_process_can_claim(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    store = PaperIntentStore(path)
    store.initialize()
    store.prepare(_intent())

    context = get_context("spawn")
    ready = context.Event()
    results = context.Queue()
    processes = [context.Process(target=_claim_worker, args=(str(path), ready, results)) for _ in range(4)]
    for process in processes:
        process.start()
    ready.set()
    outcomes = [results.get(timeout=15) for _ in processes]
    for process in processes:
        process.join(timeout=15)
        assert process.exitcode == 0
    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 3
    assert store.state("synthetic-1") == "submission_unknown"
