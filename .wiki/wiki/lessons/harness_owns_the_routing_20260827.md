---
type: lesson
topic: harness-routing
date: 2026-08-27
keywords: [routing, detect, level-up, signature-default, tool-set, r101]
---

# The biggest losses were in the harness, not in any tool

> Two routing defects cost more than every tool improvement of the day combined, and no tool author could have found either — one was found by a tool author measuring MY code.

## Symptom

Tools that solved their game outright scored almost nothing through the harness. One cleared
ar25 8/8 with `GameState.WIN` under its own probe and scored **0.0278** — exactly one level of
eight — in the full-25 run. The same gap appeared three times in one session, on three different
tools, and was misread each time as "the tool needs work".

## Root Cause 1 — a level-up handed the board away

`_reset_level()` cleared `_current`, so the next action forced a re-decide. That decision is made
on the TRANSITIONAL frame, where the tool that just solved the level frequently scores 0: the next
board has not been drawn yet. Traced step by step on ar25 — the tool cleared level 1 in 16 actions,
the general searcher took the board on the level-up, and spent the remaining 384 actions clearing
nothing.

**Clearing a level is the strongest evidence of fit that exists. It must outrank a `detect()` score
taken mid-transition.** With the tool kept, the same run clears 8/8 in 269 actions. A tool that
then stalls is still retired by the normal stall path, so nothing is lost.

## Root Cause 2 — a bid of 0.0 won the board

`_signature_default` started at `best = -1.0`, so `0.0 > best` held. A board that **no** tool
claimed went to whichever tool was FIRST in registration order — meaning every tool added silently
re-assigned games none of them bid on. Found by the author of a tool that had measured **zero bids
across 9,600 frames** of foreign games and still saw one of them change hands when it registered.

With nobody claiming the board, the general searcher is now the deliberate fallback.

## Root Cause 3 and 4 — the model's menu was hardcoded, twice

Found only when the LLM path was finally exercised on a GPU-less box, at the user's insistence.
Everything above was measured on the **LLM-free fallback**, where routing is by signature; the
deployed path asks a model to name a tool.

* `context.py` listed **eight tool names as literals** to slice `tool_selector.md` into per-tool
  blocks. The eighteen rule-recovery tools built the same day were not among them, so the model
  was never told they exist.
* `_relevant_tools` then scored **the same eight literals** to decide which blocks fit the board.
  After `tool_selector.md` gained an entry per tool the parser found **26 blocks and the ranker
  still passed 8**.

Between them the model was structurally unable to name the tool that clears a game 8/8 — on ar25
it picked the general searcher and the code path and scored one level, while the signature fallback
picked the right tool and scored 1.0000.

**Fix**: the menu is `default_tools()`, and the ranking is each tool's OWN `detect` — the same
number the fallback routes on, so the model is ranked by evidence the harness already trusts.
Verified: ar25's menu now leads with the right tool and its block is in the 5,849-char context.
The fallback path is byte-identical (0.2143, all 25 games unchanged).

⛔ **A tool that is registered must be NAMEABLE.** Two menus in one file drifted from the registry
without anything failing, because the fallback never reads them. Any list of tool names that is
not derived from the registry is a defect waiting for the day someone runs the model.

## What it was worth

```
full 25, generic tools alone, frozen snapshot, registry unchanged
  0.1525 -> 0.2143
  ar25  0.0278 -> 1.0000   conquered
  sb26  0.8334 -> 1.0000   conquered
  re86  0.0278 -> 0.2685
  wa30  0.0223 -> 0.1333
  sc25  0.1905 -> 0.2440
no game regressed
```

## The three ways a probe and the harness disagree

By the end of the round all three had been measured, and they need different fixes:

| # | symptom | cause | who can see it |
|---|---|---|---|
| 1 | the tool never acts | it bids too LOW on its own board (0.35 lost every comparison) | the integrator, from a full-25 run |
| 2 | it clears level 1 and then stops | the harness took the board on the level-up | the integrator, by tracing which tool acted |
| 3 | **it holds every step and still clears less** | **the harness's execution contract differs from the probe's** | only a trace of the real loop |

Type 3 measured on m0r0: the tool's own probe cleared **4 levels in 148 actions**; the harness gave
it **all 500 steps** and it cleared **2**. Not a routing loss — it owned every turn and did worse
with three times the actions.

Where that difference lives, in the order worth checking:

* **`reset()` on level-up.** The harness resets every registered tool at a level transition. A tool
  that learned its controls on level 1 loses them and re-probes from scratch on every level — which
  costs actions AND depth at once, exactly the pair of symptoms seen.
* **What `observe()` receives.** The harness feeds transitions only to the tool that chose the
  action, and it feeds a BOARD-level changed flag with edge chrome excluded — not a raw frame diff.
  A tool that learns from something the harness never hands it plans on a different model.
* **One step per turn.** `propose` is re-entered after every action, so a plan that assumes it runs
  uninterrupted can be undone by replanning.

⛔ **A tool must be built against the HARNESS's contract, not its probe's.** The probe is a
convenience for its author; the harness is what is scored. An author looking only at their own
probe cannot see type 3 at all, so the integrator has to trace the real loop for every tool whose
probe and harness numbers disagree.

## When to stop letting an author tune a tool

One tool regressed its own game **four times** in this round, each time after its author's probe
showed more levels:

```
committed file : ls20 6 levels in the harness
author's edits : 4 -> 2 -> 3 levels, and -0.4286 on one full-25
```

Each time the committed version was kept, and each time that was right. The pattern is not
carelessness — the author is optimising against a probe that drives the tool DIRECTLY, while the
harness resets it at every level-up, feeds it only its own transitions, and re-plans after every
action. Those are different problems, and solving the first can unsolve the second.

⛔ **After the second such regression, change the author's instrument, not their code.** The brief
becomes: run `scripts/harness_probe.py`, make ONE change, re-run it, keep only if the level count
rises, revert yourself otherwise. If it regresses again after that, stop taking edits to that tool
— it is at a local optimum the probe cannot see past, and further tuning is a net loss.

## Prevention

- When a tool's standalone probe and its harness score disagree, suspect the ROUTING first. A
  probe drives a tool directly; the harness routes by `detect`.
- Selectivity and ownership are properties of the tool SET. No agent can see them, so a fan-out
  must reserve them for the integrator — [[../parallel_build_protocol]].
- ⛔ Take a peer's measurement seriously and CHECK IT. The `best = -1.0` defect arrived as a claim
  from a subordinate agent about the parent's code, and it was correct.

## Falsification

If a routing change is worth nothing, it will show as a byte-identical full-25. The zero-bid fix
did exactly that (0.1525 -> 0.1525, all 25 identical) and was kept anyway, because "first in the
dict wins" is an accident of ordering rather than a decision.

## Related

- [[tool_selectivity_20260827]] — the mirror image: a tool bidding on a board it cannot solve.
- [[moving_target_measurement_20260827]] — why the baselines in this round needed freezing.
- [[../rounds/r101_tool-development]] — the round.
