# TL-003 package-to-LEAN synthetic parity contract

Owner: [issue #95](https://github.com/Loothore907/tidelab/issues/95). Contract fixed before implementation on 2026-09-26 under the owner's approved six-step action plan, including commit, push, review and gated merge. Classification: foundation integration. Consumer: a future shared historical batch backend. The development agreement was integrated in PR #100.

## Outcome and scope

One command takes a normalized strategy package, its exact synthetic intake record and invented hourly bars, runs the Python evaluator and pinned LEAN execution path, and retains both traces plus field-level discrepancies. No per-strategy C# edits are needed. Unsupported packages remain explicit outcomes. This is neither source ingestion nor a historical trial.

Reuse the existing package parser, predicates and cost identity. Instrument the current Python evaluator rather than introducing another Python replay loop. The LEAN adapter interprets the same supported expression tree independently and uses the selected source pin `88bce0fc6fe282378ee73c54cef1090d0d7a73ee`, public backtesting transaction/brokerage interfaces, fill/fee models and portfolio accounting. Do not copy expected Python fills into LEAN or manually set balances after initialization.

A deterministic test harness supplies synthetic open/close events and advances the algorithm clock. It is not a Launcher/AlgorithmManager data-feed or unattended forward-paper acceptance test. A null feed must prevent data acquisition. LEAN market-order requests, fill callbacks and resulting cash/holdings must actually occur. The model deliberately assumes immediate full fills under the declared synthetic costs; it cannot establish venue realism or liquidity.

## Frozen semantics

- Package v1: hourly spot long/cash, close/SMA/constant numeric nodes, gt/lt/and/or/not predicates, existing lag/window/depth bounds. No language expansion. Only TideLab-authored synthetic intake records are admitted by this command.
- For the cross-runtime decimal domain, positive prices are at most 1e9 with at most eight fractional digits; numeric constants have absolute value at most 1e9 and at most eight fractional digits; target fraction has at most eight fractional digits. At most 10,000 bars. Outside-domain inputs are named unsupported before execution. The general package parser's existing domain is unchanged.
- Synthetic policy is the existing `SYNTHETIC_COST`: initial cash 10,000, fee rate 0.0025, adverse price rate 0.001, quantity unit 0.00000001. Every artifact binds that policy, package, record, fixture, TideLab commit and LEAN pin.
- A bar starts at its UTC timestamp and closes one hour later. Only completed closes enter predicates. Warmup uses the existing maximum window/lag requirement. No decision is made on the final bar because there is no following executable open.
- At a signal close, a flat account may commit `cash * target_fraction` to a pending buy; a held account may commit an exit. Exit has precedence when held. There is no continuous rebalance or pyramiding.
- At the following bar open, calculate the buy quantity from the pending cash budget, opening price plus adverse rate and fee; round quantity down to the unit. A sell closes the held quantity at opening price minus adverse rate. Submit that quantity to LEAN at this open, not at signal close. This preserves the evaluator's existing budget-then-quantity semantics. A close and the following open share a UTC boundary but are distinct ordered events identified by bar index and phase.
- LEAN's fill model uses the supplied open, adverse rate and entire order quantity; its fee model charges fill notional times fee rate. LEAN processes the fill and updates its own portfolio. Any rejection, unfilled order, unexpected callback or invalid balance fails the run.
- Value remaining units at the final close; do not liquidate merely to end a fixture. Compare predicates/actions, fill index/time/side/quantity/price/fee, per-bar closing cash/units/equity and terminal values. Quantity, identity, sequence and timestamps must match exactly. Monetary decimal differences of at most 1e-18 are allowed for Python/.NET decimal arithmetic; no relative tolerance or rounded percentage comparison hides discrepancies.

## Acceptance and integration

1. Existing synthetic SMA package plus a different supported expression package traverse the same adapter without strategy-specific code. Unsupported semantics are retained and do not run LEAN.
2. Independent expected values cover a gap from signal close to next open, a complete entry/exit including fees, warmup/no-trade behavior, and an open terminal position. Compare traces as well as final balances.
3. Altered fill timing or fees must produce a nonzero comparison result with the offending field. Repeated identical executions have matching semantic traces; run timestamps/attempt identifiers may differ.
4. Input identities and an attempt record are written before the engine runs. Create a new output directory per attempt; preserve failed runs and engine logs. Interrupted attempts remain visibly incomplete. This synthetic evidence is not the real research trial registry.
5. Run the relevant Python checks and a reproducible pinned LEAN check locally and in a CI job. CI must execute the LEAN order/fill/portfolio route, not only compile C# or run the old zero-order H1 accounting check. Missing remote coverage is unmet acceptance.
6. Obtain distinct review of the exact final head, resolve findings, inspect exact-head CI, then merge within the owner's approval and verify main CI. Do not append new parsers, real-data access, external candidate selection, feed/broker recovery or an engine replacement.

The brief is falsified if matching results require hardcoding strategies, replaying Python fills into LEAN, bypassing LEAN accounting, changing declared semantics silently, or claiming wider source/runtime support than this route exercises. Record discrepancies and revise the contract openly if implementation evidence requires it.
