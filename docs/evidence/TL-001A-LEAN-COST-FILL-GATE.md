# TL-001A synthetic cost and displayed-liquidity gate

Status: bounded evidence for [issue #2](https://github.com/Loothore907/tidelab/issues/2), 2026-09-23. Neither engine is adopted. No market data, account, credential, or live order was used.

## Question and reproduction

Can pinned LEAN's default equity market fill be accepted when the invented displayed ask size is smaller than the order? Run `TL001A_COST_FILL_ONLY=1 bash scripts/lean_fallback/run_forward_recovery_probe.sh <pinned LEAN checkout> <dotnet 10 binary>`. The runner pins LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, copies only TideLab-authored probe code into that isolated checkout, builds it, and invokes `TideLabCostFillProbe` once. Repository CI checks the script but does not compile the C# probe.

## Observed synthetic case

The fixture is a US-equity test symbol, not a crypto or other product claim. At a synthetic minute quote, bid is 100.00, ask is 100.20, and displayed size on each side is 0.4 units. A one-unit market buy uses LEAN's `EquityFillModel` with `ConstantSlippageModel(0.001)`; its last trade is 100.10. The pinned model returned **Filled, quantity 1, price 100.3001**: ask 100.20 plus 0.1001 slippage calculated from the last trade. It did not cap quantity at the displayed 0.4. A separately configured `ConstantFeeModel` returned 0.1003001 USD for this fixture, numerically 0.1% of the observed notional. The constant model does not establish a dynamic percentage fee rule. The probe asserts every number and emits `decision=HOLD_OPTIMISTIC_FULL_FILL`.

This is an engine behavior observation, not a prediction of market execution. Pinned LEAN's `EquityFillModel.MarketFill` explicitly assumes the order completely filled after finding a price; its configurable slippage and fee surfaces do not impose a liquidity limit. The existing NautilusTrader synthetic quote-size case filled 0.4 at 100.20 and the 0.6 residual one tick higher at 100.21. Both defaults infer execution beyond the displayed size, by different rules. The Nautilus result is recorded in [the bakeoff](TL-001A-ENGINE-BAKEOFF.md).

## Decision consequence

LEAN remains the stronger candidate for replaceable brokerage/restart integration and shared synthetic H1 strategy/risk behavior, but its default market fill cannot be TideLab's realism claim. Adoption still requires a versioned, product-aware cost and fill contract with explicit bid/ask source, fee schedule and currency, lot/tick rounding, partial and missed fills, rejection and stale-quote behavior, sell-side accounting, and reconciliation. The contract must apply consistently to historical research and forward paper operation while preserving venue-native rules; synthetic models cannot validate real fill probabilities. A conservative model may leave the unobserved 0.6 pending or mark outcome unknown according to the selected mode, but this probe does not implement that model.

Integration work comparison: LEAN exposes fill, slippage, and fee models and has the stronger tested forward/restart path, so TideLab would supply the product capability rules, conservative models, broker authority and ledger, and parity tests. NautilusTrader also exposes simulation model controls, but the pinned external Python data-client plus cache-backing incompatibility still requires an evidenced public recovery path or TideLab-owned persistence. Neither engine removes TideLab's research cost assumptions; neither is adopted. Next specify the shared product-aware cost/fill contract, then test at least one conservative partial/missed/rejected path against both historical and forward paper accounting. Keep [TL-001B issue #3](https://github.com/Loothore907/tidelab/issues/3) separate.

Local focused runner: build succeeded with zero errors; upstream dependency audit warnings remain in the pinned LEAN checkout. The case printed `TL001A_LEAN_COST_FILL bid=100 ask=100.20 displayed_ask=0.4 order=1 slippage=0.1pct fill=1@100.3001 fee=0.1003001 fee_model=constant decision=HOLD_OPTIMISTIC_FULL_FILL`. No order was sent to a brokerage.
