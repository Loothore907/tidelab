from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from typing import Any, Mapping


SCHEMA_VERSION = 1


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_utc(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def decimal_text(value: Any, field_name: str) -> str:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be decimal-compatible") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return format(parsed, "f")


def canonical_json(value: Mapping[str, Any] | list[Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_id(*parts: str) -> str:
    material = "\x1f".join(parts).encode("utf-8")
    return sha256(material).hexdigest()


@dataclass(frozen=True)
class CapabilityProfile:
    venue: str
    product_class: str
    public_market_data: bool
    historical_bars: bool
    live_market_data: bool
    expiry_and_settlement: bool = False
    onchain_transactions: bool = False
    schema_version: int = SCHEMA_VERSION
    native: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Instrument:
    venue: str
    venue_instrument_id: str
    product_class: str
    base_asset: str
    quote_asset: str
    base_increment: str
    quote_increment: str
    base_min_size: str
    quote_min_size: str
    status: str
    fetched_at: datetime
    capabilities: CapabilityProfile
    native: Mapping[str, Any]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("base_increment", "quote_increment", "base_min_size", "quote_min_size"):
            object.__setattr__(self, name, decimal_text(getattr(self, name), name))
        if self.fetched_at.tzinfo is None:
            raise ValueError("fetched_at must be timezone-aware")

    @property
    def instrument_id(self) -> str:
        return f"{self.venue}:{self.venue_instrument_id}"


@dataclass(frozen=True)
class MarketEvent:
    venue: str
    instrument_id: str
    event_type: str
    event_time: datetime
    received_at: datetime
    source: str
    payload: Mapping[str, Any]
    native: Mapping[str, Any]
    interval_seconds: int | None = None
    closed: bool = False
    source_key: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.event_time.tzinfo is None or self.received_at.tzinfo is None:
            raise ValueError("event timestamps must be timezone-aware")
        if self.interval_seconds is not None and self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

    @property
    def event_id(self) -> str:
        source_key = self.source_key or canonical_json(dict(self.native))
        return stable_id(
            str(self.schema_version),
            self.venue,
            self.instrument_id,
            self.event_type,
            isoformat_utc(self.event_time),
            self.source,
            source_key,
        )
