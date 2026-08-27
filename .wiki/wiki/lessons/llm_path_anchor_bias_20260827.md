---
type: lesson
topic: llm-routing
date: 2026-08-27
keywords: [llm, routing, anchor-bias, tool-selection, gemma4, fallback, r101]
---

# The model still picks the familiar tool after being shown the right one

> Three games the signature fallback conquers at 1.0000 scored 0.0000 through the LLM path, because the model named `graph` on all three.

## Symptom

With `HARNESS_MODEL=gemma4:26b` driving the loop:

```
game    LLM path            signature fallback
ar25    graph, 0 levels     reflect_cover, 1.0000
ft09    graph, 0 levels     stencil,       1.0000
sb26    graph, 0 levels     subroutine,    1.0000
```

## What was ruled out first

Two real defects were found and fixed before this measurement, and both had to go before the
result meant anything:

* `context.py` sliced `tool_selector.md` into per-tool blocks using **eight literal tool names**,
  so the twenty-two rule-recovery tools built that day were invisible to the model;
* `_relevant_tools` then RANKED the same eight literals, so even after every tool gained a
  `tool_selector.md` entry the parser found 26 blocks and the ranker passed 8.

Both are fixed — the menu is `default_tools()` and the ranking is each tool's own `detect`.
Verified on the measurement box itself: for ar25 the menu now leads
`['reflect_cover', 'code', 'graph', ...]` and the block for the right tool is inside the 5,849-char
context the model receives.

**So the model was shown the right tool, first, with its observable signature, and named the
general searcher anyway.**

## Root Cause

Anchor bias on a familiar name — the same failure this project measured across rounds R5–R11 with
an 8B model, where four rounds of wiki work failed to dislodge `bfs_state_space` / `click_rare`,
removing those two names merely moved the anchor to the next-most-familiar BFS-shaped name, and
the tool only ever ran once the whitelist was cut to a SINGLE entry. It reproduces at 26B.

## Prevention / what to try next, in order

1. **Constrain the decode.** The pick is already enum-shaped; binding it to the ranked menu's top-k
   (say 3) rather than to all 26 names removes the anchor's room without hiding tools.
2. **Ask for a signature match, not a name.** The model is good at "which of these observable
   signatures does this board show" and bad at "name a tool"; the tool then follows from the
   signature deterministically.
3. **Let the bid decide and use the model for what it is good at** — the fallback already routes
   correctly on all 25 games. The model's value in the deployed design is patching and combining
   tools on HIDDEN games, not out-picking a detector on games where the detector is right.

⛔ Do NOT respond by cutting the whitelist to one name again. That is what R11 did; it made the
routing measurement meaningless because there was nothing to choose between.

## Falsification

If the model picks the ranked-first tool on these three games under a constrained decode, the
diagnosis is anchor bias and the fix works. If it still picks the searcher, the problem is the
prompt or the signature vocabulary, not the menu.

## Related

- [[harness_owns_the_routing_20260827]] — the two hardcoded menus this had to get past first.
- [[../rounds/r101_tool-development]] — the round; every other number on it is the fallback path.
