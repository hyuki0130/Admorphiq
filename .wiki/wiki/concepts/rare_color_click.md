---
type: concept
instantiating_games: [LP85, VC33]
detection_frame_only: yes
---

# Rare Color Click

> On some games the level advances when the agent clicks a specific pixel whose color is distinctly rare in the frame. Cheap to solve: cluster by color, find the smallest cluster of a non-background color, click its centroid.

## Definition

A game uses the rare-color-click pattern if:
- Level progression requires `ACTION6(x, y)` at a specific location
- That location has a distinct color index (e.g. color 8 or 9) appearing in a small cluster elsewhere not on screen
- Other actions have no or minimal effect

Observable from outside: clicking at the rare pixel triggers `levels_completed += 1`.

## Detection heuristics

1. Histogram color indices across the frame.
2. Identify colors with very small count (1–5 pixels).
3. Cluster those rare-color pixels.
4. Click each cluster centroid in turn; one of them will clear the level.

This is precisely what the [[../strategies/frame_only/click_rare]] strategy does (see `strat_click_rare` in `src/admorphiq/agent_ensemble.py`).

## Instantiating games

| Game | Rare color | Winning click |
|------|-----------|---------------|
| [[../games/LP85]] | 8 | (30, 4) |
| [[../games/VC33]] | 9 | (33, 60) |

## Key abstractions

- **Rare color** — a color index appearing in very few pixels in the current frame
- **Click centroid** — the center pixel of the rare color cluster

## Worked flow

```
frame_hist = Counter(frame.flatten())
rare_colors = [c for c, n in frame_hist.items() if 1 <= n <= 20 and c != background]
for color in rare_colors:
    pixels = find_color_positions(frame, color)
    cluster = largest_connected_component(pixels)
    cx, cy = centroid(cluster)
    env.ACTION6(cx, cy)
    if level_up_observed:
        remember (color, cx, cy) as winning click for this level
        break
```

## Related concepts

- [[sprite_cluster]]
- [[../game_types/click]]
- [[../strategies/frame_only/click_rare]]

## Related games

- [[../games/LP85]]
- [[../games/VC33]]

## Pitfalls

- **Decoration rare colors**: some frames have decorative rare-color pixels that don't trigger anything. Iterate through all rare colors, not just the rarest.
- **Multi-click sequences**: a few games need two or more rare-color clicks. Continue probing after the first doesn't clear.

## Sources

- `src/admorphiq/agent_ensemble.py` — `strat_click_rare` implementation
- 2026-04-20 regression: LP85 and VC33 both passed v1 and (VC33) v2 via this strategy
