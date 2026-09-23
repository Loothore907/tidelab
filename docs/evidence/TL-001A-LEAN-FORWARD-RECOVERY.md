# TL-001A LEAN synthetic brokerage restart probe

Status: bounded positive **startup reconciliation seam** on 2026-09-22 Alaska time. Issue [#2](https://github.com/Loothore907/tidelab/issues/2) remains open. This does not adopt LEAN or establish a complete forward-paper runner.

## Method

The unmodified LEAN source at [`88bce0fc6fe282378ee73c54cef1090d0d7a73ee`](https://github.com/QuantConnect/Lean/commit/88bce0fc6fe282378ee73c54cef1090d0d7a73ee) was built with the isolated .NET 10.0.401 SDK. TideLab's `scripts/lean_fallback/TideLabForwardRecoveryProbe.cs` was copied into LEAN's test project, and the TideLab runner was built against that project. No LEAN source was changed, copied into TideLab, or patched. The test uses LEAN's real `BrokerageSetupHandler`, `BrokerageTransactionHandler`, and `QCAlgorithm`, with a mock `IBrokerage` reading a durable TideLab-authored **synthetic** report. The synthetic symbol `TL001ASYN` is only a test identifier; no market data was requested.

The first process wrote and synced a report with broker ID `TL001A-BROKER-ORDER-1`, one `Submitted` limit buy for 1 at 90, USD cash 10,000, and zero holding. LEAN setup registered that pending order. The process then called `Environment.Exit(23)` without disposing the setup or transaction handler. A second process, with no LEAN state carried over, read the same report and ran setup again. The broker report was the authoritative state for this test, not an engine snapshot or a replayed signal.

## Observed

- LEAN's first setup and fresh-process setup each called the broker's `GetCashBalance`, `GetOpenOrders`, and `GetAccountHoldings` once, and registered one `Submitted` order with the same broker ID.
- The second process showed USD cash `10000` and holding `0`, matching the synthetic brokerage report. `PlaceOrder` was called zero times in both processes. The local LEAN order ID was reallocated (`1` here); continuity was checked by broker ID.
- The seed process logged `phase=seed status=pending ... new_submissions=0` and terminated without the normal teardown trace. The restore process logged `phase=restore status=pending ... new_submissions=0` and returned success.
- The isolated test-project build completed with 0 errors. It emitted upstream package audit warnings, including `NU1903` and `NU1904` for packages in the pinned LEAN dependency graph. These need separate review before any adoption or distribution.

The NUnit runner's assembly-wide Python initialization crashed in this WSL environment before the focused test ran, so the TideLab standalone runner invokes the same built test method directly. An initial direct run failed because the process working directory did not point to LEAN's local `Data` folder; running from `Launcher/bin/Release` resolved it. The first implementation also exposed the need for a mock live data feed during `PostInitialize`. Those setup failures preceded the successful two-process result; they are not evidence of recovery.

## Reproduction

In a separate LEAN checkout at the pinned commit, copy the three `TideLabForwardRecovery*` files from `scripts/lean_fallback/`: the probe `.cs` to `Tests/Engine/Setup/`, and the runner `.cs` and `.csproj` to a new `TideLabForwardProbe/` directory at the LEAN root. Build `TideLabForwardProbe/TideLabForwardRecoveryRunner.csproj` in Release with .NET 10. Run the runner from `Launcher/bin/Release` with `TL001A_REPORT_PATH` set to a **new** local temporary file path and `TL001A_PHASE=seed`. Confirm its marker and forced nonzero exit. Then run the same runner in a new process with the same report path and `TL001A_PHASE=restore`; expect a success exit and the restore marker. Keep the temporary report local and remove it after inspection. No account, credential, paid CLI, exchange connection, real data, or live order is involved.

## Limits and next gate

The mock brokerage reads a fully consistent report. This establishes that the pinned LEAN **setup path** can rebuild a pending order and cash/holding state from broker-provided reports after process loss without submitting a replacement order. It does not prove that LEAN itself durably persisted the state, that a real/paper brokerage can produce complete reports, or that the direct Launcher can run this custom brokerage unattended. It also does not test a fill during downtime, partial fills, canceled/rejected orders, broker-ID collisions, stale or contradictory reports, fee/cost accounting, strategy timer parity, or downstream order-event reconciliation. An absent or ambiguous authoritative report must block new submission; this probe contains no submit path and does not yet exercise that policy in a full runner.

Next: compare this startup seam with Nautilus's pinned external-Python-client/backing gap, then implement a small synthetic full forward-paper loop with a change in brokerage state during downtime and explicit ambiguous-report fail-closed behavior. Keep issue #3's data-rights gate independent. Neither historical replay nor this setup result justifies engine adoption.
