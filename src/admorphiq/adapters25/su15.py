"""script25 quarantined adapter: SU15 (vacuum-merge delivery puzzle).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. *** Imports: stdlib + admorphiq.kernels + admorphiq.adapters25.base
ONLY (scripts/adapters25_lint.py enforces this).

**R56 iteration 10 — the mechanic was DECODED from the game source
(dev-time read of ``environment_files/su15/*/su15.py``; the obfuscated
internals are level data + physics, legal to read at dev time, and the
runtime adapter below stays strictly frame-only). This CORRECTS the
iteration-8/9 "click-to-steer navigation" model, which was WRONG.**

The decode, entity by entity (source names in parens):

* **Vacuum click (``axaxyjxqoe``).** ``ACTION6(x, y)`` runs a vacuum at the
  clicked grid cell. Every FRUIT (and enemy) whose bounding box is within a
  radius of ``kacsjmxae = 8`` px of the click (``kcqeohsztd``) is pulled
  TOWARD the click over ``gdamdvokm = 4`` sub-steps of up to ``ikskfqldi =
  4`` px/axis each (``pkrdtzfrth``), clamped so it stops at the click point.
  Net: a selected fruit jumps up to ~16 px toward the click, capped at the
  click itself. The whole animation resolves inside ONE agent action
  (the engine only ``complete_action``s after it settles), so from the
  agent's view each ACTION6 is atomic: click → nearby fruits jump toward
  it → same-value overlaps merge → win check.
* **THE "COLOUR-0 PLAYER" WAS AN ARTIFACT.** Iterations 7-9 tracked a
  ~48-52 cell colour-0 blob that "lands on every click" and modelled it as
  a steered player. It is the VACUUM RING (``vmgyqpnfu`` /
  ``rgxlnsrafr``): a radius-8 annulus of colour-``pynrefijae`` (= 0) pixels
  drawn centred on the click; ~2·π·8 ≈ 50 cells, bbox ~16×16. Measured
  proof: in the gold trace its centroid in ``frames[i]`` equals the
  PREVIOUS click's ``(x=col, y=row)`` exactly. It is not a game object —
  colour 0 is ignored entirely by this adapter.
* **Fruits (``lkujttxgs``, tag "fruit").** Solid colour blocks; value 0..8
  maps to colour ``laalrfemee = [10, 6, 15, 11, 12, 8, 9, 7, 14]`` and to a
  growing sprite size (1×1, 2×2, 3×3, 4×4, 5×5, 7×7, 8×8, 9×9, 10×10). Two
  fruits of the SAME value that overlap after a pull merge into one of
  value+1 at their centroid (``mdetahtgad`` union-find) — 2048-style.
* **Goal zones (``powykypsm``, tag "goal").** Static colour-9 disks with
  transparent (holey) corners — density < 1.0, and they never move. A
  fruit whose centre lands inside a goal's SPRITE bbox counts as delivered.
* **Enemies (``fezhhzhih``, tag "enemy"/2/3).** Sparse star sprites, colours
  7 / 14 / 13. They chase the nearest fruit each step and DOWNGRADE it by 1
  on contact (``wwvumwkgbn``); steering a fruit into one, or clicking a
  fruit toward one, loses value / the run. Colours 7 and 14 collide with
  fruit values 7 and 8, so an enemy is told apart from a same-colour fruit
  by DENSITY (star ≈ 0.35-0.5, solid block ≈ 0.9-1.0); colour 13 is enemy
  only.
* **Win (``cbdhpcilgb``).** The multiset of delivered-fruit VALUES must
  EXACTLY equal the level's goal spec (plus any enemy-in-goal count). The
  spec is level data ``xkstxyqbs`` — see the named divergence below.

**What this adapter does (frame-only greedy gather-and-deliver, correct
mechanic).** Detect goal zones + fruits (value from colour) + enemies each
call, then: (a) if two same-value non-delivered fruits sit close, click
their midpoint to MERGE them a level up; (b) otherwise pull the
highest-value not-yet-delivered fruit one hop toward its nearest goal by
clicking ``point_toward`` it, at an absolute offset kept inside the
radius-8 selection window so the fruit is actually grabbed; (c) nudge a
fruit away from an adjacent enemy instead of into it. Steering is composed
from :func:`admorphiq.kernels.point_toward`; segmentation from
:func:`admorphiq.kernels.find_regions`; the last click's effect is measured
with :func:`admorphiq.kernels.frame_diff` for step-size escalation on a
dead click.

**NAMED DIVERGENCES (banked, per the team's "bank, don't re-derive"
convention).**

1. **Exact-count win + semi-observable spec.** ``cbdhpcilgb`` requires the
   delivered multiset to match ``xkstxyqbs`` EXACTLY (over- or
   under-delivery both fail). That spec is level data, not cleanly on the
   frame — the top HUD hint band mixes a fixed colour legend
   (``0012qpdeinaukn``) with target-fruit sprites, and measured against the
   9 known specs it both UNDER-specifies (L2 hint shows only v3, spec is
   {v3,v2}) and OVER-specifies (L3 hint shows v3+v2, spec is {v3}). So a
   frame-only agent cannot read the exact target multiset. This adapter
   therefore reliably handles only the pure-delivery case (a single
   target-value fruit already present — the L0 shape); the merge-heavy
   levels (L1-L8 combine 8+ value-0 fruits up to the target) need the spec
   to prune merge order and are best-effort here.
2. **Sprite-bbox collision padding.** The goal/fruit collision uses SPRITE
   bounding boxes, which include the sprite's transparent border and are
   thus a px or two LARGER than the frame-visible coloured pixels. A
   frame-only delivery lands a fruit when its visible centre is inside the
   detected (slightly smaller) goal box, so it must aim for the goal centre,
   not its edge — handled by aiming at the goal centroid.
3. **Enemy dynamics not simulated.** Enemy chase/downgrade is avoided
   heuristically (don't click a fruit toward an adjacent enemy), not planned
   against — deep levels whose only path crosses enemy territory are out of
   scope for this greedy planner.
"""

from __future__ import annotations

from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    available_action_ids,
    canonical_layer,
    click_action,
    has_frame,
    reset_action,
    state_name,
)
from admorphiq.kernels import find_regions, frame_diff, point_toward

GAME_ID = "su15"

Cell = tuple[int, int]  # (row, col)
Region = dict[str, Any]

_GIVEUP_DEFAULT = 4000

# From the game source (dev-time read; runtime uses none of these as game
# internals — they are the physics constants the frame-only planner mirrors).
_BACKGROUND = 5  # BACKGROUND_COLOR
_PADDING = 3  # PADDING_COLOR (frame border + decorative diagonal line)
_ARENA = 4  # the play-field panel colour (one huge region)
_RING = 0  # pynrefijae — the vacuum-ring animation colour (NOT an object)
# value -> colour (laalrfemee); inverted to colour -> value.
_VAL_COLORS = (10, 6, 15, 11, 12, 8, 9, 7, 14)
_COLOR_VAL = {c: v for v, c in enumerate(_VAL_COLORS)}
_GOAL_COLOR = 9  # goal-zone disks (also fruit value 6 — told apart by density/staticness)
# Colours a star-shaped ENEMY can render as (7 and 14 collide with fruit
# values 7/8, disambiguated by size at gap=0; 13 is enemy-only).
_ENEMY_ONLY_COLOR = 13
_ENEMY_AMBIGUOUS = (7, 14)
# At gap=0 an enemy star of colour 7/14 fragments into pieces this small or
# smaller, while a value-7/8 fruit is a solid 81/100-cell block.
_ENEMY_MAX_FRAGMENT = 5

# Rows above the play field carry the HUD (gvvyzrusqq = 10 in the source);
# row 63 (qsqeqpepjy) is the step-counter bar. Clicks outside 10..62 are
# ignored by the engine, and objects there are chrome, not gameplay.
_PLAY_TOP = 10
_PLAY_BOTTOM = 62
_GRID = 64

# Vacuum radius (kacsjmxae). A fruit is grabbed only if its bbox is within
# this many px of the click, so a delivery click must stay this close to the
# fruit while still reaching toward the destination.
_VACUUM_RADIUS = 8
# Absolute px a delivery click is placed beyond the fruit's own half-extent
# toward the destination: keeps the fruit's near edge ~this far from the
# click (<= _VACUUM_RADIUS) so it is reliably selected, while advancing it.
_LEAD_PX = 6
# Escalation of the lead when a click moved nothing (a fruit that failed to
# grab needs the click nearer / the step larger); reset on a useful click.
_LEAD_GROWTH = 1.4
_MAX_LEAD_PX = 14.0
# A same-value fruit pair within this centroid distance is merged by clicking
# their midpoint. Must stay under ~2×_VACUUM_RADIUS so the SINGLE midpoint
# click actually grabs BOTH fruits (each within radius 8 of the midpoint);
# measured: at 22 a ~19px-apart pair's midpoint sat >8px from each fruit, a
# dead click that stalled the cascade. Farther pairs are gathered instead by
# pulling one member toward the other (the _deliver_click branch).
_MERGE_DIST = 14.0
# A fruit whose visible centre is within this margin inside a goal's detected
# bbox is treated as delivered (accounts for the sprite-bbox padding
# divergence: aim for, and credit near, the goal centre).
_DELIVERED_MARGIN = 1
# An enemy centroid closer than this to a fruit makes delivering that fruit
# risky — nudge it away from the enemy instead of toward the goal.
_ENEMY_DANGER = 9.0
# A dominant frame change smaller than this (px, on the diff bbox) counts as
# "nothing usefully moved" for lead escalation.
_MIN_USEFUL_DIFF = 1.5


def _bbox_hw(region: Region) -> tuple[float, float]:
    r0, c0, r1, c1 = region["bbox"]
    return (r1 - r0 + 1) / 2.0, (c1 - c0 + 1) / 2.0


def _density(region: Region) -> float:
    r0, c0, r1, c1 = region["bbox"]
    area = (r1 - r0 + 1) * (c1 - c0 + 1)
    return region["size"] / area if area > 0 else 0.0


def _in_play(region: Region) -> bool:
    r0 = region["bbox"][0]
    r1 = region["bbox"][2]
    return r0 >= _PLAY_TOP and r1 <= _PLAY_BOTTOM


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def _classify(grid: tuple[tuple[int, ...], ...]) -> tuple[list[Region], list[Region], list[Region]]:
    """Return ``(goals, fruits, enemies)`` from one frame, chrome removed.

    Goals are colour-9 non-solid disks in the play field (holey corners,
    density < 1.0 — a solid same-colour value-6 fruit is not a goal).
    Fruits are solid value-coloured blocks; the two enemy-ambiguous colours
    (7, 14) are a fruit only when solid, an enemy when sparse. Colour 13,
    the vacuum ring (0), the arena (4), padding (3) and background (5) are
    never fruits.
    """
    # gap=0 (no fusion): value-0 fruits are single cells that sit adjacent to
    # each other, and fusing them would hide a mergeable pair as one region
    # (measured: the merge cascade stalled on a fused size-2 zero clump). A
    # solid fruit block or a holey goal disk is connected regardless, so gap=0
    # keeps each whole; only the sparse enemy stars fragment, handled below by
    # a size floor.
    regions = [r for r in find_regions(grid, background=_BACKGROUND, gap=0) if _in_play(r)]
    goals: list[Region] = []
    fruits: list[Region] = []
    enemies: list[Region] = []
    for r in regions:
        color = r["color"]
        if color in (_RING, _PADDING, _ARENA, _BACKGROUND):
            continue
        if color == _GOAL_COLOR:
            # A goal disk is not fully solid; a solid colour-9 block is a
            # (rare) value-6 fruit.
            if _density(r) < 0.92 and r["size"] >= 24:
                goals.append(r)
            elif color in _COLOR_VAL:
                fruits.append(r)
            continue
        if color == _ENEMY_ONLY_COLOR:
            enemies.append(r)
            continue
        if color in _ENEMY_AMBIGUOUS and r["size"] <= _ENEMY_MAX_FRAGMENT:
            # A value-7/8 fruit is a solid 9×9/10×10 block (81/100 cells); an
            # enemy star of the same colour fragments into tiny pieces at
            # gap=0. Size alone separates them cleanly.
            enemies.append(r)
            continue
        if color in _COLOR_VAL:
            # Colour alone is unambiguous for the value colours; the play-area
            # and chrome filters above already removed ring/arena/padding/HUD.
            fruits.append(r)
    return goals, fruits, enemies


def _value(region: Region) -> int:
    return _COLOR_VAL.get(region["color"], -1)


def _centroid(region: Region) -> tuple[float, float]:
    return region["centroid"]


def _inside_goal(fruit: Region, goal: Region) -> bool:
    r, c = _centroid(fruit)
    r0, c0, r1, c1 = goal["bbox"]
    m = _DELIVERED_MARGIN
    return (r0 - m) <= r <= (r1 + m) and (c0 - m) <= c <= (c1 + m)


def _nearest(target: tuple[float, float], regions: list[Region]) -> Region | None:
    if not regions:
        return None
    return min(regions, key=lambda r: _dist(target, _centroid(r)))


def _clamp_click(row: float, col: float) -> Cell:
    r = int(round(row))
    c = int(round(col))
    r = max(_PLAY_TOP, min(_PLAY_BOTTOM, r))
    c = max(0, min(_GRID - 1, c))
    return (r, c)


class Adapter(GameAdapter):
    """Frame-only vacuum gather-and-deliver play, composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True
        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        # Absolute lead offset (px) for the next delivery click; escalated on
        # a dead click, reset on a useful one. A property of vacuum strength,
        # so it persists across levels.
        self._lead_px = float(_LEAD_PX)
        self._pending_click: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        # Static-goal memory: colour-9 disks that have not moved. Seeded on
        # level start, used to prefer true (static) goals over a stray
        # value-6 fruit. Reset per level.
        self._goal_anchors: list[tuple[float, float]] = []

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state in ("NOT_PLAYED", "GAME_OVER") or not has_frame(latest_frame):
            self._pending_click = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        grid = canonical_layer(latest_frame)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._pending_click = None
            self._prev_grid = None
            self._lead_px = float(_LEAD_PX)
            self._goal_anchors = [_centroid(g) for g in _classify(grid)[0]]

        self._step += 1
        self._observe_result(grid)

        _simple_ids, action6_ok = available_action_ids(latest_frame)
        if not action6_ok:
            self._prev_grid = grid
            self._pending_click = None
            return reset_action()

        target = self._plan(grid)
        self._prev_grid = grid
        self._pending_click = target
        row, col = target
        return click_action(x=col, y=row)

    # ── measurement: did the last click move anything? ──────────────────

    def _observe_result(self, grid: tuple[tuple[int, ...], ...]) -> None:
        """Escalate the click lead on a dead click, reset it on a useful one."""
        before = self._prev_grid
        pending = self._pending_click
        self._pending_click = None
        if before is None or pending is None:
            return
        diff = frame_diff(before, grid)
        if diff["count"] == 0:
            self._lead_px = min(_MAX_LEAD_PX, self._lead_px * _LEAD_GROWTH)
            return
        r0, c0, r1, c1 = diff["bbox"]
        span = max(r1 - r0, c1 - c0)
        if span < _MIN_USEFUL_DIFF:
            self._lead_px = min(_MAX_LEAD_PX, self._lead_px * _LEAD_GROWTH)
        else:
            self._lead_px = float(_LEAD_PX)

    # ── planning: where to click next ────────────────────────────────────

    def _plan(self, grid: tuple[tuple[int, ...], ...]) -> Cell:
        goals, fruits, enemies = _classify(grid)
        goals = self._prefer_static_goals(goals)
        if not goals:
            # The goal disk can be transiently occluded by a fruit/enemy
            # passing over it (measured on L3, where detection dropped to zero
            # mid-level and delivery stalled). Fall back to the level-start
            # anchor position so delivery keeps aiming at the true goal.
            goals = self._anchor_goals()
        if not goals or not fruits:
            return (_GRID // 2, _GRID // 2)

        # Value climbs only by merging exact PAIRS in sequence (the source's
        # union-find collapses a clump of N same-value fruits to ONE value+1,
        # not N/2 — so piling everything together is wrong; pairs must be
        # brought together one stage at a time). Merge the lowest value that
        # still has ≥2 fruits before delivering anything, so the board funnels
        # up to a single top-value fruit rather than stranding an unmatched
        # {value-2, value-1} leftover that can never combine.
        merge = self._merge_move(fruits, enemies)
        if merge is not None:
            return merge

        undelivered = [f for f in fruits if not any(_inside_goal(f, g) for g in goals)]
        if not undelivered:
            return (_GRID // 2, _GRID // 2)
        # No same-value pair left: deliver the highest-value fruit to its
        # nearest goal (the L0 pure-delivery case, and the tail of any merge
        # cascade once a single top fruit remains).
        fruit = max(undelivered, key=lambda f: (_value(f), f["size"]))
        goal = _nearest(_centroid(fruit), goals)
        if goal is None:
            return (_GRID // 2, _GRID // 2)
        return self._deliver_click(fruit, _centroid(goal), enemies)

    def _anchor_goals(self) -> list[Region]:
        """Pseudo-goal regions at the level-start disk centroids.

        Used only when live goal detection returns nothing (transient
        occlusion). The goals are static in this game, so their start-of-level
        position is a valid delivery target for the whole level. A small bbox
        around the anchor lets :func:`_inside_goal` still credit a delivery.
        """
        out: list[Region] = []
        for r, c in self._goal_anchors:
            ri, ci = int(r), int(c)
            bbox = (ri - 4, ci - 4, ri + 4, ci + 4)
            out.append({"color": _GOAL_COLOR, "centroid": (r, c), "bbox": bbox, "size": 40})
        return out

    def _prefer_static_goals(self, goals: list[Region]) -> list[Region]:
        """Keep goals near a level-start anchor when anchors exist.

        A colour-9 region that has drifted from every level-start disk is a
        moving value-6 fruit mis-tagged as a goal; drop it. Falls back to the
        raw list when no anchors were captured (goal appears mid-level).
        """
        if not self._goal_anchors:
            return goals
        kept = [g for g in goals if any(_dist(_centroid(g), a) <= _VACUUM_RADIUS for a in self._goal_anchors)]
        return kept or goals

    def _merge_move(self, fruits: list[Region], enemies: list[Region]) -> Cell | None:
        """One click toward merging the lowest value that still has a pair.

        Picks the lowest value with ≥2 fruits, takes its two nearest members,
        and: clicks their midpoint once they are close enough for a single
        vacuum to overlap them (within _MERGE_DIST), otherwise pulls the pair
        member farther from the other toward its partner (composed via
        :meth:`_deliver_click`, which keeps the click inside grab range and
        dodges an adjacent enemy). Returns None when no value has a pair.
        """
        by_value: dict[int, list[Region]] = {}
        for f in fruits:
            by_value.setdefault(_value(f), []).append(f)
        pair_values = sorted(v for v, fs in by_value.items() if len(fs) >= 2)
        if not pair_values:
            return None
        group = by_value[pair_values[0]]
        a, b = self._nearest_pair(group)
        ac = _centroid(a)
        bc = _centroid(b)
        if _dist(ac, bc) <= _MERGE_DIST:
            return _clamp_click((ac[0] + bc[0]) / 2.0, (ac[1] + bc[1]) / 2.0)
        return self._deliver_click(a, bc, enemies)

    @staticmethod
    def _nearest_pair(group: list[Region]) -> tuple[Region, Region]:
        best: tuple[float, Region, Region] | None = None
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                d = _dist(_centroid(group[i]), _centroid(group[j]))
                if best is None or d < best[0]:
                    best = (d, group[i], group[j])
        assert best is not None  # caller guarantees len(group) >= 2
        return best[1], best[2]

    def _deliver_click(self, fruit: Region, dest: tuple[float, float], enemies: list[Region]) -> Cell:
        """Click one hop toward ``dest`` from ``fruit``, kept inside grab range.

        The click is placed ``half_extent + lead`` px along the fruit->dest
        ray, so the fruit's near edge stays within the vacuum radius and it
        is grabbed, while the pull advances it up to that far. If an enemy is
        closer than ``_ENEMY_DANGER`` to the fruit, the ray is flipped to pull
        the fruit AWAY from the enemy first.
        """
        src = _centroid(fruit)
        half = max(_bbox_hw(fruit))
        aim = dest
        threat = _nearest(src, enemies)
        if threat is not None and _dist(src, _centroid(threat)) <= _ENEMY_DANGER:
            tr, tc = _centroid(threat)
            aim = (2 * src[0] - tr, 2 * src[1] - tc)  # reflect: away from enemy
        reach = _dist(src, aim)
        step = min(reach, half + self._lead_px)
        row, col = point_toward(src, aim, distance=step)
        return _clamp_click(row, col)
