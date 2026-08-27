---
type: lesson
topic: dispatch
date: 2026-08-27
keywords: [adapters, detection-dispatch, card, fallback, bail, regression, r99, r101, submission]
---

# The thirteen adapters now COST the card 0.29

> The deployed configuration scores **0.5335** over the 25 sample games. The generic tools
> ALONE score **0.8224**. The adapters are worse on **23 of 25 games**, and the two routing
> guards cannot see it because both were calibrated when the fallback was 0.0566.

## Symptom

Measured 2026-08-27 on ceph-build, both at @4000, same tree:

```
--agent kaggle_detect  (as SHIPPED: 13 adapters + generic fallback)   0.5335
--agent unified        (generic tools alone, zero adapters)           0.8224
```

Per game, where the adapter takes a board the fallback now solves better:

```
sc25  0.0427 vs 1.0000     ar25  0.0833 vs 1.0000     tn36  0.1071 vs 1.0000
wa30  0.0222 vs 0.8000     sp80  0.1429 vs 0.7143     sk48  0.2778 vs 1.0000
r11l  0.2594 vs 1.0000     tr87  0.2857 vs 1.0000     su15  0.4368 vs 1.0000
sb26  0.8460 vs 1.0000     lp85  0.6992 vs 0.8919     re86  0.7273 vs 0.8350
```

Only **two** adapters still beat the generic path: `ls20` (1.0000 vs 0.7500) and `m0r0`
(1.0000 vs 0.7143). One game ties (`ft09`, both 1.0000).

## Root cause

Nothing broke. The adapters score exactly what they always scored; the FALLBACK moved under
them, 0.0566 -> 0.8224 in a day, and both guards were calibrated against the old number:

- **The dispatch bail asks the wrong question.** `DetectDispatchAgent` hands the board back to
  the fallback when an adapter has cleared NO level in 2000 actions. An adapter that clears one
  level slowly keeps the board for the whole budget. That guard was written to catch a detector
  misfiring on an unseen private game, which it still does — it was never a guard against an
  adapter being WORSE than the fallback, because when it was written nothing was.
- **The false-positive gate measures the wrong thing too.** A detector ships at 0/24 false
  positives, i.e. it must not fire on a board that is not its own. It has never been asked
  whether firing on its OWN board is still an improvement.

## Prevention

⛔ **An incumbent's gate must be re-run when the thing it beat has changed.** Every adapter was
kept on a comparison against a 0.0566 fallback. None of those comparisons has been re-run since,
and eleven of thirteen have silently inverted.

The cheap check is the one above: run the full 25 twice, `--agent kaggle_detect` and
`--agent unified`, and compare per game. It costs about eight minutes on ceph and it is the only
way to see this — no single-game probe shows it, and the card's own mean hides it because the
adapters that still win pull it up.

## Recovery

The measurement says the deployed card would score **+0.29** by dropping eleven of the thirteen
adapters and keeping only `ls20` and `m0r0`. ⛔ That is a SUBMISSION-AFFECTING change and the
submission is the user's call — this page records the measurement, not a decision. It also
touches the unresolved doctrine conflict already in `CLAUDE.md`: the adapters are quarantined
BY DESIGN because per-game code cannot transfer to 110 private games, and the generic path now
beats them on the public set as well.

## Falsification

Wrong if the two runs are not comparable — check that both used the same tree and that the
framework directory was present (its absence scores 0.0000 on all 25 and reads like a broken
card). Wrong per-adapter if a game's generic score is itself unstable; every number above comes
from a deterministic full-25 run and the generic figures are reproduced across four separate
rounds.

## Related

- [[../rounds/r99_detection-dispatch]] — where the adapters and the bail were designed, when the
  fallback was 0.0566 and dispatch was a 5.6x gain.
- [[../rounds/r101_tool-development]] — the round that moved the fallback out from under them.
- [[tool_selectivity_20260827]] — the same shape one layer down: a tool that claims a board it
  cannot solve best costs the board.
