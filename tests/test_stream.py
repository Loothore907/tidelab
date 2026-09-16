from __future__ import annotations

from datetime import datetime, timezone

from tidelab.stream import missing_sequence_count, parse_websocket_events


def test_parse_websocket_candle_observation_preserves_live_state() -> None:
    message = {
        "channel": "candles",
        "sequence_num": 12,
        "events": [
            {
                "type": "update",
                "candles": [
                    {
                        "start": "1789473600",
                        "high": "116",
                        "low": "114",
                        "open": "115",
                        "close": "115.5",
                        "volume": "2",
                        "product_id": "BTC-USD",
                    }
                ],
            }
        ],
    }

    events = parse_websocket_events(
        message,
        venue="coinbase_advanced",
        product_id="BTC-USD",
        received_at=datetime(2026, 9, 15, 12, tzinfo=timezone.utc),
        session_id="session",
    )

    assert len(events) == 1
    assert events[0].event_type == "candle_observation"
    assert events[0].interval_seconds == 300
    assert events[0].closed is False


def test_non_candle_channel_has_no_normalized_events() -> None:
    events = parse_websocket_events(
        {"channel": "heartbeats", "events": []},
        venue="coinbase_advanced",
        product_id="BTC-USD",
        received_at=datetime(2026, 9, 15, 12, tzinfo=timezone.utc),
        session_id="session",
    )

    assert events == []


def test_connection_sequence_gaps_are_not_computed_per_channel() -> None:
    sequence = [0, 1, 2, 3, 4, 7]
    previous = None
    missing = 0
    for current in sequence:
        missing += missing_sequence_count(previous, current)
        previous = current

    assert missing == 2
