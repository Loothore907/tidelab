# TL-003 strategy intake boundary

Date: 2026-09-25 Alaska time. Owner: [issue #89](https://github.com/Loothore907/tidelab/issues/89). This decision defines the next foundation slice. It authorizes no candidate strategy, market-data read, trial, third-party source download, account access, order, provider outreach, or spend.

## Product intent

TideLab should be able to collect candidate strategies from research papers, source repositories, TradingView scripts, and other public or privately permitted material; preserve exactly where each idea came from; distinguish the author's claim from TideLab's interpretation; and decide whether a candidate merits implementation and research. A paper is not executable code. A published script is not automatically permitted to copy, safe to execute, or semantically equivalent after a port. An intake record is therefore **source metadata and a reviewable interpretation**, never an executable strategy or a performance claim.

The existing market-data contracts, pinned LEAN selection, experiment identity, trial ledger, H1 work, and fixed five-market screen are useful components. `StrategyManifest` and source intake are named in [architecture](../ARCHITECTURE.md) and the [research protocol](../STRATEGY_RESEARCH.md), but there is no implemented general intake or strategy interface. The two TL-003 v1 rules were hardcoded in a narrow offline screen. That screen remains a closed, separately recorded experiment; intake work does not retune or repeat it.

## Drift map: how foundation work became strategy code

| Transition | Observable signal | Missed interruption | Required interruption next time |
| --- | --- | --- | --- |
| The handoff named a candidate screen as the next slice | It called for “strategy families” and numeric rejection rules | We treated this as routine foundation sequencing | Classify the slice aloud: intake foundation, strategy implementation, or research evaluation |
| “Keep it small” became two chosen rules | Rule names, lookbacks, thresholds, sizing and exits were picked without source-backed candidates | Small trial count was mistaken for alignment with the user's intake goal | Write a source record and state why these exact candidates serve the product goal before selecting rules |
| Preregistration and issue #86 made the choice concrete | The plan froze ten market-rule trials | Preregistration controlled hindsight but did not validate the upstream choice of what to test | Complete the pre-code strategy checkpoint below; a frozen arbitrary rule is still a strategy choice |
| Code and CI succeeded | A runner and tests verified the chosen rules and accounting | Technical gates tested implementation, not whether this was the right foundation slice | Review product-intent alignment before strategy code; CI remains a later technical gate |
| Private data was opened after integration | Ten attempts were recorded in ignored local storage | The first chance to reconsider product scope had already passed | Do not open data until the source, interpretation, implementation and trial decisions are separately recorded |

This review reports the process failure without publishing any private market ranking, metric, or trial outcome.

## Intake record v1

One immutable JSON record version represents one candidate at one stage. The offline validator accepts source kinds `paper`, `repository`, `tradingview_script`, `other`, and `synthetic_example`. It stores title, author, locator, pinned source revision, optional source hash, UTC access date, an attributed claim, TideLab's separate interpretation, required data/capabilities, open questions, rights status and evidence reference. No raw third-party code, paper text, market data, or credentials enter the record. A synthetic example demonstrates the format.

Stages are `captured`, `specified`, `implementation_selected`, and `retired`. `captured` preserves source identity and an attributed claim without inventing missing rules. `specified` requires explicit entry, exit, sizing and timing semantics, data/capability needs, and no blocking open question. `implementation_selected` additionally needs a documented implementation-rights basis, an owning issue, and a reference to the exact authorization and scope. The validator checks record shape and references; it cannot establish that a license is legally sufficient or that a cited human decision actually granted authority. A changed interpretation creates a new record version and returns to `specified` for review. An append-only local registry prevents silently replacing an already registered version.

Keep source acquisition separate from intake. The initial command reads a supplied local record; it does not crawl, scrape, download, execute, translate Pine, install packages, or call a model. Real candidate records can stay under ignored `data/strategy_intake/` until their publication rights are reviewed. The repository example is TideLab-authored synthetic metadata.

## Pre-code checkpoint

Before adding or changing **strategy rules** in Python, LEAN/C#, Pine ports, or another runtime, the implementer must:

1. Name the exact source-backed candidate and record version. A source claim and TideLab interpretation must be visibly separate.
2. State the product job: intake infrastructure, a specific strategy implementation, or a research trial. “Screen,” “baseline,” “preregistration,” and “small” do not change the classification.
3. Confirm source provenance and rights for the proposed implementation, required data/capabilities, unresolved ambiguities, and the independent #3 data and #48 execution boundaries.
4. Present a concrete implementation proposal and its source record to the owner **before strategy code** if the existing session has not already authorized that exact candidate and scope. Record the decision reference. Foundation work alone grants no candidate authorization.
5. Only after that, implement with synthetic parity checks. Separately preregister trial budget, dates, costs and rejection rules before reading permitted real market prices. A manifest never grants evaluation or trading authority.

The repository guidance requires this checkpoint, and the validator can fail on missing fields or inconsistent stages. Neither can prove a human reviewed the candidate, that external terms remain valid, or that an agent obeyed the step. PR review and exact-head CI provide later evidence, not a substitute for the pre-code decision.

For issue #89, the classification is **intake foundation**. Build the record, validator, local registry, synthetic example, and instructions. Do not implement or evaluate a sourced trading rule in this slice.
