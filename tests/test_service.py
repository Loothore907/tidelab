from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from conftest import coinbase_config
from tidelab.coinbase import CoinbasePublicClient
from tidelab.service import sync_closed_bars
from tidelab.storage import TideStore


def test_sync_rejects_candles_outside_each_requested_window(tmp_path: Path) -> None:
    start = datetime(2026, 9, 15, 10, tzinfo=timezone.utc)
    end = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)
    candle_start = int(datetime(2026, 9, 15, 11, tzinfo=timezone.utc).timestamp())

    def transport(url: str, _headers: object, _timeout: float) -> dict[str, object]:
        query = parse_qs(urlparse(url).query)
        assert "start" in query and "end" in query
        return {
            "candles": [
                {
                    "start": str(candle_start),
                    "low": "1",
                    "high": "2",
                    "open": "1",
                    "close": "2",
                    "volume": "3",
                }
            ]
        }

    client = CoinbasePublicClient(
        coinbase_config(max_candles_per_request=1),
        transport=transport,
    )
    store = TideStore(tmp_path / "window.sqlite3")
    store.initialize()

    result = sync_closed_bars(client, store, start=start, end=end)

    assert result.fetched == 2
    assert result.inserted == 1
    assert result.duplicates == 0
