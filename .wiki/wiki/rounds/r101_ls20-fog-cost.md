---
round: R101LS20FOG
axis: ls20 level 7 — what the remaining 0.0879 is actually made of
keywords: [ls20, fogscout, fuel, mover, patrol, oracle, census, ground-truth, measured-negative, blocked-move]
verdict: NO CHANGE SHIPPED — the gap is diffuse (10 handover + 14 execution + ~21 discovery), and twelve further arms across four axes all lose or are exactly inert
commit: pending
---

# R101 — ls20 level 7: 231 against a human 186, decomposed with the engine's own state

> The briefing asked for **a different way to meet a mover under fog**. The census says the mover is
> not the cost, and the source says the obvious way to meet one is *provably impossible*. What is
> left is three separate ~15-action gaps, and every arm aimed at them was measured a loss.

## The instrument

`scripts/_ls20_census.py` runs the SHIPPED tool set through a loop that mirrors
`score_efficiency.run_game` (empty frames list, `restart_on_game_over`, break on WIN) and reproduces
the banked **[17, 101, 63, 66, 67, 100, 231], game 0.912085** exactly. `fogscout` is subclassed for
RECORDING ONLY, and beside its belief it reads the engine: avatar cell, whether the move was
accepted, every mover's cell and heading, the token triple, the drawn budget, and the lives counter.
At level-7 entry it dumps the static geometry.

⚠️ Everything below is that one deterministic run plus `environment_files/ls20/9607627b/ls20.py`.

## What level 7 IS, from its own source

```
tank 42, 2 per action -> 21 moves a life, 3 lives, restart-to-start on empty
token   = (shape 0..5, colour 0..3, rotation 0..3)   start (1,0,0)
goal    ONE cell (29,50) demanding (0,3,2)  -> 5 shape + 3 colour + 2 rotation presses
shape   changer static at (19,40)      colour changer static at (9,40)
ROTATION changer is the MOVER: a 6-cell vertical lane at x=54, y in {5..30}, period 10
refills six rings at (9,5) (14,45) (29,20) (39,5) (49,5) (54,50)
three DEFLECTORS; with their cells treated as walls the goal is UNREACHABLE — they are the
only route into the south-east, which is what fogscout's docstring already says.
```

## ⛔ YOU CANNOT WAIT FOR THE MOVER. It is not a tuning question, it is the engine.

`Ls20.step` moves every mover FIRST and then applies the player's move; if that move is refused it
calls `fwtnsrvkrz()` on every mover — an UNDO. So a blocked move leaves the joint (player, mover)
state exactly as it was and costs one budget unit. **Measured in the run: 18 blocked moves, and the
mover was frozen on 18 of 18.**

⭐ That closes a whole family at once and explains a result the briefing carried as a puzzle: the
earlier "ambush a sighted mover at its remembered beat" arm was EXACTLY INERT because ambushing
cannot work — `_hold` is a strict no-op with respect to the thing it is waiting for. `_intercept`'s
own docstring says "holding position costs one budget unit and the patrol brings itself back"; the
first half is true and the second is false. Removing `_hold` entirely was measured: **231, identical
per level**, with the suppressed clause firing 3 times.

The mover is met the only way it can be — by ROUTING into the cell it steps onto. The tool already
does this well: in the winning stretch it takes both rotation presses in two consecutive actions
(ticks 221-222) by walking down the lane alongside it.

## Where the 231 actually go

```
  1- 10   keymaze handover                        10   (8 of them pushed into a wall, which also
 11- 68   3 lives lost, GAME OVER, RESET          58    spends 20 of the first life's 42 units)
 69-155   explore; colour+shape+rotation learned  87
    156   4th death: token and position reset      1
157-231   knowledge-complete solve                 75
```

Reason census for the whole level: `map` 59 · `tread` 56 · `win` 35 · `mark` 21 · `press` 17 ·
`refuel` 14 · `look` 15 · `probe-dir` 2 · `bootstrap` 1. **`wait` 0.**

⚠️ The three early deaths are NOT the waste they look like: a death costs only the actions already
spent, the map belief survives it, and it teleports the avatar home for free. The tool never stands
on a refill in its first 67 actions because `_plan` finishes the FRONTIER before it will walk to any
unlearned mark, and a life is 21 moves.

## ⭐ The oracle: a perfect solve is 61 actions, so 75 is not the problem either

A BFS over the dumped geometry in (cell, shape, colour, rotation, mover phase, tank, rings consumed)
— deflector cells treated as ordinary floor, their displacement unmodelled — gives **55 actions with
fuel ignored and 61 with the tank enforced**. Fuel costs an optimal plan about six actions; it costs
the tool fourteen.

So the 45-action gap to the human's 186 is **three separate ~15-action gaps**, not one defect:

```
handover   10   keymaze's, harness-side
execution  14   75 against an oracle 61, of which ~8 is refuel routing
discovery  ~21  146 against the human's implied ~125
```

⭐ And the honest reading of what the human's 186 buys: a first-time human arrives at level 7 having
played six levels with **the same three changers**, while `fogscout` arrives with nothing —
`detect` returns 0.00 on every unfogged board, so it does not play levels 1-6 and cannot learn from
them. The whole mechanic is re-derived inside the one level that is scored against a player who
already knows it.

## ⛔ Closed by measurement this round — twelve arms, four axes

Every arm ran through the real harness against a control that returned 231 exactly.

**Inference — can the changer tables be deduced instead of pressed out?** (`scripts/_ls20_infer.py`)

| arm | what | level 7 | note |
|---|---|---|---|
| colour-cycle closure | an injective axis map whose pairs form one chain must close it | **324** | fired 14x; `press` 17 -> 59 |
| mask-cycle closure | same over glyphs | **level LOST (6/7)** | the seen value set is not the universe |
| motion conjugation, strict | `B(M(m)) = M(B(m))` for a believed rigid motion | 231 | never fired |
| motion conjugation, permissive | same, conflict-checked only | **231, fired 36x** | EXACTLY INERT |

⭐ The permissive conjugation is the informative one: it adds 36 table entries and changes **not one
action**. So the token model's completeness is NOT what gates this level — the tool has to walk the
shape chain regardless, and a richer table buys nothing. That also weakens the cross-level-transfer
idea above: knowing the rules earlier removes the `press` excursions, not the walking.

⚠️ The two losses are a live re-confirmation of `_rules`' existing discipline — "a small correct
table beats a large invented one". Closing a cycle over the values *seen so far* invents a
wrap-around, the win search then plans routes that do not exist, and the level costs 93 more actions.

**Fuel discovery — the tool has no fuel model for 67 actions.** (`scripts/_ls20_fuelfind.py`)

| arm | level 7 |
|---|---|
| tank <= 8: nearest unlearned mark ahead of the frontier | **level LOST (6/7)**, 18 fires |
| tank <= 12: same | **level LOST (6/7)**, 31 fires |
| only when NO refill is known at all, tank <= 8 | **343**, 3 fires |
| `_hold` removed | 231, identical per level |

A mark is the only thing on this board that can be fuel, so this looked cheap. It is not: every
variant turns the run into `press`/`refuel` shuttling (`press` 17 -> 161-186) — the same failure
`_refuel`'s own docstring records from the other direction.

**Refuel ROUTING — nearest ring vs cheapest ring.** (`scripts/_ls20_detour.py`) `_refuel` walks to
the NEAREST refill, and nearest is not cheapest when the level ends somewhere specific: a ring behind
you is paid for twice. This re-ranks ONLY the choice of ring by `d(pos->ring) + d(ring->goal)`, and
is NOT the fuel-aware win search that was already measured worse at 241.

| arm | level 7 |
|---|---|
| rank by detour whenever the goal is known | **307**, differed from nearest 14x of 33 calls |
| same, only while a win route exists | **level LOST (6/7)**, 31x of 61 |
| same, falling back to the aim cell when the goal is unknown | **307** |

⚠️ It fires, it does what it says, and it loses 76 actions. The nearest ring is also the one the tool
is most likely to REACH — ranking by a round trip sends it past the point where the tank runs out.

## What is NOT closed

- The **10-action handover** is worth ~+0.011 of the game and is `keymaze`'s, not `fogscout`'s. It
  costs more than 10 actions in effect: eight of them are pushed into a wall, which hands fogscout a
  tank at 22 of 42.
- **Cross-level mechanic carry** — the structural answer to the human's 186, and untested: it needs
  `fogscout` to perceive an UNFOGGED board it is not driving, which is a build, not an arm. The
  permissive-conjugation result above says the prize is the `press` excursions (17 ticks plus the
  lane ride), not the walking, so it is worth perhaps 20-30 of the 45.

## Related

[[r101_conquest-wave]] · [[r101_allowance-ledger]] · [[r101_silent-specialists]] ·
[[concepts/action_budget]] · [[concepts/swallowed_action]]
