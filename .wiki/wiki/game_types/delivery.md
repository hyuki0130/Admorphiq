---
type: game_type
examples: [WA30]
refactor_status: brittle_only
---

# Delivery Game

> A worker picks up items at pickup zones and delivers them to matching target zones; multiple items per level.

## Identifying features

- Distinct "worker" sprite that moves in response to directional actions
- Multiple pickup zones (often colored markers)
- Multiple target zones (often matching colors or symbols)
- Level advances only when all pickups have been delivered

## Discovery protocol

1. Identify worker via motion diff
2. Identify pickups: zones that change appearance when worker stands on them (or press ACTION5)
3. Identify targets: zones that accept a carried item (color match?)
4. Detect "holding" state via sprite color change on worker

## Canonical strategy

Min-cost matching (pickup → target pair) + movement BFS for each segment.

## Games and current results

| Game | v1 | v2 | Strategy |
|------|-----|-----|----------|
| [[../games/WA30]] | 2/9 | n/a | wa30_analytical (brittle) |

## Edge cases

- **Capacity > 1**: worker may carry multiple items; plan with TSP-like order
- **Target gates**: some targets open only after a certain pickup
