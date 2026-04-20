---
type: concept
instantiating_games: [ALL]
detection_frame_only: yes
---

# Sprite Cluster

> A connected component of same-color pixels in the frame. The universal primitive for detecting entities without reading game internals.

## Definition

Given a 2D frame grid where each cell has a color index, a **sprite cluster** is a maximal set of adjacent cells (4- or 8-connectivity) all sharing the same color (and not the background color).

For a multi-layer frame, clusters are typically computed per layer and optionally merged.

## Why it is the universal primitive

Every entity relevant to gameplay appears in the frame as pixels. Collecting those pixels into connected clusters gives you:
- **Player** — the cluster that moves on directional input
- **Walls** — clusters that never move and block the player
- **Blocks** — clusters that move on player contact but not on idle
- **Goals** — persistent clusters with distinct color
- **Interactive objects** — clusters that change on ACTION5/6
- **Enemies** — clusters that move autonomously

Internal attribute names, sprite tags, and level dictionaries are all derivable from cluster observations — without reading any internal.

## Detection pseudocode

```python
def find_clusters(frame_layer: np.ndarray, background_color: int = 0) -> list[Cluster]:
    visited = np.zeros_like(frame_layer, dtype=bool)
    out = []
    for y, x in np.ndindex(frame_layer.shape):
        if visited[y, x] or frame_layer[y, x] == background_color:
            continue
        color = frame_layer[y, x]
        # BFS from (y, x) over same-color neighbors
        cluster = bfs_flood_fill(frame_layer, (y, x), color, visited)
        out.append(Cluster(color=color, cells=cluster, centroid=mean(cluster)))
    return out
```

`src/admorphiq/perception/frame_analyzer.py` provides `find_color_positions(frame, color_idx)` as the existing primitive.

## Classification of clusters

After finding clusters, probe each with one action and observe:

| Probe | Classification |
|-------|----------------|
| cluster moves by (1, 0) when ACTION1 pressed | player |
| cluster moves by (1, 0) when player presses ACTION1 into it | pushable block |
| cluster disappears / changes color when clicked | interactive |
| cluster never moves regardless of action | wall or goal (disambiguate by color rarity) |
| cluster moves on its own between frames | enemy (autonomous) or gravity-affected (see [[gravity]]) |

## Instantiating games

Every game in this wiki uses sprite clusters implicitly. Games where the solver explicitly relies on cluster detection:

- [[../games/AR25]] — player cluster for BFS
- [[../games/M0R0]] — player + walls
- [[../games/BP35]] — player + blocks + goal
- [[../games/SU15]] (after frame-only refactor) — fruits + enemies + goals
- [[../games/CN04]], [[../games/LP85]], [[../games/VC33]] — target cluster for rare-color click

## Pitfalls

- **Noisy clusters from animations**: same logical entity may flicker between colors; use temporal smoothing
- **Cluster splitting**: an entity that spans two layers may register as two clusters; merge by overlap

## Related concepts

- [[frame_hashing]]
- [[../lessons/frame_diff_as_probe]] — clusters are detected via diffs

## Sources

- `src/admorphiq/perception/frame_analyzer.py` — existing primitive
