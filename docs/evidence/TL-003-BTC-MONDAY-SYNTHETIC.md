# BTC Monday: selected implementation and synthetic evidence

Owner: [#95](https://github.com/Loothore907/tidelab/issues/95). This is a selected strategy implementation through the existing package, replay, historical batch and pinned LEAN paths. The owner approved this bounded implementation, synthetic tests, distinct review and gated integration. Price access, a new snapshot and a real-data trial remain unapproved. The candidate's private policy and entry points fail before database access.

## Source and interpretation

Guglielmo Maria Caporale and Alex Plastun, *The day of the week effect in the cryptocurrency market*, [DOI 10.1016/j.frl.2018.11.012](https://doi.org/10.1016/j.frl.2018.11.012). The reviewed revision is [Brunel's 12-page publisher PDF](https://bura.brunel.ac.uk/bitstream/2438/17208/3/FullText.pdf), accepted 2018-11-17, copyright 2018; SHA-256 `4b6ed61e7150d1a4250e27636c9195d323e88218c3a51a33047f5e37737902ff`. Page 1 licenses it under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.en). Preserve that attribution and adaptation notice; independently written TideLab code remains Apache-2.0. No third-party trading code is executed or copied. Paper rights confer no market-data rights.

The source describes a Bitcoin Monday long position. Its timezone and end-of-day execution are insufficiently specified for direct replication; its fixed-lot simulation differs from this cash-budget model. TideLab explicitly chooses UTC Monday 00:00 through Tuesday 00:00, hourly completed-close decisions, spot long/cash, and fee-inclusive 25% cash sizing at the next open. This is an adaptation, not reproduction of the paper's simulation. Most annual source simulations do not establish superiority over a random comparison. [Baur et al.'s institutional abstract](https://research-repository.uwa.edu.au/en/publications/bitcoin-time-of-day-day-of-week-and-month-of-year-effects-in-retu-2/) supplies contrary persistence evidence; only its abstract/metadata was reviewed. This is a low-confidence falsification candidate, not a return claim.

The frozen private proposal is `data/strategy_intake/BTC-MONDAY-V1-PROPOSAL.md`, SHA-256 `6096a188e443dfce437c068518a3d4262fa646c802e46d7871ae699ffec053f3`. The selected v2 intake and implementation-only authority receipt are retained beside it. The public [synthetic record](../../research/examples/btc-monday-synthetic-record-v1.json) honestly identifies invented ALPHA data; it does not reclassify external market data as synthetic.

## Smallest shared extension

Package schema 4 adds the boolean `utc_calendar` predicate: ISO weekday 1-7 and hour 0-23 at the **completed bar close** (`start + one hour`). It rejects extra keys, booleans masquerading as integers, invalid slots and malformed UTC histories. No local timezone, DST adjustment, session scheduler or automatic source parser is added. Existing schema 1-3 behavior is preserved.

One completed close is sufficient, so preceding warmup is zero. The synthetic snapshot validator now permits zero; each package still checks its own required warmup before admission. At Monday 00:00 a flat strategy schedules entry at the next scored bar's open; at Tuesday 00:00 a held strategy schedules exit there. The two adjacent events can share a timestamp but have distinct close/open prices. There is no catch-up entry, final-bar signal or forced terminal liquidation. A 2024 fixture beginning flat at January 1 00:00 misses that initial Monday: its first decision is at 01:00. It has exactly 52 closed trips from January 8 through December 31.

Costs, sizing, rounding, metrics, benchmark treatment and recovery reuse the existing engine. Baseline fee/adverse rates are 0.0025/0.001; stress 0.005/0.002; initial synthetic cash is 10,000 and quantities floor to 0.00000001. Pinned LEAN `88bce0fc6fe282378ee73c54cef1090d0d7a73ee` evaluates the predicate using its actual UTC clock. The harness exercises native orders, fills and portfolio accounting, not live feed or venue behavior.

## Reproducible acceptance

```powershell
.venv/Scripts/python.exe -m pytest tests/test_btc_monday.py -q
.venv/Scripts/python.exe scripts/historical_batch.py demo --monday --output data/monday-synthetic/demo-01
```

Use a fresh output path; preserve prior attempts. The demonstration is one invented market, 8,784 hourly bars, one fixed package, two strategy jobs and four cash/passive benchmark jobs across two cost assumptions. All six jobs must complete; both strategy jobs must show 52 closed trips. Recovery validates retained artifacts without rerunning. This tests reusable execution and accounting, not scale across diverse sources or economic efficacy.

Hand-specified assertions distinguish close-clock decisions from open-clock or same-close fills, check independently calculated gap-open cash/fees, year boundaries, leap-year counts, US DST dates without UTC shifts, terminal inventory and no future-price dependence. Seven native LEAN cases include a full leap year. CI executes them alongside previous package, RSI and channel cases. Invalid clock/slot and disabled private-entry checks fail before any fill or database access.

Local verification on this implementation: 221 Python tests passed, 34 optional-runtime cases skipped on Windows; all seven focused native LEAN cases passed in WSL; two context tests passed. PR checks provide the exact-head remote regression evidence. Distinct review and merge state belong in the PR, not this pre-integration receipt.

## Next decision and limits

After distinct review and exact-head integration, the next owner decision is the frozen one-BTC, already-exposed 2024 proposal: one separately approved snapshot and six private jobs, no variants or retries, $0 acquisition/spend and a 30-minute run ceiling. It is not a holdout. Future admission must bind that exact proposal, selected intake, canonical store and finite inventory, followed by review of the concrete implementation before execution. No grant is created by this slice. Existing RSI/channel grants remain consumed and their private artifacts and canonical anchor must be preserved.

General source parsing, broad admission, timely data rights (#3) and execution authority (#48) remain independent. The proposal is a specific reviewed translation; it does not imply the platform can parse arbitrary papers.
