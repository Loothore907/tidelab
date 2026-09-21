from __future__ import annotations

from tidelab.config import CoinbaseConfig


def coinbase_config(**overrides: object) -> CoinbaseConfig:
    values: dict[str, object] = {
        "venue": "coinbase_advanced",
        "product_id": "BTC-USD",
        "rest_url": "https://example.invalid/api/v3/brokerage",
        "websocket_url": "wss://example.invalid",
        "granularity": "ONE_HOUR",
        "granularity_seconds": 3600,
        "max_candles_per_request": 350,
        "request_timeout_seconds": 1.0,
        "max_attempts": 3,
        "retry_base_seconds": 0.01,
    }
    values.update(overrides)
    return CoinbaseConfig(**values)  # type: ignore[arg-type]
