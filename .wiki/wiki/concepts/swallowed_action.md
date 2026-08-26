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
