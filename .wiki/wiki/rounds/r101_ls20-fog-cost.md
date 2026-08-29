---
round: R101LS20FOG
axis: ls20 level 7 — what the remaining 0.0879 is actually made of
keywords: [ls20, fogscout, keymaze, fuel, mover, patrol, oracle, census, ground-truth, measured-negative, blocked-move, handover, empty-proposal]
verdict: NO CHANGE SHIPPED — twelve arms across four axes lose or are exactly inert, and the handover third of the gap is now measured NOT A GAP (231 is invariant over a nine-action range of the handover; sixteen arms, none beats it)
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

## The handover — CLOSED, measured negative (2026-08-30)

`scripts/_ls20_handover.py` records, per tick of level 7, which tool the harness holds, what that
tool's `propose` returned, the action finally taken, the avatar cell before and after (equal = the
engine REFUSED the move), the drawn tank, lives, and both tools' live `detect`. Control arm:
**[17, 101, 63, 66, 67, 100, 231], 0.912085.**

**What the ten actions are, exactly — and only two of them are `keymaze`'s.**

| tick | who | proposal | action | moved? | tank |
|---|---|---|---|---|---|
| 1 | keymaze | `[UP]` | ACTION1 | yes (19,15)->(19,10) | 42 -> 40 |
| 2 | keymaze | `[UP]` | ACTION1 | yes (19,10)->(19,5) | 40 -> 38 |
| 3-10 | keymaze | **`[]`** | ACTION1 | **NO, all eight refused** | 38 -> 22 |
| 11 | fogscout | `[DOWN]` | ACTION2 | yes | 22 -> 20 |

Ticks 1-2 are `keymaze._choose`'s deliberate blind step (`self._idle <= 2`, the branch that rides out
a life-loss flash and the stale level-up frame). Ticks 3-10 are **not keymaze actions at all** —
`propose` returns `[]` and the HARNESS spends the action: `loop._fill_from_current` ends
`self._queue = legal or self._probe(...)`, and `_probe` returns `simple_ids[0]` — ACTION1 — every
time. `_EMPTY_TOLERANCE` is 8, so the eighth empty proposal retires keymaze and fogscout starts on
action 11.

**The swap signal is available on action 2 and the loop does not act on it.** `fogscout.detect` is
0.00 on the level-up frame (which still draws level 6, so `fog_view` is None — exactly the brief's
"something becoming true") and **0.80 from the level's second frame onward**; `keymaze.detect` is
**0.00 for the entire level**. So from tick 3 the loop is holding a tool that bids zero and proposes
nothing while another bids 0.80, and it spends eight actions before saying so.

**The fix built**: evidence-gated early retirement in `_fill_from_current` — retire on the
`_EMPTY_EVIDENCE`-th empty proposal (not the 8th) when some other non-failed tool bids strictly
higher on that exact frame, via a side-effect-free twin of `_better_alternative_exists`. It works
mechanically: fogscout takes the board on action 5 with a 34-unit tank instead of action 11 with 22.

**And it LOSES THE LEVEL.** `scripts/_ls20_evsweep.py` sweeps the constants on BOTH sides — the
evidence threshold 1..8 (handover earlier; 8 reproduces the shipped behaviour exactly) and
`_EMPTY_TOLERANCE` 9..16 (handover later) — one arm per value, shipped agent, same mirrored runner:

| handover on action | tank handed over | level 7 | game |
|---|---|---|---|
| 4, 5, 6 | 34, 32, 30 | **LEVEL LOST** | 0.7500 |
| 7 | 28 | 327 | 0.8309 |
| 8 | 26 | **LEVEL LOST** | 0.7500 |
| **9, 10, 11 (shipped)** | 24, 22, 20 | **231** | **0.912085** |
| 12, 13, 14 | 18, 16, 14 | **LEVEL LOST** | 0.7500 |
| 15 | 12 | **231** | 0.912085 |
| 16 | 10 | **LEVEL LOST** | 0.7500 |
| 17 | 8 | **231** | 0.912085 |
| 18, 19 | 6, 4 | **LEVEL LOST** | 0.7500 |

⭐ **231 is invariant across handovers from 9 to 17 actions, and nothing beats it on either side.**
Six of sixteen arms lose the level outright — not to a timeout (every run is under 32 s) but to the
harness's own no-progress bail, `is_done`'s `_steps - _last_clear_step >= no_progress`.

**Why the handover is free, which is the finding.** The census's life column says the level's first
life runs the tank dry on action **21**, and the avatar is thrown back to the start with a full tank
(lives 3->2 at 22, 2->1 at 44, 1->0 at 67, GAME_OVER and reset at 69, 3->2 at 156, clear at 231). The
handover's twenty fuel units are therefore charged to **a life that ends by running dry regardless of
who spends them**. Handing `fogscout` a fuller tank does not buy it actions; it buys it a different
slice of a life it loses either way, and what it learns in that slice is chaotic in the tank size —
which is why the surface above oscillates instead of sloping.

**Scope, so this is not carried to another game** (`scripts/bid_matrix.py`, all 25 first frames):
`keymaze` bids **0.90 on ls20 and 0.00 everywhere else**, and `fogscout` bids 0.00 on every first
frame including ls20's. The handover exists on ls20 alone; no other game pays for it, and the
eight-action probe run is the `_EMPTY_TOLERANCE` cap already doing its job (uncapped it was s5i5's
448 and dc22's 499).

⛔ **NOT SHIPPED, and do not re-open it.** The 45-action gap's decomposition must be corrected:
**the "10 handover" third is not a gap.** What is recoverable is the execution and discovery pieces
only, and any future handover work has to explain how it beats a 231 that is already invariant over
a nine-action range of exactly this lever.

## What is NOT closed

- **Cross-level mechanic carry** — the structural answer to the human's 186, and untested: it needs
  `fogscout` to perceive an UNFOGGED board it is not driving, which is a build, not an arm. The
  permissive-conjugation result above says the prize is the `press` excursions (17 ticks plus the
  lane ride), not the walking, so it is worth perhaps 20-30 of the 45.

## Related

[[r101_conquest-wave]] · [[r101_allowance-ledger]] · [[r101_silent-specialists]] ·
[[concepts/action_budget]] · [[concepts/swallowed_action]]
