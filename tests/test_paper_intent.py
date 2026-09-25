from __future__ import annotations

from multiprocessing import get_context
from pathlib import Path
import sqlite3

import pytest

from tidelab.paper_intent import PaperIntent, PaperIntentStore, PaperProductRules


RULES = PaperProductRules("synthetic:BTC-USD", "fixture-rules-v1", "0.1", "0.01", "0.1", "1")


def _intent(client_id: str = "synthetic-1") -> PaperIntent:
    return PaperIntent(client_id, "synthetic:BTC-USD", "buy", "0.4", "89.91", "report-7")


def _claim_worker(path: str, ready: object, results: object) -> None:
    ready.wait(timeout=10)
    results.put(PaperIntentStore(path).claim_once("synthetic-1", "report-7", RULES))


def test_intent_survives_restart_and_never_reclaims_unknown(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    first = PaperIntentStore(path)
    first.initialize()
    assert first.prepare(_intent(), RULES)
    assert PaperIntentStore(path).prepare(_intent(), RULES) is False
    assert PaperIntentStore(path).state("synthetic-1") == "prepared"

    assert PaperIntentStore(path).claim_once("synthetic-1", "report-8", RULES) is False
    assert PaperIntentStore(path).state("synthetic-1") == "prepared"
    assert PaperIntentStore(path).claim_once("synthetic-1", "report-7", RULES) is True
    assert PaperIntentStore(path).state("synthetic-1") == "submission_unknown"
    assert PaperIntentStore(path).claim_once("synthetic-1", "report-7", RULES) is False
    with pytest.raises(RuntimeError, match="unresolved"):
        PaperIntentStore(path).prepare(_intent("synthetic-2"), RULES)


def test_reused_client_id_cannot_change_order_or_source(tmp_path: Path) -> None:
    store = PaperIntentStore(tmp_path / "paper.sqlite3")
    store.initialize()
    store.prepare(_intent(), RULES)
    with pytest.raises(ValueError, match="different intent"):
        store.prepare(PaperIntent("synthetic-1", "synthetic:BTC-USD", "sell", "0.4", "89.91", "report-7"), RULES)
    with pytest.raises(ValueError, match="different intent"):
        store.prepare(PaperIntent("synthetic-1", "synthetic:BTC-USD", "buy", "0.4", "89.91", "report-8"), RULES)
    changed_rules = PaperProductRules("synthetic:BTC-USD", "fixture-rules-v1", "0.01", "0.01", "0.1", "1")
    with pytest.raises(ValueError, match="different intent"):
        store.prepare(_intent(), changed_rules)
    assert store.state("synthetic-1") == "prepared"
    assert store.claim_once("synthetic-1", "report-7", changed_rules) is False
    assert store.claim_once("synthetic-1", "report-7", RULES) is True


@pytest.mark.parametrize("intent,reason", [
    (PaperIntent("a", "synthetic:OTHER", "buy", "0.4", "89.91", "r"), "instrument mismatch"),
    (PaperIntent("a", "synthetic:BTC-USD", "buy", "0.35", "89.91", "r"), "base increment"),
    (PaperIntent("a", "synthetic:BTC-USD", "buy", "0.4", "89.911", "r"), "quote increment"),
    (PaperIntent("a", "synthetic:BTC-USD", "buy", "0.1", "1", "r"), "quote minimum"),
])
def test_product_rules_hold_before_intent_write(tmp_path: Path, intent: PaperIntent, reason: str) -> None:
    store = PaperIntentStore(tmp_path / "paper.sqlite3")
    store.initialize()
    with pytest.raises(ValueError, match=reason):
        store.prepare(intent, RULES)
    assert store.state(intent.client_id) is None


def test_legacy_unversioned_intent_cannot_be_claimed(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE paper_intents (
            client_id TEXT PRIMARY KEY, instrument_id TEXT, side TEXT, quantity TEXT,
            limit_price TEXT, source_revision TEXT, state TEXT)""")
        db.execute("INSERT INTO paper_intents VALUES (?, ?, ?, ?, ?, ?, ?)",
                   ("old", "synthetic:BTC-USD", "buy", "0.4", "89.91", "report-7", "prepared"))
    store = PaperIntentStore(path)
    store.initialize()
    assert store.claim_once("old", "report-7", RULES) is False
    with pytest.raises(ValueError, match="different intent"):
        store.prepare(PaperIntent("old", "synthetic:BTC-USD", "buy", "0.4", "89.91", "report-7"), RULES)


def test_existing_h1_successor_gains_claim_guard_on_upgrade(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE paper_intents (
            client_id TEXT PRIMARY KEY, instrument_id TEXT, side TEXT, quantity TEXT,
            limit_price TEXT, source_revision TEXT, rules_identity TEXT, state TEXT)""")
        db.execute("INSERT INTO paper_intents VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   ("next", RULES.instrument_id, "buy", "0.4", "89.91",
                    "h1-report-v1:old-hash", RULES.identity, "prepared"))
    store = PaperIntentStore(path)
    store.initialize()
    with pytest.raises(RuntimeError, match="source-specific guarded claim"):
        store.claim_once("next", "h1-report-v1:old-hash", RULES)
    assert store.state("next") == "prepared"


def test_changed_stored_terms_hold_at_claim(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    store = PaperIntentStore(path)
    store.initialize()
    store.prepare(_intent(), RULES)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE paper_intents SET quantity='0.35' WHERE client_id='synthetic-1'")
    with pytest.raises(ValueError, match="base increment"):
        store.claim_once("synthetic-1", "report-7", RULES)
    assert store.state("synthetic-1") == "prepared"


@pytest.mark.parametrize("quantity,limit_price", [("0", "89"), ("NaN", "89"), ("1", "Infinity")])
def test_invalid_order_terms_hold(quantity: str, limit_price: str) -> None:
    with pytest.raises(ValueError, match="positive decimal"):
        PaperIntent("synthetic-1", "synthetic:BTC-USD", "buy", quantity, limit_price, "report-7")


def test_only_one_process_can_claim(tmp_path: Path) -> None:
    path = tmp_path / "paper.sqlite3"
    store = PaperIntentStore(path)
    store.initialize()
    store.prepare(_intent(), RULES)

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
