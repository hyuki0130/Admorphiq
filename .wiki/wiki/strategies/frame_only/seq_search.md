---
type: strategy
name: seq_search
generalizes: yes
implementation: src/admorphiq/agent_ensemble.py
dispatched_from: strat_action_sequence_search in agent_ensemble.py
---

# seq_search

> Try random action sequences of length 4-8, scoring each by total frame change, looking for one that triggers level completion. Reads only frame diffs — no game internals.

## Applies When

- A [[../../game_types/sequence]] game: progression requires a short pattern of actions rather than a single click or a navigable path.
- The action set is small and the winning sequence is short (≤ 8 actions).
- No obvious mover sprite (so BFS over positions does not apply) and no single rare-color click target.

## Algorithm

(from `strat_action_sequence_search` in `src/admorphiq/agent_ensemble.py`, search phase)

1. Reset env. Build `usable = available_actions \ {7, 8}`.
2. For up to `budget // 20` trials:
   a. Reset, pick a random sequence length 4-8, sample that many actions from `usable`.
   b. Execute the sequence. For `ACTION6`, click a random `(x, y)`. Accumulate `frame_diff(before, after)` over the sequence.
   c. If `levels_completed` increased, record `name = f"seq_search_{seq_len}"`.
   d. Track the sequence with the highest total frame change (`best_change_seq`).
3. The recorded best-change sequence is handed to the [[seq_repeat]] phase if no clear yet.

## Why It Generalizes

- Uses only `FrameData.frame` (for `frame_diff`), `available_actions`, `state`, `levels_completed`.
- No sprite tags, no attribute reads. Random sampling + frame-diff scoring transfers to any game version.

## Games Cleared

| Game | v1 | v2 |
|------|-----|-----|
| [[../../games/R11L]] | 1/6 | 1/6 (via seq_repeat phase) |

## Observable Signature

The plan is the right pick when at DiscoveryReport time:

- Directional probes produce small/ambiguous diffs (no single mover sprite to BFS over).
- No isolated rare-color click marker (so [[click_rare]] does not apply).
- The action set is small, suggesting a short combinatorial trigger.

## Falsification Signature

The plan has failed AND should be swapped when after execution it returns 0 levels AND:

- `best_change_seq` is empty (no sequence produced any frame change) — actions are inert; the game needs coordinates, not action patterns.
- Many trials hit `GAME_OVER` early — random sequences are harmful; the game punishes exploration.
- The winning sequence is longer than 8 actions (out of the search depth).

## Tunable Parameters

- `budget`: default 600, range 200-2000. Effect: more trials (`budget // 20`) sample more sequences.
- sequence length range: 4-8 (`np.random.randint(4, 9)`). Effect: widen for longer triggers, narrow to focus search.

## Next-Best

When the falsification signature triggers, try (in priority order):

- [[seq_repeat]] — when a high-change sequence was found but a single pass did not clear (the trigger needs repetition).
- [[click_rare]] — when the trigger is a coordinate click rather than an action pattern.
- [[bfs_state_space]] — when a mover sprite exists and the game is actually navigation.

## Related

- [[seq_repeat]] — the repeat phase of the same function
- [[../../game_types/sequence]]
- [[../../games/R11L]]

## Sources

- `src/admorphiq/agent_ensemble.py` — `strat_action_sequence_search` (search phase)
- 2026-04-20 regression: R11L cleared via the seq_search → seq_repeat path
