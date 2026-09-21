from __future__ import annotations

from pathlib import Path

import pytest

from tidelab.config import load_config


CONFIG_TEXT = """
[storage]
path = "data/test.sqlite3"

[coinbase]
venue = "coinbase_advanced"
product_id = "BTC-USD"
rest_url = "https://example.invalid/api"
websocket_url = "wss://example.invalid"
granularity = "ONE_HOUR"
granularity_seconds = 3600
max_candles_per_request = 350
request_timeout_seconds = 15
max_attempts = 3
retry_base_seconds = 0.1

[stream]
channels = ["candles", "heartbeats"]
open_timeout_seconds = 15

[report]
stale_after_seconds = 7200
"""


def test_load_config_resolves_storage_relative_to_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG_TEXT, encoding="utf-8")

    config = load_config(path)

    assert config.storage.path == (tmp_path / "data" / "test.sqlite3").resolve()
    assert config.stream.channels == ("candles", "heartbeats")


def test_load_config_rejects_unsupported_channel(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG_TEXT.replace('"heartbeats"', '"user"'), encoding="utf-8")

    with pytest.raises(ValueError, match="channels"):
        load_config(path)
