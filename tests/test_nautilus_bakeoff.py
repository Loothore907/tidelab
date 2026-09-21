from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("nautilus_trader")

from nautilus_trader.model import InstrumentId

from tidelab.domain import MarketEvent
from tidelab.nautilus_bakeoff import admit_hourly_bars, run_execution_probe, run_probe


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
INSTRUMENT_ID = InstrumentId.from_str("BTC-USDT.SIM")


def synthetic_bar(hour: int, close: str, *, closed: bool = True) -> MarketEvent:
    start = START + timedelta(hours=hour)
    return MarketEvent(
        venue="SIM",
        instrument_id="SIM:BTC-USDT",
        event_type="bar",
        event_time=start,
        received_at=start + timedelta(hours=1),
        source="synthetic.fixture",
        payload={
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": "1.000",
        },
        native={"synthetic_hour": hour},
        interval_seconds=3600,
        closed=closed,
        source_key=str(hour),
    )


def test_synthetic_replay_is_deterministic_and_has_provenance() -> None:
    bars = [synthetic_bar(i, price) for i, price in enumerate(
        ("100.00", "101.00", "102.00", "99.00", "98.00"))]
    first = run_probe(bars)
    second = run_probe(bars)
    assert first == second
    assert first["signals"] == ("warming", "warming", "long", "cash", "cash")
    assert first["source_event_ids"] == tuple(bar.event_id for bar in bars)
    assert first["orders_submitted"] == 0


@pytest.mark.parametrize("events,reason", [
    ([synthetic_bar(0, "100.00"), synthetic_bar(0, "100.00")], "duplicate"),
    ([synthetic_bar(0, "100.00"), synthetic_bar(2, "100.00")], "missing"),
    ([synthetic_bar(0, "100.00", closed=False)], "closed"),
])
def test_rejects_invalid_sequences(events: list[MarketEvent], reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        admit_hourly_bars(events, instrument_id=INSTRUMENT_ID)


def test_rejects_non_synthetic_source() -> None:
    event = synthetic_bar(0, "100.00")
    event = MarketEvent(**{**vars(event), "source": "coinbase.public_rest.candles"})
    with pytest.raises(ValueError, match="synthetic"):
        admit_hourly_bars([event], instrument_id=INSTRUMENT_ID)


def test_simulated_order_waits_for_later_quote_and_updates_cash() -> None:
    result = run_execution_probe([synthetic_bar(0, "100.00")], quote_after_first_close=True)
    assert result["rejections"] == ()
    fill_ns = int(START.timestamp()) * 1_000_000_000 + 3_660_000_000_000
    assert result["fills"] == (("1.000", "100.20", "0.10020000 USDT", fill_ns),)
    assert result["fills"][0][3] > result["submitted_at"]
    assert result["usdt_total"] == "9899.69980000 USDT"
    assert result["btc_total"] == "1.00000000 BTC"
    assert result["cached_order_status"] == "FILLED"
    assert result["cached_filled_qty"] == "1.000"
    assert run_execution_probe([synthetic_bar(0, "100.00")], quote_after_first_close=True) == result


def test_simulated_order_without_following_market_data_is_not_a_fill() -> None:
    result = run_execution_probe([synthetic_bar(0, "100.00")], quote_after_first_close=False)
    assert result["fills"] == ()
    assert result["cached_order_status"] == "REJECTED"
    assert result["cached_filled_qty"] == "0.000"
    assert result["usdt_total"] == "10000.00000000 USDT"
    assert result["btc_total"] == "None"


def test_limited_quote_exposes_residual_fill_assumption() -> None:
    result = run_execution_probe(
        [synthetic_bar(0, "100.00")],
        quote_after_first_close=True,
        quote_size="0.400",
    )
    assert result["fills"][:1][0][:3] == ("0.400", "100.20", "0.04008000 USDT")
    assert result["fills"][1][:3] == ("0.600", "100.21", "0.06012600 USDT")
    assert result["usdt_total"] == "9899.69379400 USDT"
    assert result["btc_total"] == "1.00000000 BTC"
    assert result["cached_order_status"] == "FILLED"
