from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.error import URLError

from conftest import coinbase_config
from tidelab.coinbase import CoinbasePublicClient


PRODUCT = {
    "product_id": "BTC-USD",
    "product_type": "SPOT",
    "base_currency_id": "BTC",
    "quote_currency_id": "USD",
    "base_increment": "0.00000001",
    "quote_increment": "0.01",
    "base_min_size": "0.00000001",
    "quote_min_size": "1",
    "status": "online",
}

CANDLE = {
    "start": "1789473600",
    "low": "114000.25",
    "high": "116000.75",
    "open": "115000.00",
    "close": "115500.50",
    "volume": "12.345",
}


def test_fetch_product_normalizes_runtime_rules() -> None:
    client = CoinbasePublicClient(
        coinbase_config(),
        transport=lambda _url, _headers, _timeout: PRODUCT,
    )
    received_at = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)

    instrument = client.fetch_product(received_at)

    assert instrument.instrument_id == "coinbase_advanced:BTC-USD"
    assert instrument.quote_increment == "0.01"
    assert instrument.quote_min_size == "1"
    assert instrument.capabilities.historical_bars is True


def test_request_retries_are_bounded() -> None:
    attempts = 0
    sleeps: list[float] = []

    def flaky(_url: str, _headers: object, _timeout: float) -> dict[str, object]:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise URLError("temporary")
        return PRODUCT

    client = CoinbasePublicClient(
        coinbase_config(max_attempts=3, retry_base_seconds=0.25),
        transport=flaky,
        sleeper=sleeps.append,
    )

    client.fetch_product(datetime(2026, 9, 15, 12, tzinfo=timezone.utc))

    assert attempts == 3
    assert sleeps == [0.25, 0.5]


def test_parse_candle_marks_only_completed_interval_closed() -> None:
    client = CoinbasePublicClient(coinbase_config())
    start = datetime.fromtimestamp(int(CANDLE["start"]), tz=timezone.utc)

    closed_event, closed = client.parse_candle(
        CANDLE,
        received_at=start + timedelta(hours=1),
    )
    incomplete_event, incomplete = client.parse_candle(
        CANDLE,
        received_at=start + timedelta(minutes=59),
    )

    assert closed is True
    assert closed_event.closed is True
    assert incomplete is False
    assert incomplete_event.closed is False
    assert closed_event.payload["close"] == "115500.50"


def test_candle_windows_respect_request_limit() -> None:
    client = CoinbasePublicClient(coinbase_config(max_candles_per_request=2))
    start = datetime(2026, 9, 15, tzinfo=timezone.utc)
    end = start + timedelta(hours=5)

    windows = list(client.candle_windows(start, end))

    assert windows == [
        (start, start + timedelta(hours=2)),
        (start + timedelta(hours=2), start + timedelta(hours=4)),
        (start + timedelta(hours=4), end),
    ]
