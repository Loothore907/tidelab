"""Hand-specified channel semantics, shared inventory, and native LEAN comparison."""
from datetime import timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3

import pytest

from tidelab import channel_breakout as channel, historical_batch as batch, rsi_private as rsi
from tidelab.domain import isoformat_utc, parse_utc
from tidelab.historical_batch_demo import create_demo
from tidelab.package_lean_parity import validate_input, run_parity, compare_traces
from tidelab.strategy_batch import parse_package, replay_package, CloseSeries, UnsupportedPackage
from tidelab.trial_registry import TrialRegistry

ROOT = Path(__file__).resolve().parents[1]


def record():
    return batch.read(ROOT / "research/examples/channel-breakout-synthetic-record-v1.json")


def fixture(case="gap"):
    # Prior highs/lows differ from all closes. Independent expected first bounds:110/90.
    values = [(100, 100, 110, 90)] * 480 + [(100, 111, 150, 95), (200, 89, 210, 80), (50, 50, 60, 40)]
    if case == "equal_upper": values[480] = (100, 110, 150, 95)
    if case == "equal_lower": values[481] = (200, 90, 210, 80)
    if case == "expiry":
        values[0] = (100, 100, 5000, 1)
        values[480] = (100, 100, 110, 90)
        values[481] = (100, 111, 150, 95)
    if case == "open_terminal": values = values[:482]
    if case == "no_trade": values = [(100, 100, 110, 90)] * 483
    first = parse_utc("2026-01-01T00:00:00Z")
    return {"kind": "tidelab_synthetic", "interval_seconds": 3600, "bars": [
        {"start_utc": isoformat_utc(first + timedelta(hours=i)),
         "open": str(o), "close": str(c), "high": str(h), "low": str(l)}
        for i, (o, c, h, l) in enumerate(values)]}


def run(case="gap", **kwargs):
    strategy, bars = validate_input(channel.package(record()), record(), fixture(case))
    trace = []
    replay_package(strategy, bars, score_start=480, emit=trace.append, **kwargs)
    return trace


def test_first_scored_golden_prior_bounds_and_next_open_accounting():
    strategy, bars = validate_input(channel.package(record()), record(), fixture())
    assert (strategy.warmup, strategy.preceding_warmup) == (481, 480)
    trace = run()
    assert [r["action"] for r in trace] == ["buy", "sell", "hold"]
    assert trace[0]["index"] == 480 and trace[0]["fill"] is None
    assert trace[0]["channel_upper"] == "110" and trace[0]["channel_lower"] == "90"
    assert trace[1]["channel_upper"] == "150"  # bar480 admitted after its decision
    buy, sell = trace[1]["fill"], trace[2]["fill"]
    assert buy["utc"] == fixture()["bars"][481]["start_utc"]
    assert Decimal(buy["quantity"]) == Decimal("12.45637155")
    assert Decimal(buy["price"]) == Decimal("200.2")
    assert Decimal(buy["fee"]) == Decimal("6.2344139607750")
    assert Decimal(sell["price"]) == Decimal("49.95")
    assert Decimal(trace[-1]["cash"]) == Decimal("8120.64027125441875")
    assert trace[-1]["units"] == "0"
    with pytest.raises(ValueError, match="scoring_boundary"):
        replay_package(strategy, bars, score_start=479)


def test_equality_expiry_and_terminal_inventory():
    assert [r["action"] for r in run("equal_upper")] == ["hold"] * 3
    assert [r["action"] for r in run("equal_lower")] == ["buy", "hold", "hold"]
    expiry = run("expiry")
    assert expiry[0]["channel_upper"] == "5000" and expiry[0]["action"] == "hold"
    assert expiry[1]["channel_upper"] == "110" and expiry[1]["action"] == "buy"
    assert expiry[0]["channel_lower"] == "90"  # old low expired after 240, not480
    terminal = run("open_terminal")
    assert terminal[-1]["action"] == "hold" and Decimal(terminal[-1]["units"]) > 0


def test_no_future_dependence_and_readiness():
    strategy, bars = validate_input(channel.package(record()), record(), fixture())
    series = CloseSeries.from_bars(bars, 3)
    assert series.channel_upper[479] is None and series.channel_upper[480] == 110
    assert series.channel_lower[239] is None and series.channel_lower[240] == 90
    prefix = CloseSeries.from_bars(bars[:481], 3)
    assert prefix.channel_upper == series.channel_upper[:481]
    trace = []
    replay_package(strategy, bars, emit=trace.append)
    assert all(row["action"] == "hold" for row in trace[:480])
    assert not compare_traces({"channel_upper": None}, {"channel_upper": None})
    assert compare_traces({"channel_upper": "110"}, {"channel_upper": "110.000000000000000001"})


@pytest.mark.parametrize("damage", ["missing", "wick", "nonfinite", "domain", "partial"])
def test_invalid_actual_ohlc_fails_before_any_fill(damage):
    data = fixture()
    if damage == "missing":
        for row in data["bars"]:
            del row["high"]; del row["low"]
    elif damage == "partial": del data["bars"][0]["low"]
    else: data["bars"][0]["high"] = {"wick": "99", "nonfinite": "NaN", "domain": "1000000001"}[damage]
    with pytest.raises((ValueError, UnsupportedPackage)):
        strategy, bars = validate_input(channel.package(record()), record(), data)
        replay_package(strategy, bars, score_start=480, emit=lambda _: pytest.fail("fill path entered"))


@pytest.mark.parametrize("damage", ["version", "lag", "window", "bool"])
def test_only_exact_versioned_channel_supported(damage):
    candidate = channel.package(record())
    if damage == "version": candidate["schema_version"] = 2
    else: candidate["rule"]["entry"]["right"]["lag" if damage in ("lag", "bool") else "window"] = {
        "lag": 0, "window": 479, "bool": True}[damage]
    with pytest.raises(UnsupportedPackage): parse_package(candidate, record())


@pytest.mark.skipif(not os.environ.get("TIDELAB_LEAN_ROOT"), reason="requires pinned LEAN; exercised in CI")
@pytest.mark.parametrize("case", ["gap", "equal_upper", "equal_lower", "expiry", "open_terminal", "no_trade", "stress", "unscored"])
def test_actual_native_lean_channel(tmp_path, case):
    for name, value in (("package", channel.package(record())), ("record", record()),
                        ("fixture", fixture("gap" if case in ("stress", "unscored") else case))):
        batch.write(tmp_path / f"{name}.json", value)
    result = run_parity(tmp_path / "package.json", tmp_path / "record.json", tmp_path / "fixture.json",
        Path(os.environ["TIDELAB_LEAN_ROOT"]), os.environ.get("TIDELAB_DOTNET", "dotnet"), tmp_path / "attempt",
        cost=rsi.COSTS["stress" if case == "stress" else "baseline"], score_start=0 if case == "unscored" else 480)
    assert result["status"] == "matched", result


def test_full_shared_30_job_inventory_and_artifact_diagnostics(tmp_path):
    plan, snapshot, db = create_demo(tmp_path / "fixture", channel=True)
    output, registry = tmp_path / "attempt", tmp_path / "trials.sqlite3"
    result = batch.run(plan, snapshot, db, registry, output)
    assert result["status"] == "completed"
    assert len(result["jobs"]) == result["attempt_count"] == 30
    assert result["strategy_jobs"] == 10 and result["benchmark_jobs"] == 20
    assert all(r["status"] == "completed" and r["metrics"]["scored_bars"] == 8784 for r in result["jobs"])
    verdict = channel.review_artifacts(output)
    assert len(verdict["markets"]) == 5 and len(verdict["diagnostics"]) == 30
    assert verdict["automatic_promotion"] is False
    assert batch.recover(output, registry) == result
    with sqlite3.connect(registry) as conn:
        assert conn.execute("SELECT COUNT(*) FROM trial_attempts").fetchone()[0] == 30


def test_five_trip_threshold_and_incomplete_precedence():
    jobs = [{"index": i, "status": "completed", "metrics": {"round_trips": 5,
             "net_return": "0.02" if i % 6 < 2 else "0.01", "max_drawdown": "0.15"}} for i in range(30)]
    summary = {"kind": "synthetic", "jobs": jobs}
    markets = [f"synthetic:{i}" for i in range(5)]
    assert channel.review(summary, markets)["markets"][0]["status"] == "eligible_for_deeper_review"
    assert rsi.review(summary)["markets"][0]["status"] == "inconclusive"  # old policy unchanged
    jobs[0]["metrics"]["round_trips"] = 4
    jobs[5]["status"] = "failed"
    verdict = channel.review(summary, markets)
    assert verdict["markets"][0]["status"] == "incomplete" and verdict["eligibility_provisional"]
    jobs[5]["status"] = "completed"
    assert channel.review(summary, markets)["markets"][0]["status"] == "inconclusive"
    jobs[0]["metrics"].update(round_trips=5, net_return="NaN")
    assert channel.review(summary, markets)["markets"][0]["status"] == "incomplete"


def test_no_channel_grant_can_be_inferred_or_recreated(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite3, "connect", lambda *a, **kw: pytest.fail("database access"))
    for function in (channel.prepare_private, channel.execute_private, channel.UnapprovedChannelPolicy.preflight,
                     channel.UnapprovedChannelPolicy.package, channel.UnapprovedChannelPolicy.read_partition):
        with pytest.raises(ValueError, match="authority_ungranted"):
            function(tmp_path / "invented-authority.json", grant="renamed-rsi", registry=tmp_path / "alternate.sqlite3")
    with pytest.raises(ValueError, match="authority_ungranted"):
        channel.review({"kind": "third_party", "jobs": []}, [])


def test_shared_canonical_identity_keeps_rsi_consumed(tmp_path, monkeypatch):
    monkeypatch.setattr(rsi, "ROOT", tmp_path)
    base = tmp_path / "data/strategy_intake"; base.mkdir(parents=True)
    path = rsi.registry_path(); path.parent.mkdir(parents=True)
    registry = TrialRegistry(path); registry.initialize()
    batch.write(rsi.anchor_path(), {"store_id": "invented", "grant": rsi.GRANT, "authority_sha256": rsi.AUTHORITY_HASH})
    registry.reserve_access(rsi.GRANT, "authorization", {"store_id": "invented", "authority_sha256": rsi.AUTHORITY_HASH,
        "proposal_sha256": rsi.PROPOSAL, "record_sha256": rsi.RECORD_HASH})
    registry.reserve_access(rsi.GRANT, "snapshot", {"invented": True})
    registry.reserve_access(rsi.GRANT, "batch", {"invented": True})
    restored = rsi.canonical_registry()
    for operation in ("snapshot", "batch"):
        with pytest.raises(sqlite3.IntegrityError): restored.reserve_access(rsi.GRANT, operation, {})
    rsi.anchor_path().write_text('{}')
    with pytest.raises((ValueError, KeyError)): rsi.canonical_registry()


def test_shared_private_ohlc_and_bounded_query_on_invented_rows():
    from tidelab import private_history
    from tidelab.domain import canonical_json
    from tidelab.historical_input import FIELDS
    first = parse_utc("2024-01-01T00:00:00Z")
    window = private_history.Window(isoformat_utc(first), isoformat_utc(first + timedelta(hours=3)), 3)
    rows = []
    for i in range(3):
        stamp = isoformat_utc(first + timedelta(hours=i))
        rows.append(dict(zip(FIELDS, [str(i), 1, "okx", "okx:INVENTED", "bar", stamp, stamp,
            window.source, 3600, 1, canonical_json(dict(open="100", close="101", high="130", low="80", volume="1")),
            canonical_json(dict(archive_period="2024-01", archive_sha256="a" * 64, minute_rows=60))])))
    bars, _ = private_history.validate_rows(rows, "okx:INVENTED", window, preserve_ohlc=True)
    assert bars[0].high == 130 and bars[0].low == 80
    legacy, _ = private_history.validate_rows(rows, "okx:INVENTED", window)
    assert legacy[0].high is None  # preserve original RSI object semantics
    class Query:
        def execute(self, sql, params):
            assert params == ("okx:INVENTED", window.first, window.end)
            assert "event_time_utc>=? AND event_time_utc<?" in sql
            return self
        def fetchmany(self, count):
            assert count == 4
            return rows
    assert private_history.rows_for(Query(), "okx:INVENTED", window) == rows
    rows[0]["payload_json"] = canonical_json(dict(open="100", close="101", high="1000000001", low="80", volume="1"))
    with pytest.raises(UnsupportedPackage):
        private_history.validate_rows(rows, "okx:INVENTED", window, preserve_ohlc=True)


def test_retained_trace_diagnostics_golden(tmp_path):
    from tidelab.batch_review import trace_diagnostics
    path = tmp_path / "trace.jsonl"
    path.write_text('\n'.join(json.dumps(row) for row in run()))
    result = trace_diagnostics(path, fee_rate=Decimal("0.0025"), adverse_rate=Decimal("0.001"))
    assert Decimal(result["largest_closed_trade_net_pnl"]) == Decimal("-1879.35972874558125")
    assert Decimal(result["terminal_unrealized_net_of_entry_fee"]) == 0
    path.write_text('\n'.join(json.dumps(row) for row in run("open_terminal")))
    result = trace_diagnostics(path, fee_rate=Decimal("0.0025"), adverse_rate=Decimal("0.001"))
    assert result["largest_closed_trade_net_pnl"] is None
    assert Decimal(result["terminal_hypothetical_exit_cost"]) > 0
