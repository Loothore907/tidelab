# Open-source and publication policy

Decision date: 2026-09-21.

## Purpose

TideLab is intended to become a completely open-source, reproducible account of whether a systematic strategy can demonstrate positive expectancy after realistic costs. Publication is part of the evidence model, not a substitute for evidence. No profitable strategy has been established.

## Project license

TideLab-authored source, tests, documentation, configurations, and original examples are licensed under the Apache License 2.0. See `LICENSE` and `NOTICE`.

Third-party dependencies retain their own licenses. A TideLab release must identify and comply with those licenses rather than implying that Apache-2.0 relicenses dependency code, market data, trademarks, or other third-party material.

## Adopt-before-build engine policy

TideLab evaluated established open-source engines before building commodity backtest, broker, portfolio, or ledger infrastructure. The [TL-001A decision](decisions/TL-001A-INITIAL-ENGINE-SELECTION.md) selects pinned LEAN for the first synthetic historical/local-paper integration. This is a bounded integration target, not an installed runtime, distribution approval, or endorsement.

The default shape is an exact-source LEAN dependency behind TideLab-owned strategy manifests, experiment records, promotion gates, reporting, data rights, paper authority, and capability checks. Use public APIs and upstream general fixes. Do not copy, rename, or permanently fork an engine by default. No custom general engine infrastructure is authorized by the selection.

Before distributing a LEAN-backed release, pin the exact source and build, include its Apache-2.0 license and applicable notices, identify any modified engine files, inspect transitive dependency licenses and build audit warnings, and keep TideLab independently branded. No LEAN binary is currently shipped.

Before distributing a NautilusTrader-backed release:

- pin and record the exact dependency version and source revision;
- preserve its LGPL notices and provide the required license texts;
- keep TideLab code and dependency code separable and replaceable;
- provide corresponding dependency source and relinking/replacement information when a container or executable conveys the library;
- include the required independent-project disclaimer and do not imply affiliation, endorsement, or support by Nautech Systems Pty Ltd or the official NautilusTrader project;
- review any upstream contribution separately because accepted NautilusTrader contributions require its contributor agreement.

## Market-data and publication rights

Public API access does not imply permission to use or republish the resulting market data for every intended purpose. Coinbase's Market Data Terms reviewed on 2026-09-21 were last updated 2026-08-07 and state broad restrictions on redistribution, display, or dissemination of market data and derived charts, analytics, and research without prior written consent. They also restrict using market data to develop, validate, benchmark, or otherwise improve specified AI, machine-learning, algorithmic, agent, and automated systems. The interaction between the stated personal/research permission and those restrictions is not resolved here. The precise application to TideLab's strategy research or any proposed artifact requires a current terms review and, where needed, written permission or legal advice.

Therefore Coinbase remains a bounded technical fixture. Until the TL-001B research-use and publication-rights decision is recorded:

- do not fetch new Coinbase market data for strategy development or automated analysis; use synthetic or otherwise permitted fixtures for TL-001A;
- do not commit or publish recorded Coinbase market data;
- do not publish downloadable Coinbase-derived backtest datasets, charts, reports, or video evidence as though public endpoint access grants redistribution rights;
- keep local validation artifacts ignored and access-controlled;
- use synthetic or expressly redistributable fixtures for public tests;
- prefer a historical and forward-data source whose retention, research, reproducibility, charting, and public demonstration rights fit TideLab's intended workflow;
- record source terms, provenance, access date, redistribution status, and any expiration or revocation risk in each experiment manifest.

Changing the research-data source may change observable market history and execution assumptions. Treat such a change as a versioned experiment input, not an invisible substitution.

## Process capture and eventual video

TideLab will capture lightweight, publication-safe evidence as work proceeds and assemble any polished video after a strategy has produced evidence worth presenting. Continuous full-session recording is not required.

Capture now:

- dated decisions and changed assumptions in governing documents;
- coherent Git history and tagged experiment identities;
- machine-readable manifests, test counts, failures, warnings, gaps, and cost assumptions;
- sanitized milestone screenshots or short recordings only when they materially demonstrate behavior;
- immutable forward-paper reports and incident records;
- every failed experiment and material change, not only the selected winner.

Never capture credentials, recovery material, personal information, private account screens, unredacted logs, or data and derived artifacts that cannot be published. Generated evidence should be reproducible from permitted inputs rather than dependent on a hidden editing narrative.

Produce later:

- select recording and editing software only after the technical stack and target format are clearer; no purchase or subscription is authorized now;
- script the narrative from the decision record, experiment registry, tagged code, and forward evidence;
- distinguish simulation, forward paper, advisory, and live results visually and verbally;
- disclose tested variants, failed hypotheses, costs, capacity limits, drawdowns, data rights, and the exact period for which a claim is supported;
- avoid promises of passive, universal, or continuing profit.

The intended video is a transparent case study and reproducibility guide. It is not evidence until the underlying versioned system, permitted data, and forward record exist.

## Public-release gate

Before the first public release or video publication, verify:

1. Apache-2.0 project notices and a third-party dependency inventory are complete.
2. Dependency licenses, source availability, trademark rules, and required disclaimers are satisfied.
3. Repository history and artifacts contain no credentials, personal information, or private account material.
4. Every published dataset, chart, report, screenshot, and recording has documented publication rights.
5. Reproduction instructions identify exact code, configuration, data acquisition, experiment, and environment versions.
6. Claims separate historical simulation, forward paper, advisory reconciliation, and actual live fills.
7. All known failed trials and material limitations are available with the selected result.

## Sources reviewed for this policy and later selection

- [NautilusTrader LGPL-3.0 license](https://github.com/nautechsystems/nautilus_trader/blob/develop/LICENSE)
- [NautilusTrader open-source licensing and contributions policy](https://nautilustrader.io/legal/open-source-licensing/)
- [NautilusTrader trademark and brand usage policy](https://nautilustrader.io/legal/trademark-policy/)
- [GNU license FAQ on LGPL linking and distribution](https://www.gnu.org/licenses/gpl-faq.en.html)
- [Pinned LEAN Apache-2.0 license](https://github.com/QuantConnect/Lean/blob/88bce0fc6fe282378ee73c54cef1090d0d7a73ee/LICENSE)
- [Coinbase Market Data Terms of Use](https://www.coinbase.com/legal/market_data)

These links are point-in-time evidence. Re-check the exact dependency license, trademark policy, provider terms, and proposed artifacts before distribution.
