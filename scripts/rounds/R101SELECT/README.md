# R101SELECT — what happens AT THE HANDOVER FRAME (2026-08-30)

**Axis**: SELECTIVITY. Not "how often does `graph` win" but **why does a board fall through to
`graph` at all**. `scripts/bid_matrix.py` reads FIRST frames only and cannot answer it, because the
fall-through happens hundreds of actions into a game, at `UnifiedAgent._redecide` and nowhere else.

**Instrument**: `scripts/_select_handover.py`. It subclasses `UnifiedAgent` (⛔ `loop.py` is shared
by ~40 concurrent agents and was NOT touched) and re-classes the object that
`score_efficiency._make_agent("unified")` builds, so the configuration is identical by construction
rather than by copying. The run itself is `score_efficiency.run_game`, so the scorer's loop —
empty frames list, `restart_on_game_over`, break on WIN — is mirrored rather than re-implemented.

**Provenance**: 9 games, `pfan.sh selho ... 9 "" 6` on ceph-build out of a private snapshot,
budget 4000, working tree at `02d94fcb` + one dirty file (`tools/crag.py`, the bp35 agent's
in-flight edit — bp35 still scores its baseline, so it is currently neutral). ollama on the box has
only `gemma4:26b`; the harness default `gemma4:31b-it-q8_0` 404s in 13 ms, so `_decide` falls back
to `_signature_default` — pure argmax routing. That is the same configuration every gate measures.

## Instrument neutrality — PROVEN, not asserted

Extra `detect()` calls could in principle perturb a stateful tool. They did not: all nine games
reproduce the `R101WA30` gate baseline **to the action**.

```
game   this run                     R101WA30 baseline
lf52   0.272727  5/10  823a         0.272727  5  823
bp35   0.221988  5/9   740a         0.221988  5  740
s5i5   0.583333  6/8   694a         0.583333  6  694
dc22   0.714286  5/6   925a         0.714286  5  925
lp85   0.967682  8/8   189a         0.967682  8  189
m0r0   1.000000  6/6   188a         1.000000  6  188
vc33   1.000000  7/7   199a         1.000000  7  199
g50t   1.000000  7/7   296a         1.000000  7  296
ls20   0.912085  7/7   645a         0.912085  7  645
```

## THE TABLE — every handover in nine games

`survived` = steps the winner lasted **on the level it was picked on** (the loop's step counter is
level-local, so a tenure that spans a level-up reports only its last level — which is the wall
level, i.e. exactly the number of interest). `proposed` = `propose()` calls that returned a legal
plan, cumulative over the tenure.

```
game   step lvl  retired    reason         -> WINNER          owns  survived proposed   top  tied-at-top
lf52      0  0   -          game_start        railpeg         yes    122      359      0.95  pegjump,railpeg
lf52    122  5   -          empty_propose     pegjump         yes     12        1      0.95  pegjump
lf52    134  5   -          empty_propose     graph           yes    366      353      0.80  graph
bp35      0  0   -          game_start        crag            no      14      234      0.50  crag
bp35     14  5   -          empty_propose     graph           yes    486      381      0.80  graph
s5i5      0  0   -          game_start        swivel          yes     39      222      0.95  swivel,telescope
s5i5     39  6   -          empty_propose     linkage         yes    461      460      0.90  linkage
dc22      0  0   -          game_start        gantry          yes    500      924      0.86  gantry
lp85      0  0   -          game_start        cyclepress      yes     33      188      0.86  cyclepress
m0r0      0  0   -          game_start        decouple        yes     40       32      0.90  decouple
vc33      0  0   -          game_start        pillar_transfer yes     58      198      0.85  pillar_transfer
g50t      0  0   -          game_start        clonewalk       yes     43      295      0.75  clonewalk
ls20      0  0   -          game_start        keymaze         yes     10      261      0.90  keymaze
ls20     10  6   -          empty_propose     fogscout        yes    220      219      0.80  fogscout,graph
```

Bids at each handover frame (bid now, best seen so far this game); every other tool bid **0.00** —
41 to 43 of the ~48 registered tools at every single decision point.

```
lf52 @0    railpeg .95/.95  pegjump .95/.95  hop .88/.88  graph .45/.45  deadsig .40  wm .25
lf52 @122  pegjump .95/.95  graph .80/.80    llm_goal .05 deadsig .40    wm .25      (railpeg -> 0.00)
lf52 @134  graph   .80/.80  llm_goal .05     deadsig .40  wm .25                     (pegjump -> 0.00)
bp35 @0    crag    .50/.50  graph .45/.45    deadsig .40  wm .25
bp35 @14   graph   .80/.80  crag  .50/.50    llm_goal .05 deadsig .40  wm .25   <- crag STILL BIDS
s5i5 @0    swivel  .95/.95  telescope .95/.95 linkage .90/.90 graph .40 deadsig .40 wm .25
s5i5 @39   linkage .90/.90  graph .40/.40    llm_goal .05 deadsig .40  wm .25   (swivel, telescope -> 0.00)
dc22 @0    gantry  .86/.86  phase_grid .85   graph .45    deadsig .40  wm .25
ls20 @0    keymaze .90/.90  graph .45/.45    deadsig .40  wm .25
ls20 @10   fogscout .80/.80 graph .80/.80    llm_goal .05 deadsig .40  wm .25   <- TIE, specialist wins
```

## What it says

**1. NOT ONE handover was lost to a routing tie — the "specialist bid and lost" case does not
exist in this data, and cannot.** Three handovers had a tie at the top (lf52 `pegjump`/`railpeg`
0.95, s5i5 `swivel`/`telescope` 0.95, ls20 `fogscout`/`graph` 0.80). All three broke by
REGISTRATION ORDER, and `registry.py` lists every specialist ahead of `graph` (graph is 43rd of
48), so a specialist can never lose a tie to the general searcher. The routing layer is not the
defect.

**2. EVERY retirement in nine games went through the EMPTY path. Five of five.** Zero
`stall_swap`, zero `death_clock`. The incumbent's `propose()` returns `[]` for `_EMPTY_TOLERANCE`
(8) consecutive calls and it is dropped. ⚠️ The harness's own stderr line is MISLEADING here: at
s5i5's handover it printed `feedback='action no new state x3'`, which reads as a stall, while the
retirement was the empty counter. `_feedback` is the last message set, not the reason.

**3. `graph` is what a stuck game looks like on TWO of the four, not four.** Who actually holds
the wall level to the end of the budget:

```
lf52   graph   366 actions   <- fell through
bp35   graph   486 actions   <- fell through
s5i5   linkage 461 actions   <- a SPECIALIST holds it; graph never runs
dc22   gantry  500 actions   <- the ORIGINAL specialist; ZERO handovers all game
```

⛔ **dc22 does not fall through at all.** `gantry` bids 0.86, is above `_PRIMARY_CONF` (0.70) so it
is never retired on a stall, and returns a legal plan on 924 of 925 refills. The chain quoted in
the briefing (`gantry 12 -> phase_grid 12 -> graph 474`) does not reproduce at this tree. Rule 7p
measured dc22's wall level at 70.6% INERT actions — those are **gantry's** inert actions, not
graph's. Same for s5i5: `linkage` proposes on 460 of 461 refills.

**4. A retired specialist's `detect` does not always fall — and `crag` is the contract
violation.** `railpeg` (lf52) and `swivel`/`telescope` (s5i5) correctly drop to 0.00 at the frame
their planner gives up. `crag` still bids **0.50** on the frame it goes empty on bp35 level 5 —
identical to its frame-0 bid — because `crag.detect` is a board-SHAPE test (`_readings(...)` plus
the control scheme), not a plan test. "A tool with no plan must bid 0.00" is violated, and it costs
nothing here only because `graph` outbids it at 0.80.

**5. Confidence that PEAKS BETWEEN decisions is invisible to the router.** `hop` bids 0.88 on
lf52's first frame and 0.00 at both later handovers; `socketmerge` reaches **0.95** at some sampled
frame of lf52 and is never at a decision point; `telescope` bids 0.95 on s5i5's first frame and
0.00 at the only handover. The loop samples every tool exactly once per handover, so a tool whose
mechanic becomes visible mid-level is never asked.

**6. `graph` promotes itself to un-retirable owner on exactly the boards where it is wrong.**
`GraphSearchTool.detect` returns **0.8** as soon as any observed transition changed a small
localized region (`graph_search.py:589`) — i.e. "there is an avatar", which is true of nearly every
movement board. 0.8 > `_PRIMARY_CONF` 0.70, so `_primary_owns` is set and the stall path can never
retire it. That is why `graph` held bp35 for 486 and lf52 for 366 actions. Its 0.45 -> 0.80 rise
between frame 0 and the wall frame is not evidence about the wall.

⛔ **What this does NOT license.** Every one of these is a measurement of a MECHANISM (rule 7o).
None of them is a measured claim that changing it raises the score. In particular: 0.8-as-ownership
looks wrong and `crag`'s 0.50 looks wrong, and the only thing that can say so is the full-25 gate
against `scripts/rounds/R101WA30` (0.9069).

## Reproduce

```
bash scripts/pfan.sh selho scripts/_select_handover.py 9 "" 6
ssh -i ~/VM/keys/nfw-dev.pem ubuntu@ceph-build 'cat /tmp/pfan_selho.jsonl' | python3 scripts/rounds/R101SELECT/format.py
```

---

# Part 2 — is a BETTER tool available at a frame where nobody asks?

Finding 5 above says the loop evaluates `detect` only inside `_redecide`. `scripts/_select_overtake.py`
samples every tool every 10th action instead, and records when a non-incumbent strictly outbids the
incumbent. Raw: `overtakes.jsonl`, formatter `format_overtakes.py`.

⚠️ **Instrument caveat, stated because it is real**: this probe moved lf52 from 823 to 827 actions
(score identical, 8 of 9 games exact), so at least one tool's `detect` is NOT side-effect-free. The
handover probe, which samples only at decisions, is exact on all nine.

⛔ Its first version was WRONG and the error is worth recording: the sampling gate used
`self._steps`, which is LEVEL-LOCAL and resets on every level-up, so after the first clear it stayed
shut until the counter climbed back past its old value. m0r0 got SIX samples over 188 actions, all
on level 0. A monotonic tick of the probe's own is the only correct clock.

```
game   samples  overtaken   the overtakes that matter
lf52     83       41        lvl5 graph(.80) outbid by railpeg(.90) x17, hop(.88) x5, pegjump(.95) x1
                            lvl4 railpeg(.75) outbid by pegjump(.95) x4, socketmerge(.95) x4
bp35     73       19        crag(.50) outbid by graph(.80) x12 and llm_goal(.70) x7, all levels
s5i5     70        0        never
dc22     93        0        never
lp85     19        0        never
m0r0     19        8        decouple(.00) outbid by graph(.80) — on a game scoring 1.0000
vc33     20        0        never
g50t     30       26        clonewalk(.75) outbid by graph(.80) on ALL SEVEN levels — scores 1.0000
ls20     65        4        keymaze(.00) / fogscout(.00) outbid by graph — scores 0.9121
```

⛔ **THE OBVIOUS LEVER IS REFUTED BY THE CONTROLS.** "Re-decide when a non-incumbent strictly
outbids the incumbent" fires on 26 of 30 g50t frames and 8 of 19 m0r0 frames — **both games score
1.0000** — and on ls20 at 0.9121. A margin trigger would hand three capped games to the general
searcher. The between-decision peak is a genuine architectural limit; it is not a licence for a
margin trigger. (Rule 7b: contrast with the level that CLEARS, always.)

What survives is narrower and is what `7e53372f` acts on: the incumbent's bid COLLAPSING to 0.00
while it is winning (`decouple`, `keymaze`, `fogscout` all do this mid-play) means a bid comparison
cannot be trusted as a progress signal at all — so the only defensible use of `graph`'s 0.80 is the
one that was removed, namely that it should not confer OWNERSHIP.

## Where the four stuck games actually differ

```
lf52  fell through to graph      no tool has a plan for level 5      -> a new tool, or none
bp35  fell through to graph      no tool has a plan for level 5      -> a new tool, or none
s5i5  linkage holds 461 actions  a SPECIALIST is playing and losing  -> that tool's depth
dc22  gantry holds 500 actions   ZERO handovers all game             -> that tool's depth
```

## Three things the gate cannot see — carried here so "gated clean" is never read wider than it is

⚠️ **`llm_goal` on Kaggle.** On ceph the LLM 404s so `llm_goal` bids 0.05 at every measured
handover, but **on Kaggle the LLM is live** and the 0.70 band is real there and unmeasured here.
That is a difference between the box and the deployed card, and the full 25 cannot see it. It does
not block `7e53372f` — `llm_goal` outranking `graph` is plausibly correct — but nobody should later
read "gated clean" as covering it.

⛔ **The refuted lever, stated so it is not re-proposed.** "Re-decide when a non-incumbent outbids
the incumbent" fires on 26 of 30 g50t frames, 8 of 19 m0r0 frames, and on ls20 — **a margin trigger
would hand three capped games to the general searcher. The between-decision peak is an architectural
limit, not a licence.**

⚠️ **At least one tool's `detect` is not side-effect-free** — the every-10th-action sweep moved
lf52 from 823 to 827 actions while leaving its score identical. `detect` is supposed to be a
question, not a move. WHICH tool is unmeasured and is worth its own run: bisect by sampling one
tool's `detect` at a time on lf52 and comparing the action count against 823.


---

# Part 3 — WHICH tool's `detect` is not side-effect-free? It is `railpeg`.

Part 2 left an honesty note: the every-10th-action sweep moved lf52 from **823 to 827** actions,
score identical, so at least one tool answers a question by moving. `scripts/_select_detectfx.py`
bisects it — one arm per registered tool, all arms in one fan, plus two controls.

⛔ **BOTH CONTROLS ARE THE POINT.** Without the negative control an all-clean fan is
indistinguishable from a fan that measured nothing; without the positive control a clean result may
just mean the perturbation stopped reproducing.

```
CONTROL  sample nothing   expect 823   got 823   OK
CONTROL  sample all 47     expect 827   got 827   OK   <- reproduces at HEAD
```

```
OFFENDERS (1 of 47 tools measured)
  railpeg            827 actions   delta +4   score 0.272727   83 samples

CLEAN at exactly 823 (46): assemble blastclock clonewalk cover_targets crag cyclepress deadsig dealias decouple fogscout gantry graph haul hop keymaze lattice_maze linkage llm_goal maze mirror orderforge paint pattern_cast pegjump phase_grid pillar_transfer progbits reflect_cover reforge rule_rewrite shepherd sigilgate slotlaunch sluice socketmerge spill stamppaint stencil subroutine swivel telescope tether toggle track tube_order world_model
unused arms: 1
```

**ONE tool accounts for the ENTIRE perturbation, and it is lf52's own incumbent.**

## What `railpeg.detect` mutates

`src/admorphiq/tools/railpeg.py`. `detect` is four lines and two of them mutate:

- `:1482` `self._peaked = max(self._peaked, len(m.pieces))` — a high-water mark.
- `:1485` `return self._ensure_plan(m)` — **`detect` runs the PLANNER.** `_ensure_plan` returns
  early only when a plan already exists (`:1312`), so when the plan is empty — exactly when the
  tool has just spent it — an extra `detect` builds and STORES a plan against a frame the tool was
  never asked to act on, and on the way:
  - `:1343` `self._sincecapture += 1`, which gates `:1334 stuck = self._elsewhere and
    self._sincecapture >= _LOCAL_PATIENCE`, and `_LOCAL_PATIENCE` is **3**;
  - `:1402` `self._barren += 1`, which gates `:1370 if self._barren >= 3` — the tool's own give-up;
  - `:1326` `self._elsewhere = True`, `:1327 self._claiming = False`.

⛔ So **asking `railpeg` whether it recognises a board spends a third of the patience that decides
when it stops proposing and hands the board over** — the very handover part 1 of this round
measured. On lf52 level 5 `railpeg` retires through the EMPTY path.

⭐ **The defect is a known one, half-fixed, in the same file by the same author.** The other thing
`detect` calls, `_sync`, already carries an explicit idempotence guard at `:1073`: *"⛔ Idempotent
per frame. The harness asks `detect` and then `propose` about the SAME board, and this method LEARNS
— running it twice makes a frame look as if it had settled ... and installs a stale board over a
correct model."* `_ensure_plan` was left unguarded. `pegjump` has the identical structure and
measures CLEAN here, which is the next point.

## The population is far larger than the arm that fired

`bash scripts/detect_purity_scan.sh` — grep only, no engine, no box:

```
railpeg  26   pegjump 24   tube 15   haul 12   reforge 10   paint_flood 5   socketmerge 3
crag 3   orderforge 2   cover_targets 2   + 9 more at 1
19 of 49 tools have a detect that reaches a mutating line
```

⚠️ Most of those score a clean 823 here only because they early-return on a board that is not
theirs — `pegjump` is the proof, same code shape as `railpeg` and clean on this game. ⛔ **The eval
is 110 boards nobody has seen and the tool set is the same one, so "clean on lf52" is not "pure".**

⭐ `socketmerge` is the pattern worth copying and it is already in the tree: `detect` saves the state
tuple, mutates freely while reading, and restores it in a `finally` — pure by construction rather
than by luck. A line-counting scan cannot tell that apart from a real leak, which is why the scan
reports and never fails.

## ⛔ What this does NOT license

Rule 7o. `detect`-then-`propose` on the same board is the harness's NORMAL call pattern, so
`_ensure_plan` running inside `detect` and being reused by `propose` is plausibly load-bearing for
the tool's efficiency — the plan is deliberately built one call early. A naive "make detect
read-only" could cost a plan per action. Only the full-25 gate can decide it, and `railpeg` belongs
to whoever owns lf52.

The narrow claim that IS established: **an instrument sampling `detect` more often than the harness
does is measuring a run it perturbed, and it will not look wrong.**

⚠️ **One instrument note from this fan, because it nearly corrupted the write-up.** Two background
waiters were redirecting the box's results to the SAME temp path, and the second one truncated the
file while the append script was reading it — the script died on a missing control key rather than
silently writing a table with no controls. That it failed loudly is luck, not design: a race that
drops the OFFENDER rows instead would have produced a clean-looking all-clear. ⛔ Namespace every
temp path per fan, exactly as `pfan.sh` already forces for its own output after the same class of
collision cost a peer's results on 2026-08-29.

---

# Part 4 — the fix for part 3 is REFUTED, and the mechanism is now fully separated

Part 3 attributed the lf52 823 -> 827 perturbation to `railpeg`, and named the obvious repair: give
`_ensure_plan` the same per-frame idempotence guard `_sync` already carries eight lines away. It was
built (memo keyed on `_sync_key`, wrapper + `_build_plan`, four contract tests validated in both
directions) and then MEASURED, and it does nothing at all.

⛔ **THE 2x2, and every cell of it is identical across the two trees.** `builds` = every planning
decision of the whole game (`_tiers` is `__init__`-only on this tool, so it survives `reset()` and
counts the game, not the level).

```
                       control: sample nothing        sample all 47 tools, every 10th action
UNGUARDED (HEAD)       823 actions, builds 67         827 actions, builds 100
GUARDED   (the memo)   823 actions, builds 67         827 actions, builds 100
tiers, both rows       win 7 capture 31 travel 19     win 7 capture 33 travel 25 none 34
                       none 9 approach 1              approach 1
```

**The memo changes nothing — not the actions, not the build count, not the tier breakdown.** It was
reverted rather than shipped: `OPERATING_RULES.md` 7b, *keep nothing that does not move the score,
and the rule applies to your own work hardest*.

## Why it cannot work, which the same measurement shows

⛔ **There is no same-frame double-build to suppress.** `builds` is 67 with the memo and 67 without
it on the unsampled run — so the duplicate the memo exists to catch does not occur. It cannot,
because every path in `_build_plan` that advances a counter also fills `_plan`, and a filled `_plan`
wins the `if self._plan: return 0.9` branch above. The repeat that IS reachable touches only
`_why['barren-cap']` and `_tiers['none']`, which are diagnostics.

**The +33 builds are on frames the harness never asked about.** Each is a genuinely NEW frame, so a
per-frame memo is a no-op by construction. The instrument samples every tenth action; the harness
calls `propose` only when its queue drains, so most samples land where the tool would never have
been consulted, and `detect` plans there — 25 of the 33 extra builds are the `none` tier (nothing
found) but `travel` gains 6 and `capture` 2, which are real plans built against boards the tool was
not about to act on.

## `_sync` is EXONERATED, and that is a separate measurement

Two mechanisms could explain part 3 and they wanted opposite follow-ups, so both were run
(`scripts/_select_syncfx.py`, rule 7h — enumerate, then test together):

```
control                          823 actions   builds 67   tiers win7 cap31 trav19 none9 app1
`_sync` ONLY, 83 samples         823 actions   builds 67   tiers IDENTICAL
full `detect`, 83 samples        827 actions   builds 100  tiers win7 cap33 trav25 none34 app1
```

⭐ **Handing the tool 83 frames it would never have seen, and letting it LEARN every one of them,
changes nothing whatsoever.** The learner's own per-frame memo plus the fact that it is fed those
frames anyway makes it inert. The whole perturbation is the planner.

## What a real fix would have to be, and why it is not being taken here

`detect` would have to stop planning — report a claim from the model alone. ⛔ That is a
BID-SEMANTICS change, not a purity change: `detect` currently returns the plan's own quality (0.95
win / 0.9 capture / 0.75 explore / 0.0 barren), and replacing it with a model-only claim changes the
number the router sees. This tool's bid is 0.95 on its game, above `_PRIMARY_CONF` 0.70, so a
changed bid can change OWNERSHIP on the game it currently clears to five levels at 8/52/60/64/139
actions. That is a design with a gate behind it, not an edit.

⚠️ And the size of the prize should be stated honestly first: in the UNSAMPLED run the tool plans 67
times in 823 actions, which is the normal rate — the out-of-band builds come from `_better_alternative_exists`,
`_signature_default` and the `_primary_owns` re-check, which ask `detect` at frames the tool will not
act on. That is real, and it is small. **Nothing measured says removing it wins a level.**
