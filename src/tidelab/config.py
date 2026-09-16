from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class StorageConfig:
    path: Path


@dataclass(frozen=True)
class CoinbaseConfig:
    venue: str
    product_id: str
    rest_url: str
    websocket_url: str
    granularity: str
    granularity_seconds: int
    max_candles_per_request: int
    request_timeout_seconds: float
    max_attempts: int
    retry_base_seconds: float


@dataclass(frozen=True)
class StreamConfig:
    channels: tuple[str, ...]
    open_timeout_seconds: float


@dataclass(frozen=True)
class ReportConfig:
    stale_after_seconds: int


@dataclass(frozen=True)
class AppConfig:
    storage: StorageConfig
    coinbase: CoinbaseConfig
    stream: StreamConfig
    report: ReportConfig


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).resolve()
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    storage_path = Path(raw["storage"]["path"])
    if not storage_path.is_absolute():
        storage_path = (config_path.parent / storage_path).resolve()

    coinbase = raw["coinbase"]
    stream = raw["stream"]
    report = raw["report"]

    if int(coinbase["granularity_seconds"]) <= 0:
        raise ValueError("granularity_seconds must be positive")
    if not 1 <= int(coinbase["max_candles_per_request"]) <= 350:
        raise ValueError("max_candles_per_request must be between 1 and 350")
    if int(coinbase["max_attempts"]) < 1:
        raise ValueError("max_attempts must be at least 1")
    channels = tuple(str(channel) for channel in stream["channels"])
    if not channels or any(channel not in {"candles", "heartbeats"} for channel in channels):
        raise ValueError("stream channels must contain candles and/or heartbeats")

    return AppConfig(
        storage=StorageConfig(path=storage_path),
        coinbase=CoinbaseConfig(
            venue=str(coinbase["venue"]),
            product_id=str(coinbase["product_id"]),
            rest_url=str(coinbase["rest_url"]).rstrip("/"),
            websocket_url=str(coinbase["websocket_url"]),
            granularity=str(coinbase["granularity"]),
            granularity_seconds=int(coinbase["granularity_seconds"]),
            max_candles_per_request=int(coinbase["max_candles_per_request"]),
            request_timeout_seconds=float(coinbase["request_timeout_seconds"]),
            max_attempts=int(coinbase["max_attempts"]),
            retry_base_seconds=float(coinbase["retry_base_seconds"]),
        ),
        stream=StreamConfig(
            channels=channels,
            open_timeout_seconds=float(stream["open_timeout_seconds"]),
        ),
        report=ReportConfig(stale_after_seconds=int(report["stale_after_seconds"])),
    )
