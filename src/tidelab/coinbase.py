from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import time
from typing import Any, Callable, Iterator, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from tidelab.config import CoinbaseConfig
from tidelab.domain import CapabilityProfile, Instrument, MarketEvent, decimal_text


JsonObject = dict[str, Any]
Transport = Callable[[str, Mapping[str, str], float], JsonObject]


class CoinbaseRequestError(RuntimeError):
    pass


def _default_transport(url: str, headers: Mapping[str, str], timeout: float) -> JsonObject:
    request = Request(url, headers=dict(headers), method="GET")
    with urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    value = json.loads(body)
    if not isinstance(value, dict):
        raise CoinbaseRequestError("Coinbase returned a non-object JSON response")
    return value


class CoinbasePublicClient:
    def __init__(
        self,
        config: CoinbaseConfig,
        *,
        transport: Transport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        self.config = config
        self._transport = transport or _default_transport
        self._sleep = sleeper

    def _get_json(self, path: str, query: Mapping[str, str | int] | None = None) -> JsonObject:
        url = f"{self.config.rest_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        headers = {
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "TideLab-TL001/0.1",
        }

        last_error: BaseException | None = None
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return self._transport(url, headers, self.config.request_timeout_seconds)
            except HTTPError as exc:
                if exc.code != 429 and not 500 <= exc.code <= 599:
                    raise CoinbaseRequestError(f"Coinbase request failed with HTTP {exc.code}") from exc
                last_error = exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc

            if attempt < self.config.max_attempts:
                self._sleep(self.config.retry_base_seconds * (2 ** (attempt - 1)))

        raise CoinbaseRequestError(
            f"Coinbase request failed after {self.config.max_attempts} attempts"
        ) from last_error

    def fetch_product(self, received_at: datetime) -> Instrument:
        raw = self._get_json(f"/market/products/{self.config.product_id}")
        required = (
            "product_id",
            "product_type",
            "base_currency_id",
            "quote_currency_id",
            "base_increment",
            "quote_increment",
            "base_min_size",
            "quote_min_size",
            "status",
        )
        missing = [name for name in required if name not in raw]
        if missing:
            raise CoinbaseRequestError(f"product response missing fields: {', '.join(missing)}")

        capabilities = CapabilityProfile(
            venue=self.config.venue,
            product_class=str(raw["product_type"]).lower(),
            public_market_data=True,
            historical_bars=True,
            live_market_data=True,
            native={"rest_product_endpoint": True, "websocket_candles": True},
        )
        return Instrument(
            venue=self.config.venue,
            venue_instrument_id=str(raw["product_id"]),
            product_class=str(raw["product_type"]).lower(),
            base_asset=str(raw["base_currency_id"]),
            quote_asset=str(raw["quote_currency_id"]),
            base_increment=str(raw["base_increment"]),
            quote_increment=str(raw["quote_increment"]),
            base_min_size=str(raw["base_min_size"]),
            quote_min_size=str(raw["quote_min_size"]),
            status=str(raw["status"]),
            fetched_at=received_at,
            capabilities=capabilities,
            native=raw,
        )

    def fetch_candle_window(self, start: datetime, end: datetime) -> list[JsonObject]:
        raw = self._get_json(
            f"/market/products/{self.config.product_id}/candles",
            {
                "start": int(start.timestamp()),
                "end": int(end.timestamp()),
                "granularity": self.config.granularity,
                "limit": self.config.max_candles_per_request,
            },
        )
        candles = raw.get("candles")
        if not isinstance(candles, list):
            raise CoinbaseRequestError("candle response missing candles list")
        if any(not isinstance(candle, dict) for candle in candles):
            raise CoinbaseRequestError("candle response contains a non-object entry")
        return candles

    def candle_windows(self, start: datetime, end: datetime) -> Iterator[tuple[datetime, datetime]]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("candle bounds must be timezone-aware")
        cursor = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)
        window_seconds = self.config.granularity_seconds * self.config.max_candles_per_request
        while cursor < end:
            window_end = min(cursor + timedelta(seconds=window_seconds), end)
            yield cursor, window_end
            cursor = window_end

    def parse_candle(
        self,
        raw: JsonObject,
        *,
        received_at: datetime,
    ) -> tuple[MarketEvent, bool]:
        required = ("start", "low", "high", "open", "close", "volume")
        missing = [name for name in required if name not in raw]
        if missing:
            raise CoinbaseRequestError(f"candle missing fields: {', '.join(missing)}")

        event_time = datetime.fromtimestamp(int(raw["start"]), tz=timezone.utc)
        interval = self.config.granularity_seconds
        closed = event_time + timedelta(seconds=interval) <= received_at.astimezone(timezone.utc)
        payload = {
            "open": decimal_text(raw["open"], "open"),
            "high": decimal_text(raw["high"], "high"),
            "low": decimal_text(raw["low"], "low"),
            "close": decimal_text(raw["close"], "close"),
            "volume": decimal_text(raw["volume"], "volume"),
            "granularity": self.config.granularity,
        }
        event = MarketEvent(
            venue=self.config.venue,
            instrument_id=f"{self.config.venue}:{self.config.product_id}",
            event_type="bar",
            event_time=event_time,
            received_at=received_at,
            source="coinbase.public_rest.candles",
            payload=payload,
            native=raw,
            interval_seconds=interval,
            closed=closed,
            source_key=f"{self.config.granularity}:{int(raw['start'])}",
        )
        return event, closed
