"""Tests for the SU15 vacuum-merge delivery adapter (R56 iteration 10).

The iteration-10 rewrite replaced the falsified "click-to-steer player"
model (iterations 7-9) with the mechanic decoded from the game source: a
vacuum click pulls nearby fruits toward it, same-value overlaps merge to
value+1, and a level clears when the delivered-fruit multiset matches the
goal spec. These tests pin the durable contracts of that model — entity
classification (the "colour-0 player" was an animation ring and must never
be a fruit/goal), the balanced pairwise merge driver, delivery targeting,
and per-level state reset.
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.su15 import (
    Adapter,
    _classify,
    _inside_goal,
)


def _grid(size: int, bg: int, stamps: list[tuple[int, int, int, int, int]]) -> tuple[tuple[int, ...], ...]:
    """A blank ``size``x``size`` grid of ``bg`` with each ``(colour, r0, c0,
    r1, c1)`` rectangle painted on top."""
    g = [[bg] * size for _ in range(size)]
    for colour, r0, c0, r1, c1 in stamps:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                g[r][c] = colour
    return tuple(tuple(row) for row in g)


def _holey_goal(g: list[list[int]], r0: int, c0: int) -> None:
    """Paint a 9x9 colour-9 goal disk with transparent (background) corners,
    matching the game's ``0008hngjwqibfi`` sprite shape (density < 1.0)."""
    for r in range(r0, r0 + 9):
        for c in range(c0, c0 + 9):
            corner = (r in (r0, r0 + 8)) and (c in (c0, c0 + 8))
            edge_corner = (r - r0, c - c0) in {(0, 0), (0, 8), (8, 0), (8, 8), (0, 1), (1, 0), (8, 7), (7, 8)}
            if not (corner or edge_corner):
                g[r][c] = 9


def test_classify_ignores_the_vacuum_ring_colour():
    """Purpose: colour 0 is the vacuum-ring animation (``rgxlnsrafr``), not a
    game object — the exact artifact iterations 7-9 mis-tracked as a steered
    "player". It must never be classified as a fruit or goal.
    Expected feedback: failure means the adapter would again chase the ring
    instead of the real fruits, reproducing the falsified model."""
    grid = _grid(64, 5, [(0, 20, 20, 28, 28), (15, 40, 40, 42, 42)])
    goals, fruits, enemies = _classify(grid)
    assert all(f["color"] != 0 for f in fruits)
    assert all(g["color"] != 0 for g in goals)


def test_classify_reads_fruit_value_from_colour_including_size_one_zeros():
    """Purpose: fruit value is the colour's index in the source palette, and
    value-0 fruits render as a SINGLE cell (sprite "0" is 1x1) — they must
    still be detected (the merge cascade starts from them).
    Expected feedback: failure means merge-heavy levels are unplayable
    because the base value-0 fruits are invisible to the planner."""
    g = [[5] * 64 for _ in range(64)]
    g[30][30] = 10  # value 0, size 1
    for r in range(20, 23):
        for c in range(20, 23):
            g[r][c] = 15  # value 2, 3x3
    goals, fruits, enemies = _classify(tuple(tuple(row) for row in g))
    vals = sorted(f["color"] for f in fruits)
    assert 10 in vals and 15 in vals


def test_classify_distinguishes_goal_disk_from_solid_block():
    """Purpose: a colour-9 GOAL is a holey disk (density < 1.0); a solid
    colour-9 block is a value-6 fruit. They must be told apart so deliveries
    aim at real goals.
    Expected feedback: failure means either the goal is missed (no delivery
    target) or a value-6 fruit is mistaken for a goal."""
    g = [[5] * 64 for _ in range(64)]
    _holey_goal(g, 30, 30)
    for r in range(15, 23):
        for c in range(15, 23):
            g[r][c] = 9  # solid 8x8 value-6 fruit
    goals, fruits, enemies = _classify(tuple(tuple(row) for row in g))
    assert len(goals) == 1
    assert any(f["color"] == 9 for f in fruits)


def test_classify_treats_sparse_colour7_star_as_enemy_not_fruit():
    """Purpose: colours 7 and 14 are used by BOTH a fruit value (7/8, a solid
    block) and an enemy (a sparse star). A low-density colour-7 cluster is an
    enemy, not a value-7 fruit.
    Expected feedback: failure means an enemy is chased as a deliverable
    fruit, or steered into (losing the run)."""
    g = [[5] * 64 for _ in range(64)]
    # sparse X star of colour 7 in a 4x5 bbox (~8 cells, density ~0.4)
    for r, c in [(20, 22), (21, 21), (21, 23), (22, 20), (22, 24), (23, 21), (23, 23)]:
        g[r][c] = 7
    goals, fruits, enemies = _classify(tuple(tuple(row) for row in g))
    assert any(e["color"] == 7 for e in enemies)
    assert not any(f["color"] == 7 for f in fruits)


def test_deliver_click_stays_within_grab_range_and_in_play_area():
    """Purpose: a delivery click must be close enough to the fruit that the
    vacuum grabs it (within the radius-8 selection window of the fruit's
    edge) while advancing toward the destination, and must land inside the
    playable rows.
    Expected feedback: failure means clicks either miss the fruit entirely
    (no motion) or land in the ignored HUD/border rows."""
    a = Adapter()
    fruit = {"color": 15, "bbox": (30, 30, 32, 32), "centroid": (31.0, 31.0), "size": 9}
    row, col = a._deliver_click(fruit, (10.0, 10.0), enemies=[])
    # near edge of fruit to the click must be within the vacuum radius
    edge = (31.0 - 1.5, 31.0 - 1.5)  # toward dest
    assert ((row - 31.0) ** 2 + (col - 31.0) ** 2) ** 0.5 <= 8 + 2  # centroid->click within grab band
    assert 10 <= row <= 62


def test_deliver_click_flips_away_from_an_adjacent_enemy():
    """Purpose: when an enemy sits within the danger radius of the fruit, the
    click must pull the fruit AWAY from the enemy (opposite side), not toward
    the goal through it.
    Expected feedback: failure means the planner steers fruits into enemies,
    losing value/the run on every enemy level."""
    a = Adapter()
    fruit = {"color": 15, "bbox": (30, 30, 32, 32), "centroid": (31.0, 31.0), "size": 9}
    enemy = {"color": 13, "bbox": (33, 31, 35, 33), "centroid": (34.0, 32.0), "size": 9}
    # goal is beyond the enemy (down-right); the click must go up-left instead
    row, col = a._deliver_click(fruit, (40.0, 40.0), enemies=[enemy])
    assert row < 31.0 and col < 31.0


def test_merge_move_gathers_lowest_value_pair_first():
    """Purpose: value climbs only by merging exact pairs in sequence, lowest
    value first (the source collapses a same-value clump to ONE value+1, so
    piling is wrong). With value-0 and value-1 pairs both present, the driver
    must act on the value-0 pair.
    Expected feedback: failure means the cascade strands an unmatched
    higher-value fruit and never reaches the target value."""
    a = Adapter()
    fruits = [
        {"color": 10, "bbox": (20, 20, 20, 20), "centroid": (20.0, 20.0), "size": 1},
        {"color": 10, "bbox": (20, 24, 20, 24), "centroid": (20.0, 24.0), "size": 1},
        {"color": 6, "bbox": (40, 40, 41, 41), "centroid": (40.5, 40.5), "size": 4},
        {"color": 6, "bbox": (40, 44, 41, 45), "centroid": (40.5, 44.5), "size": 4},
    ]
    click = a._merge_move(fruits, enemies=[])
    assert click is not None
    # the value-0 pair is close (dist 4 <= _MERGE_DIST) -> click their midpoint
    assert abs(click[0] - 20.0) <= 1 and abs(click[1] - 22.0) <= 1


def test_merge_move_returns_none_without_a_pair():
    """Purpose: with no same-value pair, there is nothing to merge and the
    planner should fall through to delivery.
    Expected feedback: failure means the planner loops on merge attempts for
    an already-distinct board (e.g. the L0 single-fruit case)."""
    a = Adapter()
    fruits = [
        {"color": 10, "bbox": (20, 20, 20, 20), "centroid": (20.0, 20.0), "size": 1},
        {"color": 15, "bbox": (40, 40, 42, 42), "centroid": (41.0, 41.0), "size": 9},
    ]
    assert a._merge_move(fruits, enemies=[]) is None


def test_inside_goal_credits_a_centred_fruit():
    """Purpose: a fruit whose centre is inside a goal's (padding-inflated)
    bbox counts as delivered.
    Expected feedback: failure means delivered fruits are re-targeted
    forever, or the win is never recognised as reachable."""
    goal = {"color": 9, "bbox": (30, 30, 38, 38), "centroid": (34.0, 34.0), "size": 59}
    inside = {"color": 15, "bbox": (33, 33, 35, 35), "centroid": (34.0, 34.0), "size": 9}
    outside = {"color": 15, "bbox": (10, 10, 12, 12), "centroid": (11.0, 11.0), "size": 9}
    assert _inside_goal(inside, goal)
    assert not _inside_goal(outside, goal)


def test_adapter_resets_per_level_state_on_level_up():
    """Purpose: goal anchors and the click-lead are properties of the current
    level's layout and must reset when ``levels_completed`` advances (each
    level is a fresh board).
    Expected feedback: failure means level 2+ carries stale goal anchors from
    level 1, mis-filtering its real goals."""
    a = Adapter()
    a._levels_seen = 0
    a._goal_anchors = [(1.0, 1.0)]
    a._lead_px = 99.0
    grid = tuple(tuple(5 for _ in range(64)) for _ in range(64))
    frame = SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name="NOT_FINISHED"),
        levels_completed=1,
        available_actions=[6],
    )
    a.choose_action([], frame)
    assert a._levels_seen == 1
    assert a._lead_px != 99.0
