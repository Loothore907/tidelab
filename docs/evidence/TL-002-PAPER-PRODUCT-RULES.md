# TL-002 synthetic paper product-rule gate

Issue: [#48](https://github.com/Loothore907/tidelab/issues/48). Scope: TideLab's local synthetic paper intent barrier; no exchange adapter, account, market data, or trading authority.

Each newly prepared paper intent now requires an explicit versioned `PaperProductRules` snapshot for its instrument. The gate rejects a quantity off the base increment, a limit price off the quote increment, a quantity below the base minimum, or a notional value below the quote minimum **before** persisting an intent. The full canonical rule identity is stored beside the intent; replay with changed values, even under the same revision label, is rejected. A claim after restart requires the same rule identity and revalidates the stored terms. Existing unversioned database rows migrate to a fail-closed sentinel and cannot be claimed or silently relabeled.

The fixed LEAN buy/sell join supplies invented rules for `synthetic:TL001ASYN`, and its direct transactional sell insertion records the same identity. This checks a concrete control boundary in the existing synthetic route. It does not verify venue metadata, quote-currency rounding, dynamic status changes, fees, portfolio sizing, or a general runtime reconciliation path. No real instrument rule is inferred from the fixture.

Local verification: Python suite 35 passed, 1 optional Nautilus import skip. Tests cover bad increments/minima, changed rule identity and stored terms before a claim, legacy-row refusal, restart and cross-process claim behavior, and the unchanged synthetic buy/sell join. Remote exact-head CI must be checked separately.
