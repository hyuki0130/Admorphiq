---
type: lesson
topic: model reconciliation
date: 2026-08-29
keywords: [refused action, animation lag, stale frame, model reconciliation, belief update, scrolling board, rails, railpeg, lf52, over-inclusive perception]
commit: 0443f0e0
---
# A refused action and a lagging frame are the same picture

> `railpeg` drove a cart 249 times on lf52's level 6 and the map it had of the board did not grow
> by one cell. Every refusal was being resolved as an animation, because the board after a refused
> action is a board the tool has already seen — which is exactly the test it used to recognise a
> stale frame.

## The claim

Any tool that keeps a simulation and reconciles it against a frame stream needs a rule for the
frame that disagrees with the simulation. On a game with animations the honest rule is that a
disagreeing frame is usually one action behind, so the standard defence is: **if the frame
reproduces a state I have already left, it is stale — keep the simulation.**

That defence has a blind spot with a name. When the engine REFUSES an action, the board it hands
back is the board from before the action — which is, verbatim, "a state I have already left". So
every refusal is classified as a lag, the simulation keeps a move the engine never made, and the
model drifts away from the board while the tool reports nothing wrong.

The drift is not self-correcting. It is self-reinforcing: the planner re-derives the same illegal
move from the same wrong model and proposes it again.

## Symptom

Measured on lf52 level 6 (`scripts/_lf52_fire.py`, the real harness, six seeds byte-identical,
counters taken as deltas from the instant the level begins):

```
known cells at the first level-6 action      61
known cells at the 500th                     61      flat, all 40 samples
drives issued                                249     239 of them carrying nobody
camera shifts observed                       1       in 285 frames
```

The tool was boarding carts and driving them nowhere, and nothing in its own reporting said so —
it had a plan every turn and it executed it every turn. The visible cost showed up in an unrelated
place: 73 presses of one direction on a level with a 500-action allowance, which earlier work read
as a direction-mapping defect and cleared the direction map of (`_dirmap` was correct).

The second-order symptom is the one that misleads. `railpeg`'s two preceding repairs both FIRED —
`plan:local-win-refused` 26,955 and 32 boardings out of 33 travel plans, against 0 of 32 before —
and the score did not move a digit. A change can be executing perfectly and still be invisible
because a different defect downstream discards its effect.

## Root cause

Two things have to be true together, and both are ordinary:

1. **The staleness test is a set-membership test over past states.** `_sync` accepted any frame
   matching the current state OR any state in its recent history. The pre-action state is always in
   that history.
2. **Perception is over-inclusive somewhere.** Rails were read from pixels, and floor drawn in the
   track's colour reads as track. The model therefore believed in track that does not exist, and
   `m.rails` was union-only — every frame could ADD a rail cell and nothing in the tool could ever
   remove one.

(1) makes a wrong belief unfalsifiable; (2) supplies the wrong belief. Either alone is survivable.

## Prevention

- **Separate the two readings by TIME, not by appearance.** A refusal and a lag look identical in
  one frame and differ in the next: an animation resolves, a refusal does not. Judge the outcome of
  an action on the first SETTLED frame after it, and do not let the history test reach that verdict
  first.
- **Any belief filled from pixels needs a retraction path.** A union-only map cannot be wrong
  temporarily; it can only be wrong permanently.
- **A refusal is free survey data.** The engine only moves a vehicle onto real track, so "it did not
  move" is a precise measurement of the cell ahead. The cheapest information on the board is the
  action the engine would not perform.
- **Count the outcome, not the proposal.** A tier that reports "I made a plan" every turn cannot
  distinguish 249 drives from one. Counters belong on what the BOARD did.

## Recovery

`src/admorphiq/tools/railpeg.py:_settle_drive` (commit `0443f0e0`) reads the last drive's verdict
off the first settled frame, judged on the visible window only — a vehicle scrolled off screen is
absent for reasons that have nothing to do with the action. It restores the whole pre-action state,
pieces included, because a cart carries its passenger and restoring the carts alone leaves the
passenger floating one cell away. Track is retracted only on a SECOND identical refusal: one is
indistinguishable from an action swallowed by an animation, and a spuriously deleted cell removes a
route permanently.

```
known cells 61 -> 61 (flat)   becomes   61 -> 99     the map grows past its own screen
drive:empty 239               becomes   1
drive:with-passenger 10       becomes   43
```

One retracted rail cell did all of that.

⛔ The level still did not clear, and the change was kept anyway on the explicit reasoning that a
mechanism on the path to the level is worth keeping when it holds the score. That is a judgement
about this mechanism, not a general licence — see the gate rule in `OPERATING_RULES.md` 7o.

## Falsification

- A game where the engine returns a genuinely different board for a refused action (an error flash,
  a shake, a counter tick that is not edge-pinned) does not have this hazard, and the settled-frame
  verdict is redundant work there.
- If a tool's perception is exact rather than over-inclusive, (2) is absent and the drift never
  starts — so the first thing to check on a candidate instance is whether the map can be WRONG, not
  whether the staleness test is loose.
- If retraction on the second refusal ever removes a real route, the two-strike rule is too eager
  and the discriminator has to become positive evidence (the vehicle observed moving there once)
  rather than absence of movement twice.

## Related

- [[predicate_over_a_camera_20260829]] — the sibling defect on the same tool and the same level: a
  goal predicate evaluated over the part of the state that has been seen
- [[../games/LF52]] — the board this was measured on
- [[sample_games_mechanics]] — lf52's mechanics and its rendered legal-move oracle
