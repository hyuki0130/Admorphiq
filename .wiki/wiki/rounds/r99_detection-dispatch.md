---
type: reasoning
round: R99
axis: submission card — port the quarantined adapters from game_id selection to FRAME DETECTION
keywords: [detection-dispatch, adapters25, port, false-positive-gate, probe-detection, control-scheme, card, submission, ceiling, transfer, first-frame-limit]
verdict: **CARD 0.0566 -> 0.2772 (4.9x), CONFIRMED on all 25 games in the SHIPPED configuration, zero regressions, nine adapters ported.** Every port lands EXACTLY on its ceiling (lossless), and the shipped configuration scores what the benched one does (0 differences across every game both runs finished). The gate that makes a port shippable is a MEASURED 0/24 false-positive rate across the public games; it blocked two attempts and predicted a specific production regression that the run then produced. Ports write as the mechanic's CONTROL SCHEME plus the entities it cannot do without, requiring BOTH members of a pair. Probe detection (one shared action) opens m0r0, the single largest gap. PARKED with the limit named: lp85's mechanic appears at LEVEL 2 and dispatch decides at L0.
commit: [b3c92a8, e6e4ae5, 4d26d25, 7d2b57c, 755dfad, 1d1c00e, 9fdd6bd, fecdf4f, 2b51a9b, 08050a4, 9e4cac6, c67db8e, c0b58c3, 1b94260, e0534c3, f5eb06d]
date: 2026-08-25
---

# R99 — detection dispatch: shipping the adapter depth

> Two months of adapter work (R56–R84) reached 0.3296 on the script25 scoreboard while the
> submission card sat at 0.0566, because `script25.py` selects an adapter by `game_id`
> substring and the 110 private games carry no id we know. This round moves that depth onto
> the card by recognising each mechanic FROM THE FRAME.

## The gap, measured

Both cards measured the same afternoon on ceph-build, 25 games each, in parallel:

```
card (--agent chained)     0.0566     27 levels
adapter ceiling            0.3296     87 levels
```

Three games the adapters CONQUER (ft09, m0r0, ls20 — all 1.0000) scored zero or near-zero on
the card; lp85 (8 levels) and su15 (6) did not clear a single level there.

## What made the port cheap, and what did not

⛔ The obvious reading of "quarantined by design" is that the adapters cheat and would need
rewriting. **Measured false.** Every adapter's entry point takes no game identity —
`ft09.Adapter.__init__(giveup)`, `ls20.Adapter.__init__()` — and the only `GAME_ID` references
under `adapters25/` are the registry and one comment. The AST lint already forbids importing
anything but stdlib, `admorphiq.kernels` and `adapters25.base`.

So the port is a DISPATCH change: `detect(frames)` on `GameAdapter`, and dispatch by detection.

⚠️ But frame-only is not general, and that is the whole difficulty. ft09's first detector —
"does ring discovery find a ring" — false-positived on **9 of 24** public games.

## The gate

A detector ships only at **0/24 false positives** (`scripts/detector_falsepos.py`). It is a
measurement, not a precaution:

* ft09 needed two narrowing passes (click-only → 4/24; one COMPLETE 8-cell ring → 0/24).
* sb26 sat at 2/24 and was refused. It reached the measurement box anyway (a sync tarball
  carries the working tree, not the index) and the full-25 run produced **exactly** the
  predicted regression: s5i5 0.0278 → 0.0000, while sb26 gained 0.7664.

The trade-off, stated rather than asserted away: on the public 25 that unsafe detector is
strongly net-positive. It stays out because **the public 25 are a proxy for 110 games we cannot
see**, where a misfire costs invisibly — no s5i5 line appears to warn us.

## How a detector is written

**The mechanic's CONTROL SCHEME, plus the entities it cannot do without.** Where the controls
are unique the entities are a formality; where they are shared the entities decide. What does
the work is requiring BOTH members of a pair.

```
ft09  clicks only          + one COMPLETE 8-cell ring (a 3x3 minus its centre — the definition)
ls20  movement only        + avatar, goal, carried token and goal preview all parse
sb26  clicks + confirm     + a portal-sort board  (controls: nothing to walk, so pick/place/undo)
      + undo, no movement
su15  clicks + undo        + fruits AND goal disks  (a delivery puzzle needs both)
re86  move + cycle-select  + a selection marker AND target gates
tr87  movement only        + THREE rule bands, a static source bar, an editable target bar
sk48  move/undo/click      + an arena AND snakes on BOTH sides of the divider
r11l  clicks only          + creatures with legs AND target nests
```

⛔ **Never ask the SOLVER whether it copes.** sb26's first detector asked `simdfs_plan` to parse
the board, reasoning that a mechanic whose engine can plan is present by definition. The engine
plans on s5i5 and sc25 too. A detector built on "my solver did not refuse" inherits the solver's
permissiveness — a property a solver may have and a detector may not.

The last five ports needed no narrowing pass at all once this was written down.

## Probe detection

Some mechanics are not in a still frame. m0r0 grounds its player colour from what MOVED, and a
static colour-searching stand-in resolves a "maze" on **18 of 25** games.

```
static (colour search)                18/25 candidates    0 actions
one probe: colour + maze parses        2 (ka59, m0r0)     1 action
+ the mechanic's MIRROR PAIR           1 (m0r0)           1 action
```

`detect_probed(before, after)` joins the contract. The dispatcher issues ONE shared probe and
offers the pair to every probe detector, so the cost is one action however many adapters read
it. ⚠️ Probe the axis being mirrored: a VERTICAL probe leaves m0r0 and ka59 identical
((-5,0) and (-3,0)); the horizontal one separates them ((0,-5) with (0,+5) against (0,-3)).

**The probe costs nothing**: m0r0 solves 6/6 in 199 actions fresh and 198 after a probe.

## What is parked, and the limit it names

lp85 is the largest remaining gap and resists both forms. Statically no threshold exists — its
rotation-button finder returns 3 where ft09 returns 12 and s5i5 returns 2, so lp85 sits BETWEEN
its rivals. And a click probe changes zero cells, because ⛔ **the ring mechanic appears at LEVEL
2** while dispatch decides at L0, where the board is a rare-colour click puzzle with no rotation
buttons at all.

**First-frame dispatch cannot see a mechanic that only appears at a deeper level.**

This is also why the probe worked for m0r0 and not here, which matters because the two look alike
from a distance: **m0r0's probe needs no aim.** A direction key acts on the whole board. A click
probe must choose WHERE to press, and choosing correctly requires already knowing the mechanic.

## The card, and measuring it as shipped

⚠️ `--agent detect` and the notebook are different configurations — a live LLM backend and the
runner's `GF_GIVEUP` against a dead LLM callable and the deployed default — so the benched number
could not be quoted for a submission without checking. `--agent kaggle_detect` builds the shipped
artifact exactly, and per game the two agree: **0 differences** across every game both runs
finished.

```
card                0.0566
detection dispatch  0.2772      4.9x, zero regressions, 84% of the way to the ceiling
adapter ceiling     0.3296
```

**Final, in the SHIPPED configuration, all 25 games**: `--agent kaggle_detect` reads **0.2772**, and
`scripts/benched_vs_shipped.py` compares **25 of 25 games with 0 differences**. The dead LLM callable
costs nothing — the signature-routing path reaches the same result as a live backend, consistent
with the v1 notebook's own record that the LLM contributed +0.004%p there. This is the number that
may be quoted for a submission.

Every port lands EXACTLY on its ceiling, which is what says the move was lossless: the adapter
selected by frame evidence scores what it scored when selected by `game_id`.

⛔ One measured trap: a sync carrying only `src scripts tests notebooks kaggle` produced
`No module named 'agents'` and **0.0000 on all 25 games** — the shipped wrapper needs the official
`ARC-AGI-3-Agents/` directory. That reads exactly like a broken card and is not one.

## Build provenance

`kaggle/build_and_push.sh` and `kernel-metadata.json` land WITH the card, because the 0.20 card
could not be rebuilt from this repository — no kernel-metadata on any branch, no push command, no
mapping from dataset version to commit. The script stamps the commit inside the dataset and polls
the file listing before pushing the kernel, since `datasets version` returns before the files are
served. `--submit` is a flag, never the default.

Related: [[../lessons/adapter_port_is_a_dispatch_change_20260825]],
[[../lessons/adapter_port_progress_20260825]],
[[../lessons/submission_not_reproducible_20260825]], [[r98_flow-deflection]].
