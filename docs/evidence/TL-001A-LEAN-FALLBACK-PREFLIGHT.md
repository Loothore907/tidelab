# TL-001A LEAN fallback preflight

Status: source/API screen on 2026-09-22 Alaska time, **not** an executable LEAN bakeoff or adoption. Issue [#2](https://github.com/Loothore907/tidelab/issues/2) stays open.

## Why this comparison is now due

Pinned NautilusTrader 2.0.0rc5 restored a closed order with its native sandbox client and Redis backing, but rejected a backed `LiveNode` that registered a custom Python data client. The [upstream adapter guide](https://nautilustrader.io/docs/latest/developer_guide/python_adapters/) identifies this as a current constraint in both launch modes. TideLab requires replaceable venue adapters and durable recovery; treating the native-only sandbox result as proof for an external Python adapter would be unsound. This is the bounded fallback trigger in the roadmap, not a decision to fork Nautilus or build a new engine.

## LEAN evidence screened

- Source inspected at [QuantConnect/Lean commit `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`](https://github.com/QuantConnect/Lean/commit/88bce0fc6fe282378ee73c54cef1090d0d7a73ee), current when checked. The repository states Apache-2.0 licensing. No LEAN code or data was copied into TideLab.
- LEAN documents [local custom data files](https://www.quantconnect.com/docs/v2/lean-cli/datasets/custom-data) through `BaseData`/`PythonData` and a local-file source. This is a plausible synthetic history input, not proof that TideLab's market-event contract maps cleanly or that a live synthetic feed works.
- Its [brokerage extension guide](https://www.quantconnect.com/docs/v2/lean-engine/contributions/brokerages) exposes `IBrokerage`, data queue, history, fee, and model roles. The [brokerage setup source](https://github.com/QuantConnect/Lean/blob/88bce0fc6fe282378ee73c54cef1090d0d7a73ee/Engine/Setup/BrokerageSetupHandler.cs) loads existing open orders, holdings, and cash from a brokerage. That is a candidate reconciliation seam, **not** evidence of correct process-loss behavior for a TideLab adapter.
- The official [local LEAN CLI paper-trading instructions](https://www.quantconnect.com/docs/v2/lean-cli/live-trading/brokerages/quantconnect-paper-trading) state a QuantConnect login and paid organization tier are required. TideLab has no authorization for paid services or account creation, so this comparison must use a free, direct source/launcher path or remain a source review. No CLI deployment was attempted.
- The host has a .NET runtime but no SDK; no LEAN build or synthetic run was performed. The GitHub releases API's `latest` tag was from 2017, so that label was not used to choose a modern executable candidate.

## Executable comparison required before an engine decision

Pin a specific LEAN source revision and run a minimal synthetic, local-only historical fixture without a QuantConnect account or paid dataset. Then test a forward-paper process with a synthetic brokerage that reports the same pending order after restart, proving order/account reconciliation and no blind resubmission. Compare TideLab's contract mapping, shared strategy semantics, accounting, evidence export, Windows/Linux operation, license/distribution duties, and implementation burden against Nautilus. Keep real venue adapters, credentials, live orders, and restricted market data out of the probe. Until then LEAN is a documented fallback candidate, not a passed alternative.
