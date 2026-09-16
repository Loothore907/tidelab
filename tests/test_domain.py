from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tidelab.domain import MarketEvent, decimal_text


def test_market_event_id_is_stable_for_mapping_order() -> None:
    timestamp = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
    first = MarketEvent(
        venue="venue",
        instrument_id="venue:BTC-USD",
        event_type="bar",
        event_time=timestamp,
        received_at=timestamp,
        source="fixture",
        payload={"close": "1"},
        native={"a": 1, "b": 2},
    )
    second = MarketEvent(
        venue="venue",
        instrument_id="venue:BTC-USD",
        event_type="bar",
        event_time=timestamp,
        received_at=timestamp,
        source="fixture",
        payload={"close": "1"},
        native={"b": 2, "a": 1},
    )

    assert first.event_id == second.event_id


def test_decimal_text_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        decimal_text("NaN", "price")


def test_market_event_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MarketEvent(
            venue="venue",
            instrument_id="venue:BTC-USD",
            event_type="bar",
            event_time=datetime(2026, 9, 15, 12),
            received_at=datetime(2026, 9, 15, 12, tzinfo=timezone.utc),
            source="fixture",
            payload={},
            native={},
        )
