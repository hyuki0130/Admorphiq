---
type: game_type
examples: [S5I5]
refactor_status: brittle_only
---

# Slider Puzzle

> Resize / rotate sliders to move linked goal markers into target positions.

## Identifying features

- Elongated rectangular sprites (sliders) with distinct ends
- Small circular sprites (goal markers) attached to each slider
- Small isolated clickable sprites (rotate handles) adjacent to each slider

## Discovery protocol

1. Detect sliders by elongated connected components of uniform color
2. Detect rotate handles by isolated small clusters adjacent to slider ends
3. Detect goals by distinct color, attached to slider
4. Probe: clicking slider end → goal moves by `3` units in slider axis; clicking rotate → axis rotates 90° (costs a step)

## Canonical strategy

Discrete planning on (slider_axes, goal_positions) state; minimize total click + rotation cost to reach target positions.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/S5I5]] | 1/8 | 0/8 | s5i5_slider (brittle) |
