# TL-001A joined synthetic selection gate

Status: bounded engine-selection evidence for [issue #2](https://github.com/Loothore907/tidelab/issues/2), 2026-09-24 Alaska time. Pinned LEAN source `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` remains a candidate. No real market data, account, credential, paid service, external broker, or live order was used. This result does not establish strategy profitability or data rights.

## Question and frozen inputs

Can the same explicit conservative fill rule serve LEAN's historical fill seam and a file-backed local paper report, preserve sell-side accounting, and make a correction or unknown submission block a new order in the joined recovery route? This is the final bounded test named by the [hybrid foundation review](TL-001A-HYBRID-FOUNDATION-DECISION.md). The earlier [joined paper workflow](TL-001A-LEAN-JOINED-PAPER-WORKFLOW.md) already tested initial LEAN submission, partial execution after a forced process exit, correction and ledger reconciliation, cancellation, and a subsequent LEAN order. This follow-up runs those phases on each branch before testing the policy and correction gate.

The checked-in TideLab-authored synthetic [rules](../../scripts/lean_fallback/fixtures/selection_rules_v1.json) (`SHA-256 BB43F07F0FE7C60E88E429C278534BE34A9D136356096E13298083067CADAD16`) and [quote](../../scripts/lean_fallback/fixtures/selection_quote_v1.json) (`SHA-256 579886565D249E757860C32797042FEDC78A9FA7F46E4F1AC83665D2BB0FEE5C`) are read by each fresh process. The LF-normalized fill policy source SHA-256 is `D28EF997B34C11323380C078654297A52F9D359487BB84784A65960EBEEC5732`. The [portable identity exporter](../../scripts/tl001a_export_selection_identity.py) hashes these actual inputs, the policy source, the pinned engine revision, and the current committed TideLab revision into a new local JSON manifest. It requires a clean checkout and preserves existing files. This identity is a compatibility trial, not a performance experiment or a claim that synthetic prices are executable liquidity.

Run from this repository with the pinned isolated LEAN checkout and .NET 10 binary:

```bash
TL001A_SELECTION_ONLY=1 bash scripts/lean_fallback/run_forward_recovery_probe.sh \
  /home/loothore907/.cache/tidelab-lean-probe/Lean \
  /home/loothore907/.cache/tidelab-lean-probe/dotnet/dotnet
```

After committing the exact tested source, export a local identity (the output directory is ignored by Git):

```powershell
.\.venv\Scripts\python.exe scripts/tl001a_export_selection_identity.py artifacts/tl001a-selection-identity.json
```

## Observed results

The isolated LEAN build completed with **0 errors**, and all selection phases exited as expected. The pinned upstream dependency tree emitted package audit and SDK warnings, which remain an upgrade/release review item. The test ran in WSL; repository CI does not compile or execute this C# probe.

| Branch | Observed check |
| --- | --- |
| Historical/paper rule | LEAN's public fill model produced the same initial partial buy as the TideLab paper policy: `0.4 @ 89.91`, fee `0.035964`, `0.6` unfilled. The paper execution was later authoritatively corrected to `89.92`, fee `0.035968`; revision and account equality were checked rather than presented as exact original-price parity. |
| Sell-side arithmetic | The same rule modeled a full sale of the recovered `0.4` holding at `89.79`, fee `0.035916`. From the corrected buy account this yields zero holding, `9999.876116` USD cash, and `-0.123884` USD realized result on invented prices. LEAN's historical fill model returned the matching signed sale, price and fee. This is an accounting projection; no forward sell order was submitted. |
| Absent or invalid execution inputs | Stale quote and less than one displayed lot held with zero historical fill quantity. An invalid order lot was rejected. The paper report remained unchanged, and no next order was submitted. |
| Correction wins before submission | A pending correction marker was durably written through the same local gate that checks the joined report, ledger and intent. The next attempt returned `BLOCK_CORRECTION_PENDING`; `IBrokerage.PlaceOrder` was called zero times. |
| Submission enters first | The correction writer waited while the gate held the broker callback. The accepted mock order was written once, then the correction marker was published. Subsequent attempts held on the pending correction; no second submission occurred. |
| Unknown submission result | The mock broker returned a non-success result. The source persisted an unknown marker and a repeat attempt made zero additional `PlaceOrder` calls. No success was inferred from the missing acknowledgement. |

The original joined route was rerun after the new gate: it still submitted one next LEAN order after reconciliation, adopted it on restart without resubmitting, and blocked a wrong cash report. The local Python suite passed **17 tests with one optional NautilusTrader skip**; these Python checks do not replace the WSL C# run.

## Interpretation and remaining work

This closes the *synthetic compatibility question* for the initial hybrid shape: LEAN can supply replay/dispatch, portfolio and public fill/brokerage seams while TideLab owns a replaceable conservative policy, evidence identity and local paper authority. The tested responsibilities remain within the [working selection boundary](TL-001A-CONSERVATIVE-PAPER-FILL.md); no engine source was patched or forked. Combined with the existing H1 historical/forward decision-parity evidence, this makes **pinned LEAN the recommended initial engine** for TL-002 planning. NautilusTrader's pinned external-Python-data-client/backed-recovery gap remains the material alternative blocker.

The source gate uses a process-local lock and file markers. It does not enforce a cross-process lock, resolve an incomplete correction or unknown broker outcome, prove atomicity with an external brokerage, or implement a production journal. The sell is a modeled closure, not a routed and reconciled forward sell. The historical cost check uses LEAN's public fill-model seam, not a complete H1 Launcher performance run. TL-002 would need to implement and test these runtime details before unattended local paper operation. A real broker, different product class, and live capital require later separate gates. Package warnings must be inspected before any bundled release.

Formal selection on issue #2 remains an **owner architecture decision**. The proposed decision is to pin LEAN to this source revision for the first synthetic historical/local-paper integration, budget the [34–58 engineer-day planning range](TL-001A-HYBRID-FOUNDATION-DECISION.md), keep the TideLab-owned interfaces replaceable, and put the named production-quality paper tasks in TL-002. TL-001B must independently clear a historical/forward dataset for actual research; no market-data use or publication permission follows from this engine result.
