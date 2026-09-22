---
name: tidelab-context
description: Find TideLab's current handoff, project map, decisions, evidence, and code references through bounded, source-linked repository retrieval. Use for TideLab orientation, long-horizon handoffs, "what is current", roadmap or rights questions, and locating relevant implementation without rereading the whole repository.
---

# TideLab context

Use the checked-in context command for one bounded orientation, then open the exact source it points to.

Run from the TideLab checkout or active worktree:

- `node scripts/tidelab-context.mjs current` — branch, committed head, upstream divergence, dirty count, and handoff marker.
- `node scripts/tidelab-context.mjs map` — the maintained [project map](../../../docs/CONTEXT_MAP.md).
- `node scripts/tidelab-context.mjs search-docs "<short query>"` — repository documentation.
- `node scripts/tidelab-context.mjs decision "<short query>"` — governing plans and recorded choices.
- `node scripts/tidelab-context.mjs evidence "<short query>"` — dated local evidence.
- `node scripts/tidelab-context.mjs impact "<path-or-symbol>"` — bounded lexical references, not a dependency graph.

Add `--json` only when structured output helps. A no-result query is not proof of absence: shorten it once, then use a targeted tracked-file search or open the known document. Read `AGENTS.md`, the current `HANDOFF.md`, and the controlling source before changing scope.

The command reads regular-file blobs at one committed `HEAD`; staged and unstaged edits are excluded. It cannot establish fresh GitHub reviews/CI, provider permission, data rights, live account state, or execution authority. Check those separately. Never put credentials, private account data, absolute local paths, or URLs into a query. Do not treat an accepted plan, a passing test, or a retrieved snippet as approval for trading or publishing restricted market data.
