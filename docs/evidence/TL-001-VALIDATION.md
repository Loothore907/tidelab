# TL-001 local validation

Validated 2026-09-16 against public Coinbase Advanced Trade endpoints. This is local engineering evidence, not remote CI, unattended uptime, account eligibility, execution quality, or strategy performance.

## Environment

- Branch: `feat/tl-001-market-data`
- Python: 3.12.14
- SQLite: 3.53.1
- pytest: 9.1.1
- websockets: 17.1
- Credentials/account access: none
- Incremental service spend: $0

## Automated checks

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Result: 15 tests passed. Covered timestamp/decimal validation, stable identifiers, configuration validation, bounded retries, runtime product-rule normalization, closed/incomplete bar classification, request windowing, rejection of out-of-window upstream data, interrupted-ingestion recovery, restart idempotency, gap/freshness reporting, WebSocket parsing, and connection-sequence gap calculation.

## Read-only integration smoke

Command:

```powershell
.\.venv\Scripts\python.exe -m tidelab `
  --config artifacts\config.validation.toml `
  smoke --hours 24 --stream-seconds 10
```

Observed UTC window: `2026-09-15T09:00:00Z` through `2026-09-16T09:00:00Z`, end exclusive.

- Public product status: `online`, product class `spot`.
- Point-in-time rules: base increment/minimum `0.00000001`; quote increment `0.01`; quote minimum `1`.
- First synchronization: 24 closed hourly bars inserted.
- Restart synchronization: zero inserted and 24 duplicate attempts recognized.
- Report: 24 expected, 24 stored, zero missing, latest close `2026-09-16T09:00:00Z`, not stale under the configured two-hour threshold.
- Public WebSocket: 14 messages in 10 seconds, including 10 heartbeat messages and 101 five-minute candle observations; zero missing connection sequence numbers.

The REST response contained 350 candle objects for the bounded request; TideLab admitted only the 24 events inside the requested interval. The public WebSocket candle message contained a snapshot/update collection, which accounts for more normalized candle observations than wire messages.

## Historical depth probe

A separate fresh database requested 720 closed hourly intervals from `2026-08-17T09:00:00Z` through `2026-09-16T09:00:00Z`. The client made three bounded requests of at most 350 candles each.

- Upstream objects received: 1,050.
- Bars admitted after enforcing each individual request window: 349.
- Requested intervals still missing: 371.
- Observed contiguous coverage began at `2026-09-01T20:00:00Z` and ended at `2026-09-16T09:00:00Z` (end exclusive).

The unauthenticated endpoint returned recent candles even for older requested windows. TideLab rejected those out-of-window responses, reported the missing intervals, and did not fabricate history. This establishes only the observed recent 349-hour depth from this machine at this time. It does not establish enough history for TL-003.

## Restart and failure behavior

- Closed bars have deterministic identifiers and a database uniqueness constraint, so a repeated sync records duplicate attempts without silently creating a second bar.
- REST retries are bounded and exponentially delayed for transport failures, HTTP 429, and server errors. Other HTTP failures stop immediately.
- Ingestion and stream sessions end as `complete` or `failed` with counts and an error summary.
- WebSocket sequence continuity is evaluated over the connection-wide sequence, including interleaved subscription, candle, and heartbeat messages.

## Known limits

- A ten-second WebSocket test proves a reachable public feed and parsing/storage path, not long-duration availability or reconnect endurance.
- Public REST responses may be cached or incomplete. TideLab sends `Cache-Control: no-cache`, detects requested-window gaps, and does not fabricate bars.
- The observed public REST depth was 349 recent closed hourly bars. A different authorized source or a sufficiently accumulated local archive is required before serious historical strategy evaluation.
- Coinbase WebSocket candles are five-minute live updates. They are stored as non-closed observations and are not substituted for strategy-ready closed hourly bars.
- Product rules and availability are point-in-time data. They must be refreshed and do not prove account eligibility, fees, or permission to trade.
- No strategy, paper broker, order submission, credentials, or live-capable adapter exists in TL-001.
