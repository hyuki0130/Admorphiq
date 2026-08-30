---
round: R101DEADRECKON
axis: does lattice_maze's dead-reckoning repair transfer to the three live visibility-identity sites 7cl found
keywords: [dead-reckoning, visibility, identity, paint-order, z-order, occlusion, lattice_maze, telescope, swivel, blastclock, s5i5, ka59, tu93, repair, deferral, transfer, 7cd, 7cl, 7o]
verdict: NO, AND THE REASON IS MEASURED — lattice_maze re-reads identity every action (178 of 187 reads have a prior cell); telescope and swivel commit it ONCE per level on the opening frame (5 of 5 and 2 of 2 reads at in-level action 0), so the tracked state the repair needs does not exist at the read. Deferral is closed too: on the board where the defect bites, the rider markers are absent across ALL 62 reads of the costly level. Two of the three sites have no success criterion at all. Nothing built, no gate run.
commit: pending
supersedes: nothing — this is the repair question [[r101_visibility-identity-census]] opened
---

# R101 — does the repair that already worked generalise?

> [[r101_visibility-identity-census]] counted the class rule 7cd named and found five sites with the
> fallback-on-paint shape, three of them live on the 25. Buried in that count was the most useful
> fact in it: the class's **worst** site, `lattice_maze.py:484` — 6.9x on its own re-render against
> telescope's 1.56x — is **already repaired**, holds tu93 at 1.0000, and survives the exact
> perturbation that breaks the class. This round asks whether that repair transfers.

## The answer in three sentences

⛔ **No, and it is not a shrug.** `lattice_maze`'s repair needs a prior position and a spent action
of known displacement; on a run, **178 of its 187 identity reads have both**, while `telescope`'s
**five of five** and `swivel`'s **two of two** happen on the level's OPENING frame, where neither
exists.

⛔ **Deferring the commitment is closed too, and by the board rather than by the tool.** On the
archived s5i5 the rider markers are painted under their bars for the *whole* of every level the tool
plays — **62 reads on the 61-action level, `movers` empty in all of them** — so there is no later
moment with better evidence to wait for.

⚠️ **And two of the three sites have no success criterion in the first place**, which should have
been checked before any of the above: `swivel:734` fires on s5i5 levels that cost 32 and 31 actions
on BOTH boards, and `blastclock:631` fires only on ka59, which is action-for-action identical on its
own archived re-render and already scores 1.0000.

## 1. What `lattice_maze`'s repair actually is (read the docstring first)

⚠️ Rule 7cl's own lesson applies here: twice in that round a tool already had the thing it was said
to lack. So this is read off `_locate` and its docstring, not inferred from the name.

**The repair does not remove the paint read.** That is the repair 7cd forbids — it takes the tool to
the unfiltered set everywhere, which IS the 61-action behaviour. It **demotes paint from IDENTITY to
CANDIDATE GENERATION** and lets tracked state choose among the candidates, in four tiers:

| the frame shows | what it does |
|---|---|
| exactly ONE candidate | take it — paint is still the cheapest evidence and is used first |
| ZERO candidates | the colour's centroid: the piece may be mid-strike and part-way redrawn |
| MANY, no prior cell | the board ranking — *"the only evidence there is, and it is what chose this colour a moment ago"* |
| MANY, with a prior cell | predict `prev_cell + effect[prev_action]` from the probe-learned control map |

⭐ **Staleness is handled by never trusting the prediction absolutely.** The predicted cell is
accepted **only if it lands on a currently-drawn candidate**; failing that, `prev_cell` itself (the
move was refused — *"propose() distinguishes a refusal from a mis-identification by whether the cell
changed"*); failing that, the nearest candidate by Manhattan distance. The tracked state proposes,
the frame disposes.

**Two preconditions, both structural**: a learned map from action id to displacement (`self._effect`,
filled by probing), and per-action persistence of the last position (`self._prev_cell`,
`self._prev_action`).

## 2. Is that state available at the three live sites? — measured, not read

`scripts/_viscensus_run.py` gained an in-level action counter, taken from a wrapper around the
adapter's `choose_action` — the call `score_efficiency.run_game` makes exactly once per action it
sends to the engine, so the index means the same thing the human baseline means. ⛔ A tool's own step
counter counts planning, which is not what a level costs.

Full 25, `--agent unified` @4000, **every game reproducing its banked R101SHIPPED score**:

```
site                 game  eval  at0   at_min  at_max  levels        state available?
lattice_maze.py:484  tu93   187    9      0       28   0-8           ⭐ 178 of 187 reads
blastclock.py:631    ka59    33   19      0       39   0-6           14 of 33 reads
swivel.py:734        s5i5     2    2      0        0   5,6           ⛔ NONE
telescope.py:1183    s5i5     5    5      0        0   0-4           ⛔ NONE
```

⭐ **The contrast is the finding.** `lattice_maze` re-reads identity on essentially every action, so
95% of its reads have a prior cell to reckon from — which is *why* the repair was available there and
why it holds. `telescope.propose` calls `_begin` when `self._model is None`, i.e. on the first
`propose` of each level, and bakes the rider list into a `_Model` that is never revised; `swivel`
does the identical thing. **At the moment of the read, zero actions have been spent on that level.**

⚠️ `telescope` is not short of machinery — it tracks `self._w` (each control's winding), learns
`model.shift` / `model.grow` by probing, and re-verifies against the frame every action in
`_agrees`. It has everything dead reckoning needs. It acquires all of it **after** the commitment it
would need it for.

## 3. Then defer the commitment — measured, and closed

telescope probes every control anyway, spending actions it has already budgeted. If the rider
markers appeared at any point during the level, the commitment could simply wait. Whether they do is
a question about the BOARD, and only a run answers it (rule 7g).

`scripts/_s5i5_reveal.py` wraps `read_markers` for a whole run on each board and records, per call,
the level, the in-level action index and the number of movers:

```
arm    actions                    score      max movers seen, per level 0..6
live   [13, 30, 47, 39, 32, 31]   0.583333   2  1  2  1  2  1  2      ⭐ POSITIVE CONTROL
arch   [13, 30, 47, 61, 32, 31]   0.559296   0  0  0  0  0  0  1      ⭐ NEGATIVE CONTROL

level 3 — the one that costs 61 instead of 39 — archived arm:
    62 read_markers calls across the whole level.  movers EMPTY in every one.
```

⛔ **The evidence never arrives.** Not at the opening frame, and not at any action after it. The
riders are under their bars for the entire level, so deferral has nothing to wait for.

⚠️ **Both controls hold and one of them is inside the arm.** The live arm reproduces
`[13,30,47,39,32,31]` and the archived arm `[13,30,47,61,32,31]` — both banked numbers, three times
each in [[r101_zorder-rider]]. And the archived board's **level 6 reports `movers=1`**, so the
reader is demonstrably not blind on that copy; the zeros on levels 0-5 are the board, not the
instrument.

## 4. Two of the three had no success criterion to begin with

⛔ This should have been the first check, and it removes two sites before any of the above matters.

* **`swivel.py:734`** fires on s5i5 levels 5 and 6. Those levels cost **32 and 31 actions on BOTH
  boards** ([[r101_zorder-rider]], 3 runs each way). The site falls back and it costs nothing.
* **`blastclock.py:631`** fires only on ka59. ka59 **has an archived re-render**
  (`environment_files_archive/ka59`) and rule 7by measured it **action-for-action identical** on it;
  the game scores **1.0000**; and the widening the site can produce is **2 candidates to 1**.

Neither has a board anywhere in the corpus where the defect costs an action. **A repair there cannot
be shown to help and can only regress** — rule 7o, in its cheapest form: there is no measurement
that could license the change.

⭐ **So of the three live sites, exactly ONE has a measured cost anywhere — `telescope.py:1183` — and
that is precisely the one where the state is provably unavailable.**

## What was built: nothing, and no gate was run

Step 2 answered no, so step 3 did not start. `snapgate.sh` and `xfergate.sh` were not run because
there is no change to gate. ⛔ Recording that plainly matters: thirteen repairs in this campaign were
built, measured and reverted, and the most expensive was exactly this shape — `frame_2d` really did
read a stale layer at 100% of level transitions in all 21 games, and fixing the real defect cost
**0.8962 -> 0.6525 across fourteen games**. A measurement of a MECHANISM does not license a change
of BEHAVIOUR.

**What survives as a lever is not a perception fix.** 7cd already named it: on the archived board the
rider is genuinely not in the frame, so the guess is unavoidable — only its PRICE is not. Lowering
the price means refuting a candidate pairing with something shorter than the pairing's own plan,
which is a search-cost axis. Four of the five levels it would touch are already optimal.

## The transferable rule

⭐ **Dead reckoning is available exactly where identity is re-read CONTINUOUSLY.** A tool that
commits identity once per level on the opening frame has no tracked state by construction, and for
that shape there are only two repairs: defer the commitment until the evidence arrives (which
requires that it does — measured here, it does not), or make being wrong cheaper. **Ask which shape
a site has before proposing a fix for it**, because the two shapes look identical in a census and
admit disjoint repairs.

## Artefacts

```
scripts/_s5i5_reveal.py                            does the evidence ever arrive? both boards
scripts/_viscensus_run.py                          + in-level action index per evaluation
scripts/rounds/R101DEADRECKON/when_arm.jsonl       25 games, when each site reads
scripts/rounds/R101DEADRECKON/s5i5_reveal.jsonl    both boards, movers per level
```

Related: [[r101_visibility-identity-census]] (the census that opened this) ·
[[r101_zorder-rider]] (the exemplar, proved by intervention; the banked action counts both arms
reproduce) · [[r101_render-mutation-transfer]] (why a colour permutation cannot catch this class) ·
[[r101_shipped-and-transfer]] (24 of 25 identical on a re-render — the reason two of the three sites
have no success criterion).
