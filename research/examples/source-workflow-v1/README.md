# Source workflow corpus v1

Frozen TideLab-authored synthetic acceptance corpus for issue #95. No external
candidate or new rule is selected. The package files reuse the already supported
SMA, Boolean/lag and UTC calendar fixtures. Source and intake bytes are separately
hashed in `manifest.json`; normalized packages also bind the canonical intake
record digest. This avoids a circular source-file/record hash for normalized JSON.
Pine records additionally bind the exact Pine bytes. Git pins this directory to LF.

Ten ordered entries: seven normalized JSON submissions (including an exact
duplicate, malformed JSON, unsupported futures capabilities and a below-unit
sizing case), two Pine submissions (SMA supported, EMA unsupported), and one
ambiguous prose submission. Six compile, three fail parsing/capability checks,
and prose remains `needs_source_parser`. Six compiled inputs represent only three
operator structures. Neither the sizing failure nor the duplicate increases that
coverage. Pine and normalized SMA compile to equivalent job configurations.

## Independent expected signals

The truth tables were specified from these prices and UTC clocks, not exported
from the evaluator. All indices refer to `history.json`:

- Closes: `100, 101, 102, 103, 90, 50`, followed by twenty-four `100`s.
- Opens: `100, 100, 101, 102, 200, 50`, followed by twenty-four `100`s.
- Thirty hourly bars start Sunday 2026-01-04 at 20:00 UTC. A predicate uses the
  completed close, one hour after its bar's start. Bar 29 cannot place a final signal.
- SMA(3): evaluate indices 2 through 28; entry true at 2, 3, 6, 7; exit true at
  4, 5. At 8 onward the three closes equal 100, so both predicates are false.
- Boolean/lag: entry true at 2, 3, 6. Exit true at 4, 5 and 7 through 28 because
  the close is below SMA or is not above its preceding close. Equality is an exit.
- Existing calendar rule: indices 0 through 28; entry true only at 3 (Monday
  00:00 completed close), exit true only at 27 (Tuesday 00:00 completed close).

Each trace binds its source digest and this history digest. Three preceding
warmup bars honor the existing v1 package contract. Historical scoring starts at
index 3. The first SMA/logic/calendar buy fills at open 4, not the signal close.
Baseline cost buys 12.45 units at 200.2 with a 0.25% fee and a 0.03-unit lot.
SMA/logic exit at open 5; calendar exits at open 28. Cash/passive benchmarks use
the same scored window and shared costs. The tiny allocation fails explicitly at
the first fill; it is not interpreted as a successful no-trade strategy.

To add a supported input, supply a source, intake record, independent trace and
manifest entry with exact digests. No Python change is needed. The acceptance
test adds an existing Pine SMA(2) source through files/configuration alone, obtains
two more completed jobs, and correctly retains a three-structure coverage count.
