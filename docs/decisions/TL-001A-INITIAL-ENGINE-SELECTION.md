# TL-001A initial engine selection

Decision: 2026-09-24. Owner accepted the bounded LEAN recommendation for TideLab's first **synthetic historical research and local forward-paper integration**. This resolves the TL-001A engine choice; it does not install an engine runtime in TideLab, finish TL-002, clear TL-001B data rights, or authorize unattended paper or live orders.

## Selected boundary

- Pin LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` as the initial integration target. Re-evaluate any upgrade against the frozen synthetic cases before changing the pin.
- Use LEAN's public replay, managed clock/dispatch, portfolio, fill-model, and brokerage interfaces. TideLab owns versioned data and product rules, strategy and independent risk decisions, conservative cost/fill policy, portable experiment identity, and authoritative local paper reports and submission control. Keep those contracts exportable and replaceable; do not fork or patch LEAN internals to satisfy the selection.
- Limit the first integration to synthetic fixtures and one single-writer local paper authority. A real dataset, external broker, second product class, packaged release, and live operation each have separate gates.

## Evidence and tradeoff

The [joined selection gate](../evidence/TL-001A-LEAN-SELECTION-GATE.md) used the same versioned quote/product policy at LEAN's historical fill seam and a file-backed paper report. It checked a partial buy, modeled sell accounting, stale/invalid inputs, correction-before-submission, submission-before-correction, and unknown submission with zero repeated calls. The earlier [joined workflow](../evidence/TL-001A-LEAN-JOINED-PAPER-WORKFLOW.md) reached a subsequent LEAN order after controlled partial-fill correction, cancellation, restart, and reconciliation. The [H1 parity probe](../evidence/TL-001A-LEAN-H1-RISK-PARITY.md) used shared decision and risk code across historical and forward synthetic clocks. The [portable identity](../evidence/TL-001A-HYBRID-FOUNDATION-DECISION.md) records engine, code, configuration, data, cost policy, and trial provenance independently of LEAN. These are compatibility results on invented inputs, not execution realism or positive expectancy.

Pinned NautilusTrader `2.0.0rc5` remains a possible future alternative, but its tested external Python data client cannot use the backing route needed for the demonstrated replaceable recovery path. No comparably evidenced route was found in this bakeoff. LEAN has the stronger demonstrated public integration path without an engine fork. The [34–58 engineer-day estimate](../evidence/TL-001A-HYBRID-FOUNDATION-DECISION.md) for the first synthetic integration is a planning allowance, not measured effort or an expenditure authorization. Re-estimate after the first integrated slice.

## Work and gates carried to [TL-002 issue #48](https://github.com/Loothore907/tidelab/issues/48)

Build and test a durable local paper authority across processes: stable client and execution IDs; versioned orders, executions, cash and holdings; correction/reversal history; a cross-process submission barrier; crash-safe intent and journal writes; authoritative restart reconciliation; and fail-closed handling of unknown or contradictory broker outcomes. Route and reconcile a forward sell, then check cash, holdings, fees, realized result, and all partial/cancel/reject paths. Share exact strategy/risk rules between replay and forward mode, and record complete trial provenance. Test the actual supported host environments, pin the build and dependency inventory, and review notices before any distribution. The present process-local gate, controlled file reports, and projected sell are test scaffolding, not those deliverables.

TL-001B must independently establish a sufficiently deep historical and forward source with supportable local scripted research, retention, and automated-analysis rights before real-data strategy evaluation. Public real-data artifacts have a separate rights check. No live capital, private account access, paid service, or market-data acquisition follows from this decision.
