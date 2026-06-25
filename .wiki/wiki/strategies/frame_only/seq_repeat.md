---
type: strategy
name: seq_repeat
generalizes: yes
implementation: src/admorphiq/agent_ensemble.py
dispatched_from: strat_action_sequence_search in agent_ensemble.py
---

# seq_repeat

> Take the highest-frame-change sequence found by [[seq_search]] and repeat it many times from a fresh reset, in case the level advances by cumulative repetition rather than a single pass.

## Applies When

- A [[../../game_types/sequence]] game where a short action pattern must be applied repeatedly (e.g. a counter or accumulator that needs N cycles).
- [[seq_search]] found a sequence that produces frame change but a single pass did not clear the level.

## Algorithm

(from `strat_action_sequence_search` in `src/admorphiq/agent_ensemble.py`, repeat phase)

1. Precondition: `best_change_seq` is non-empty and `best == 0` (no clear yet from the search phase).
2. For up to 5 outer attempts:
   a. Reset env.
   b. Replay `best_change_seq` up to 10 times back-to-back (for `ACTION6`, click a random coord).
   c. On `levels_completed` increase, record `name = "seq_repeat"`.
   d. Stop the inner loop on `WIN`/`GAME_OVER`; reset on `GAME_OVER`.

## Why It Generalizes

- Operates only on `FrameData` fields; the sequence to repeat is discovered at runtime by frame diff.
- No game internals, so it transfers across version hashes.

## Games Cleared

| Game | v1 | v2 |
|------|-----|-----|
| [[../../games/R11L]] | 1/6 | 1/6 |

## Observable Signature

The plan is the right pick when at DiscoveryReport time:

- The env is sequence-shaped (see [[seq_search]]'s observable signature) AND a single sequence pass shows progress-toward-goal without completing.
- A counter / accumulator visual (a bar filling, a number incrementing) suggests cumulative repetition clears the level.

## Falsification Signature

The plan has failed AND should be swapped when after execution it returns 0 levels AND:

- Repeating the best sequence 10× (×5 attempts) produced no `levels_completed` increase — the level does not advance by repetition.
- Repetition triggers `GAME_OVER` consistently — the pattern overshoots a target.

## Tunable Parameters

- outer attempts: 5. Effect: more restarts of the repeat loop.
- inner repeats: 10. Effect: longer cumulative application per attempt.
- `budget`: shared with [[seq_search]] (default 600). Effect: total action ceiling across both phases.

## Next-Best

When the falsification signature triggers, try (in priority order):

- [[seq_search]] — re-search for a different high-change sequence if repetition of the first did not work.
- [[click_rare]] — when the real trigger is a coordinate click.
- [[bfs_state_space]] — when the game is actually a navigable state space.

## Related

- [[seq_search]] — the search phase that produces the sequence repeated here
- [[../../game_types/sequence]]
- [[../../games/R11L]]

## Sources

- `src/admorphiq/agent_ensemble.py` — `strat_action_sequence_search` (repeat phase, `name = "seq_repeat"`)
- 2026-04-20 regression: R11L 1/6 on both v1 and v2 via this path
