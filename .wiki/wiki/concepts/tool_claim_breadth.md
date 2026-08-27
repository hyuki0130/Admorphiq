---
type: concept
topic: routing
date: 2026-08-27
keywords: [selectivity, claim-breadth, tie-break, registration-order, specialist, routing, r101]
---

# Claim breadth — how many boards a tool says yes to

> Twenty-nine of the thirty-seven generic tools bid on EXACTLY ONE of the twenty-five sample
> boards. Three bid on all twenty-five. That split is the whole routing structure, and it is
> what breaks a tie correctly.

## Definition

A tool's **claim breadth** is the number of boards on which its `detect` returns a value above
zero. Measured on the 25 sample games at the first frame:

```
graph, world_model, deadsig              25 of 25   general searchers, correctly
29 mechanic-recovery tools                1 of 25   each claims exactly its own board
dealias, llm_goal, paint, toggle          0 of 25   stateful; they bid only mid-game
```

Nothing in between. The tool set is not a spectrum of confidence — it is a set of specialists
plus three generalists, and `detect` separates them cleanly.

## Why it matters: it is the correct tie-break

Exactly one board of twenty-five has a TIED top bid — cn04, at 0.45 between `assemble` and
`graph` — and it is the one game the LLM path loses to the LLM-free fallback. Claim breadth
settles it: `assemble` claims 1 board, `graph` claims 25, and `assemble` scores **1.0000**
where `graph` scores **0.0000**.

The reasoning generalises past this one board, which is why it is written down as a rule rather
than a patch: a specialist that declines twenty-four boards is saying something when it accepts
one, while a searcher that accepts everything says nothing by accepting. Equal numbers from
unequal evidence are not equal.

## How it is applied

Not by counting boards at runtime — the count is measured against OUR 25 and there is nothing
to count on an unseen game. It is applied through **registration order**: `default_tools()`
already puts the mechanic-recovery tools first, and both routing paths now break ties by that
order.

- `UnifiedAgent._signature_default` (the LLM-free path) already did, via strict `>` over the
  registry dict.
- `UnifiedAgent._decide`'s ranked list did NOT — it sorted ties alphabetically. On cn04
  `assemble` happens to precede `graph` in the alphabet too, so the old ordering was right by
  accident. An accident is not a rule.

## Detection heuristics (frame-only)

None — this is a property of the tool set, not of any board. It never inspects frame content.

## Falsification

Wrong if a tool appears whose claim breadth sits in the middle — say six boards of
twenty-five — because "specialist or generalist" would stop being a clean split and
registration order would stop encoding it. Re-measure breadth whenever a tool is added; the
measurement is one pass over the 25 at the first frame.

## Related

- [[../lessons/tool_selectivity_20260827]] — the rule this quantifies: a tool with no plan must
  bid 0.0, and the cost of breaking it falls on games the author never sees.
- [[../rounds/r101_llm-path-measured]] — the round where the single tie became the single loss.
