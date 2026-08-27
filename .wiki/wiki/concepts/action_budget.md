---
type: concept
instantiating_games: [AR25, CN04, DC22, FT09, KA59, LP85, LS20, RE86, S5I5, SP80, SU15, TU93, VC33, WA30]
detection_frame_only: yes
---

# Action Budget

> A per-level cap on actions that ENDS THE GAME when exceeded — thirteen of the twenty-five sample games declare one, as low as 13 actions, and it is drawn on screen.

## Definition

A level may carry a maximum number of actions. Spending it calls `lose()`, which sets
`GameState.GAME_OVER` (`arcengine/base_game.py:301`). A following `RESET` with a non-zero action
count is a **level** reset, so cleared levels survive — but the scorer keeps counting: in
`scripts/score_efficiency.py` `action_count_this_level` accumulates ACROSS a game-over restart and
is zeroed only when a level is actually completed. So over-exploring does not merely fail a level,
it converts an eventual clear into a score of approximately zero.

Declared in each game's own level data under names the designers chose — `StepCounter`,
`MaxSteps`, `steps`, `kCv`, `StepsDecrement`. Read them with
`uv run python scripts/dump_sample_levels.py <game>`.

| game | per-level budget |
|---|---|
| lp85 | 13, 60, 80, 150, 80, 80, 80, 80 |
| tu93 | 50, 50, 35, **20**, 50, 60, 30, 50, 50 |
| sp80 | 30, 45, 100, 120, 100, 120 |
| su15 | 32, 32, 48, 48, 32, 32, 32, 48, 48 |
| ft09 | 32, 32, 96, 96, 128, 128 |
| ar25 | 64, 64, 128, 128, 128, 320, 320, 320 |
| cn04 | 75, 100, 125, 125, 150, 200 |
| vc33 | 50, 50, 75, 50, 200, 50, 200 |
| ka59 | 100, 127, 100, 127, 100, 150, 200 |
| re86 | 100, 100, 200, 200, 250, 200, 300 |
| s5i5 | 50, 150, 200, 100, 150, 150, 200 |
| wa30 | 200, 70, 100, 100, 125, 75, 125, 150 |
| dc22 | 128, 192, 192, 192, 512, 1024 |

## Why it decides the architecture

**A searching agent is disqualified before it starts.** The generic path runs 4,000–8,000 actions
per game and opens hundreds of states per level; these budgets are 20–320. The stall diagnostic's
"1,500 steps, 500 states, zero levels" was never a search-breadth problem — the game had been lost
hundreds of actions earlier and the searcher was still expanding. This is why the tools that work — the stencil, track and mirror families — RECOVER a rule and
act, rather than explore and then decide. See [[../rounds/r101_tool-development]].

It also aligns the boards with the metric: RHAE scores `(human/agent)²` per level, and these
budgets sit near the human envelope.

## Detection Heuristics (frame-only)

The budget is DRAWN. Every instance seen is an edge-pinned indicator that shrinks or advances by a
roughly constant amount per action — a bar along a row, a counter marching sideways, a sprite
scrolling off screen. `src/admorphiq/tools/budget.py` recovers it: find the single row or column in
the outer band whose cells stop matching their initial value, fit the consumption rate along that
line, divide. Measured against the declared values after eight actions: **9 of 13 within 30%**, four
essentially exact (tu93 50/50, vc33 50/50, s5i5 50/50, sp80 29 vs 30). The four it cannot read
return `None` rather than a guess.

⛔ Count only the INDICATOR LINE. The first version counted the whole edge band and overestimated
every budget by roughly fifteen times — 768 where the game declares 50 — because static chrome
around the border went into the numerator.

## Related Concepts

- [[swallowed_action]] — the other reason an action can cost nothing and still be spent.
- [[frame_hashing]] — why a whole-frame hash cannot see a marching counter.

## Related Games

- [[../games/LP85]], [[../games/TU93]], [[../games/WA30]], [[../games/LS20]] — pages that already
  recorded a StepCounter before this concept existed.

## A measured budget table, and a free action (2026-08-27)

Read off one game's own source while building a tool for it, and worth checking for elsewhere
because it changes what a plan can afford:

* the per-level cap is **not constant within a game** — 64 actions on level 1, 320 on levels
  2-5, 640 on levels 6-10. A tool that calibrates its patience on level 1 will be five times too
  cautious later, and one that calibrates on level 6 will overrun level 1;
* **ACTION7 is a free UNDO**: it does not increment the counter. A plan that can undo can afford
  to be wrong, which is a different search than one that cannot;
* when the game itself decides a board is unwinnable it offers a **restart button**, bottom-left.
  That is the game telling you the state is dead — cheaper than inferring it.

Provenance: the lf52 tool author, 2026-08-27, from `environment_files/lf52/*/lf52.py`.

## The budget is visible in the ATTEMPT PATTERN, not only on screen (2026-08-27)

re86 scores 0.8349 while clearing all eight levels, and `attempt_probe.py where` puts the entire
shortfall in one level:

```
L6: paid 545  won in 144  binned 401  human 139   [200x 201x 144c]
every other level: binned 0, and five of the seven beat the human count outright
```

Two failed attempts of **200 and 201 actions**, then a win in 144. That regularity is not a
coincidence and it is not a search failure — it is the shape of an overrun. Confirmed from the
game's own source: `"StepCounter": 200` on three of its levels, with 250 on another.

⛔ **A tool that does not know the allowance spends it and loses the level, and the score cannot
tell you that happened** — a level cleared on the third try reads exactly like a level cleared
slowly, because the engine restores the board and the score carries the actions already paid. So
the attempt pattern is a SECOND way to detect a budget, available from a run rather than from the
screen, and it is the one that showed up first here.

`src/admorphiq/tools/budget.py` (`BudgetReader`) already recovers the on-screen allowance —
measured at 9 of 13 within 30%, four exact. This is the case it was built for.

Recovering those 401 actions takes re86 from 0.8349 to **0.9794**, the largest single recoverable
amount in the set.
