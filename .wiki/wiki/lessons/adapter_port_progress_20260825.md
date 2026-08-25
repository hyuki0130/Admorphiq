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

