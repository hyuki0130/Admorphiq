---
type: lesson
keywords: [port, detection, adapters25, card, ceiling, ft09, ls20, sb26, false-positive]
date: 2026-08-25
verdict: Two ports land — card 0.0566 -> 0.1341 (2.4x) with zero regressions. The procedure that makes a port shippable is a measured 0/24 false-positive rate, and it has already blocked two attempts.
---

# The port ladder, and what it costs to climb one rung (2026-08-25)

## Where the card stands

```
                        mean game_score
original card              0.0566
+ ft09 detector            0.0954
+ ls20 detector            0.1341        <- now
adapter ceiling            0.3296
```

Two ports recovered **28% of the distance** to the ceiling, and every other game is unchanged —
detection dispatch falls back to the current card when nothing fires, so a port cannot regress a
game it does not claim.

## The procedure, and that it actually blocks things

A detector ships only at **0/24 false positives** across the public games
(`scripts/detector_falsepos.py`). This is not a formality — it has blocked two attempts so far:

* **ft09** started at 9/24 and needed two mechanic-derived conditions to reach 0
  (click-only → 4/24; one COMPLETE 8-cell ring → 0/24).
* **sb26** sits at **2/24** (`s5i5`, `sc25`) and is NOT committed.
* **m0r0** has no static signature at all: its grounding discovers the player colour from a
  before/after PROBE, and a colour-searching static version resolves a "maze" on 18 of 25 games.

## The finding sb26 hands us

sb26's detector asks the solving engine itself — `simdfs_plan` parses the board, builds the
faithful offline portal-DFS simulator, and returns None when the board is not one of these. The
reasoning was that a mechanic whose engine can plan a placement is present by definition.

⛔ **Measured false.** The engine plans on `s5i5` and `sc25` too. "The engine produced a plan" is
not sufficient evidence that the mechanic is there — a general enough parser will find *some*
structure in an unrelated board and plan against it. A detector built on "my solver did not refuse"
inherits the solver's permissiveness, which is exactly the property a solver is allowed to have and
a detector is not.

The two roles pull opposite ways and that is the lesson: **a solver should be forgiving about what
it accepts; a detector must not be.** ft09's working detector is the counter-example — it does not
ask whether the solver copes, it asks whether the mechanic's defining structure (a complete
3x3-minus-centre ring) is on the board.

## Still open

* lf52 reads 0.0001 on the card and 0.0000 under dispatch, on a game whose detector never fires;
  a paired re-run is measuring whether that is variance.
* Remaining gap by size: m0r0 1.0000, sb26 0.7664, lp85 0.6970, re86 0.6440, su15 0.3433,
  tr87 0.2857, sk48 0.2778, r11l 0.2594.

Related: [[adapter_port_is_a_dispatch_change_20260825]], [[instrument_validity_20260825]].

## The gate proved itself in production (2026-08-25, measured)

The sb26 detector I refused to commit at 2/24 false positives went to the measurement box anyway —
the sync tarball carries the working tree, not the index — so the full-25 run measured exactly what
shipping it would have cost:

```
sb26   0.0796  ->  0.8460     the gain the port was chasing
s5i5   0.0278  ->  0.0000     ⛔ the false positive, in production
lf52   0.0001  ->  0.0001     the capability-flag fix, confirmed
```

`sc25`, the other false positive, scored 0.0000 already, so it hid.

**The trade-off, stated rather than asserted away.** On the public 25 the unsafe detector is
strongly net-positive: +0.7664 on sb26 against −0.0278 on s5i5, and the mean reads 0.1637 instead
of 0.1341. Shipping it would raise the proxy today.

⛔ It stays out, and the reason is the only one that matters here: **the public 25 are a proxy for
110 games we cannot see.** A detector that misfires on 2 of 24 known boards misfires on the unknown
ones too, and there the cost is invisible — no s5i5 line appears to warn us. The gate is not
protecting the proxy score; it is protecting the transfer, which is the entire reason the adapters
were quarantined in the first place.

What the episode is worth: the 0/24 rule stopped being a precaution and became a measurement. It
predicted a specific regression on a specific game, and the run produced exactly that.


## Eight static ports, measured full-25 (2026-08-25)

```
card                       0.0566
detection dispatch         0.2372      4.2x, zero regressions
adapter ceiling            0.3296
```

Every port lands EXACTLY on its ceiling, which is the property that says the port is lossless — the
adapter selected by frame evidence scores what it scored when selected by `game_id`:

```
ft09  0.0291 -> 1.0000     ls20  0.0327 -> 1.0000     sb26  0.0796 -> 0.8460
re86  0.0833 -> 0.7273     su15  0.0935 -> 0.4368     tr87  0.0000 -> 0.2857
sk48  0.0000 -> 0.2778     r11l  0.0000 -> 0.2594
```

### What made the last five need no narrowing pass

**The mechanic's control scheme, plus the entities it cannot do without.** Where the controls are
unique (su15: clicks with an undo and nothing else) the entities are a formality; where they are
shared (r11l with four other click-only games) the entities decide. What does the work is requiring
BOTH members of a pair — snakes on both sides of sk48's divider, legs AND a nest for r11l — because
one without the other is a board that merely looks similar.

⛔ The failure mode to avoid is the one sb26 walked into: asking the SOLVER whether it copes. Its
parser accepted s5i5 and sc25, and a full-25 run with only that condition took s5i5 from 0.0278 to
0.0000. A detector built on "my solver did not refuse" inherits the solver's permissiveness, which
a solver may have and a detector may not.

### Probe detection, and the three defects that hid it

m0r0 needs a probe: its player colour is whatever MOVED, so a static stand-in resolves a "maze" on
18 of 25 games. One probe takes that to 2 candidates and the mechanic's own mirror pair takes it to
1 — but ⚠️ only on the axis being mirrored. A VERTICAL probe leaves m0r0 and ka59 identical (both
(-5,0) / (-3,0)); the horizontal one separates them ((0,-5) with (0,+5) against (0,-3) alone).

Getting there cost three defects, all in wiring rather than in an adapter or the engine:

1. **arming and reading the probe were one state.** The runner calls `is_done` and `choose_action`
   with the SAME frame in one iteration, so reading on arm compared a frame with itself and fell
   back everywhere.
2. **`cls._detect_mechanic is not GameAdapter._detect_mechanic`** is always true — a classmethod is
   a fresh bound object per access — so all 25 adapters counted as ported and the dispatcher spent
   a probe on every board it did not statically recognise.
3. **a diagnostic driver stepped ACTION6 without its `data`**, and the engine's `KeyError('x')`
   read as an adapter defect for two ticks.

With the driver corrected, the question that motivated the contract answers cleanly: **the probe
costs nothing.** m0r0 solves 6/6 in 199 actions fresh and 198 after a probe.


## Why lp85 cannot be ported: the mechanic is not on the first frame (2026-08-25)

lp85 is the largest remaining gap (0.6992 ceiling against 0.0022 on the card) and it resists both
detection forms. The reason is structural, and it took two wrong diagnoses to reach.

**Static: no threshold exists.** The adapter's own rotation-button finder returns 3 on lp85, 12 on
ft09 and 2 on s5i5 — lp85 sits BETWEEN its rivals, so any cut-off is a constant fitted to this
board rather than a property of the mechanic.

**Probe: there is nothing to probe.** A click probe on the first detected "button" changes ZERO
cells. The adapter's docstring says why:

> L0/L1 are cleared by the rare-colour sweep. **L2** is the ring-permutation board — "2 targets +
> 2 goals + 3 rings".

⛔ **The ring mechanic appears at LEVEL 2.** The first frame is a rare-colour click board with no
rotation buttons at all, so the 3 "buttons" are HUD artefacts at the frame edge (the first is at
column 0) and clicking one does nothing. No number of probes helps: the structure is not there yet.

### The limit this names

**First-frame dispatch cannot see a mechanic that only appears at a deeper level.** lp85's
discriminating structure lives at L2; the dispatcher decides at L0; and what L0 *does* show —
"click the rare thing" — is too generic for any detector to claim without hijacking its four
click-only rivals.

This also explains why the probe worked for m0r0 and not here, which is worth stating because the
two look similar from a distance: **m0r0's probe needs no aim.** A direction key acts on the whole
board, so one press reveals the mirror pair. A click probe must choose WHERE to press, and choosing
correctly requires already knowing the mechanic — the circularity is real and specific, not a
figure of speech.

⛔ lp85 is PARKED honestly, with its mechanics decoded and banked. Forcing a threshold would repeat
exactly the failure sb26 walked into when its parser-only detector cost s5i5 its score.

