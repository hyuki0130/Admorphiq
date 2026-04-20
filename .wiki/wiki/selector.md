# Strategy Selector

> Feature-driven dispatch rules used by the Hypothesis Engine LLM (selected LLM (Task #11 winner)).

Input: game classification output (from first 10-20 discovery actions) + frame statistics.
Output: ordered list of strategies to try.

## Classification Features

| Feature | Source | Options |
|---------|--------|---------|
| `available_actions` | `FrameData.available_actions` | subset of {1,2,3,4,5,6,7} |
| `has_action6` | derived | bool |
| `layer_count` | `len(FrameData.frame)` | 1..N |
| `dominant_colors` | histogram | list of color indices |
| `player_candidates` | color clustering + motion diff | 0..k positions |
| `changer_candidates` | static regions after ACTION1-5 | list of regions |
| `grid_like` | regular lattice detection | bool |

## Dispatch Rules (draft — to be populated as wiki grows)

1. **Movement + few simple actions + no ACTION6** → [[game_types/movement]] → try [[strategies/frame_only/bfs_state_space]]
2. **Only ACTION6 + sparse clicks matter** → [[game_types/click]] → try [[strategies/frame_only/click_rare]]
3. **ACTION6 + grid_like + clickable bits** → [[game_types/programming_puzzle]] → frame-only TN36-analog
4. **Multiple same-color sprites + merge behavior on proximity** → [[game_types/merge_puzzle]] → SU15-analog
5. **Movement + pushable blocks** → [[game_types/sokoban]] → KA59-analog with frame-only push detection
6. **None of the above** → fallback stack: `bfs_state_space` → `click_rare` → `seq_repeat` → `spell_cast`

## Anti-patterns (do not recommend)

- Any strategy in [[strategies/brittle/]] — only for reference, not execution
- `ml_continuation` as primary — only as continuation after another strategy progressed

## LLM Prompt Template (model-agnostic; target: selected LLM from Task #11)

```
You are a strategy selector. Given:
- Game features: {features}
- Wiki game_type page: {matching_game_type_md}
- Top-3 similar game pages: {top3_game_md}

Output JSON:
{
  "game_type": "<one of movement|click|programming_puzzle|merge_puzzle|sokoban|other>",
  "primary_strategy": "<frame_only strategy name>",
  "fallback_stack": ["...", "..."],
  "rationale": "<1-2 sentences>"
}
```
