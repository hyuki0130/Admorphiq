---
type: concept
instantiating_games: [G50T, LS20, BP35, LF52, AR25, DC22]
detection_frame_only: yes
---

# Swallowed Action

> An action that arrives while the board is animating is CONSUMED WITHOUT EFFECT — it costs budget, changes nothing, and teaches a searcher a wall that is not there.

## Definition

Several games gate their action dispatch behind an animation:

```python
if self.avatar.animating:
    self.avatar.step()          # advance the animation
else:
    ...dispatch the action...   # never reached this tick
```

The action is counted (the budget indicator advances) and the board does not respond. A tool that
records "this action did nothing here" has learned a FALSE transition.

## Why it is worth its own concept

It produces contradictory measurements that look like a broken model rather than a timing artefact.
Measured on g50t: `ACTION3` repeated from a reset never moves; `ACTION3` after `ACTION2` moves;
`ACTION1` moved the body down once and up later from the same board. Those readings were recorded
as "the action→direction map is not fixed and the rule is unidentified" — and the map is simply
up/down/left/right, with the first actions after a reset absorbed. One read of the game's own
`step()` settled in seconds what eight live probes could not.

## Detection Heuristics (frame-only)

- **Probe an action SEVERAL times before believing it inert.** `src/admorphiq/tools/maze.py` uses
  four tries; a single-shot probe reported every control on g50t as dead and concluded the board
  could not be moved at all.
- **A probe that resets before each trial measures only the absorbed action.** A BFS built that way
  reported g50t as having ONE reachable state.
- Ignore the edge band when deciding whether the board answered — otherwise the budget indicator
  makes every action look effective. See [[action_budget]].

## Related Concepts

- [[action_budget]] — a swallowed action still spends it.
- [[frame_hashing]] — an animating frame hashes differently every tick, so novelty is not progress.

## Related Games

- [[../games/G50T]] — the measured case, including the two same-colour blobs that made it worse.
- [[../games/LS20]], [[../games/BP35]], [[../games/LF52]] — queue an animation and read the outcome
  once it drains.

- [[frame_layer_timeline]] — the other half: the layer stack is the animation's own
  timeline, so reading `arr[0]` reasons about the board before the animation resolved.

## Waiting for the board to settle IS the synchronisation (measured 2026-08-27)

A tool that waits for a settled frame before acting looks like it is being over-cautious, and
there is an argument that reads as obviously correct: an unsettled frame should stop the model
being BELIEVED, not stop the tool from ACTING — a sliding piece does not move the lattice, so
click coordinates stay valid throughout the animation.

**Measured on lf52: 5 levels -> 1.** Clicking into a board that has not finished resolving the
previous action loses every level after the first. The wait is not caution; it is the only
synchronisation a frame-only tool has with the engine. Reverted, and the reason is recorded in
the tool so nobody re-derives it.

Two related rules from the same measurement, both kept because both were free:

* **A model invariant is not evidence the board has settled.** "The carts are conserved" is a
  statement about the MODEL, so a model that is merely WRONG about one cart makes it true
  forever and the tool waits out the level holding a winning plan. Scope such a check to the
  window where the action could actually have violated it — here, the three frames after a
  DRIVE, because only a drive moves a cart.
* **Claim furniture only from settled frames.** An animation is the one thing that can invent an
  object, and a phantom obstacle is a phantom stepping stone the engine then refuses to use.

## A calibration probe can LOSE the level before any real move (2026-08-27)

lf52's level 6 is winnable in 87 actions against a human 148 — from the position it starts in.
Read off the engine's own object positions, varying nothing but where one cart sits:

```
opening, all 8 pieces, far cart at (23,4):  WINNABLE in 87
opening, all 8 pieces, far cart at (23,5):  NOT WINNABLE
opening, all 8 pieces, far cart at (23,6):  NOT WINNABLE
```

The level starts with that cart at (23,4). By the tool's first capture it is at (23,6), moved
during the ~29 actions of direction calibration and early travel that precede any capture — a
cart twenty columns from the action, which no plan was reasoning about.

**So the level was lost by a PROBE, before a single piece was taken.** And it is recoverable in
two actions: driving that cart back up restores the win outright, because nothing else has track
above it.

⚠️ The general shape: on a board where one action moves several objects, a probe is not a
read-only operation on the parts of the board it is not asking about. A tool that calibrates by
acting must either model what its calibration moves, or be able to undo it — here two drives.
