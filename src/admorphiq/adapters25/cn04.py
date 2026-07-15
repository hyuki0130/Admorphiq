"""script25 quarantined adapter: CN04 (connector-marker arrangement family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``.wiki/wiki/games/CN04.md`` (read for reference, not imported) historically
recorded CN04 as a "click" game cleared 1/5 on v1 by ``zig3_A2A4`` — a blind
alternating ACTION2/ACTION4 zig-zag. That classification is WRONG for the
mechanic and does not transfer: the only live env locally is the v2 hash
(``cn04-2fe56bfb``), on which the zig-zag scores 0. Reading the game source
(dev-time only; the adapter below acts from frame observations alone) and a
live probe (``scratchpad`` traces, offline) establish the real mechanic.

**Mechanic (measured, declared HERE — roles/hypothesis, not in any kernel)**:
CN04 is a rigid-arrangement / jigsaw-connector puzzle, NOT a click game.

- Exactly one sprite is ACTIVE at a time. The engine renders the active
  sprite's body in colour 0 (every other visible sprite keeps a native
  colour). ACTION6 on a sprite makes THAT sprite active (the previously
  active one reverts to its native colour).
- ACTION1/2/3/4 translate the active sprite by ONE grid cell
  (measured: up / down / left / right — but the sign is MEASURED per
  action, never assumed, exactly as ``m0r0`` measures its ``dir_map``).
  ACTION5 rotates the active sprite 90 degrees.
- Every sprite carries connector-marker stubs, all rendered as colour 8.
  A marker is SATISFIED (recoloured 3, frame-observable) when it lands on
  the same grid cell as another sprite's marker. The level WINS when every
  marker on every sprite is satisfied — i.e. the colour-8 count reaches 0.

**The hidden-pairing subtlety (measured, load-bearing)**: the engine's win
check pairs markers by their ORIGINAL colour (two source colours, 8 and 13,
both remapped to display-8 — so the two are visually indistinguishable). A
geometric coincidence therefore recolours BOTH stubs to 3 (satisfying the
*display* rule) yet may FAIL the win if the hidden 8<->13 identities are
swapped. Measured directly on level 1: making the active sprite's 2-marker
line vertical via ONE ACTION5 and translating it exactly onto the target
line recolours all 4 stubs to 3 but does NOT win (chirality wrong); doing it
via THREE ACTION5 (the 180-degree-opposite orientation, same visible line
shape) DOES win. Because the adapter cannot SEE 8-vs-13, it treats a
full coincidence with no WIN as a wrong-chirality signal and rotates 180
degrees (two more ACTION5) to swap the endpoints, then re-aligns. At most a
handful of orientations exist, so this terminates.

**Grey masking (levels 3-6, ``GreyMasking`` in the source)**: non-active
sprites — and their marker stubs — are rendered as background, so the target
markers are simply INVISIBLE until a sprite is selected. Those levels are a
memory/exploration problem the frame-only signals here cannot fully see.

**Measured coverage / banked walls (v2 hash ``cn04-2fe56bfb``, the only
local env)**:
  - **Level 1 — CLEARED** generically, ~36 actions (one chirality RESET +
    a rotate + an exact translate), ``game_score`` 0.031 on the 6-level RHAE.
  - **Level 2 — multi-piece pairing IMPLEMENTED; PAIR A solves, pair B
    banked.** Two fixes unblocked L2: (1) a **stale-render skip** — a mid-game
    level-up shows one transition frame (the old board, no colour-8 stubs)
    before the engine's one-step ``next_level`` delay draws the real board, so
    the adapter idles one benign action until stubs appear (``_awaiting_render``);
    (2) **geometric partner-matching** (``_partner_group``) — L2 has 4 sprites
    with stub counts [2, 4, 4, 2], but pairing is by STUB GEOMETRY not sprite
    count (the two 2-stub sprites are a diagonal pair vs a horizontal pair —
    NOT congruent). The partner is the k-stub subset of the other sprites'
    stubs whose pairwise-distance signature matches the active sprite's own
    stubs (rotation/reflection invariant — the geometric core of
    ``kernels.assign_pairs``). With this, the active 2-stub sprite correctly
    locks a congruent diagonal target sub-pair on the 4-stub sprite, orients,
    translates, and PAIR A coincides — then ``_advance_to_next_pair`` re-locks
    for the next pair. Re-selection of the next sprite is occlusion-robust
    (``_solid_click_cell``): a box-shaped sprite's centroid is a transparent
    HOLE, so a centroid click selects nothing — clicking a SOLID cell outside
    the overlapping active body is what actually switches the active piece
    (verified live: the active body moves to the newly-clicked sprite). **Pair
    B is banked at the ASSIGNMENT step**: the second active sprite (4 stubs)
    then finds no congruent partner and rotates without latching, because after
    pair A the remaining stubs no longer split into clean same-sprite pairs — a
    sprite's stubs pair INDIVIDUALLY across several sprites (the active's 2
    diagonal stubs matched a diagonal SUB-pair of a 4-stub sprite, leaving that
    sprite's other 2 stubs to pair elsewhere). The GLOBAL stub-to-stub
    assignment was then VALIDATED offline before building, and it surfaces a
    genuine FOURTH structure: a greedy congruence mover-ordering (repeatedly
    pick any sprite whose full stub set is congruent to a stationary subset,
    solve it, remove those stubs) gets STUCK — after a few pairs it strands two
    remaining pairs that are NOT congruent to each other (measured: a dist-12.4
    pair on one sprite and a dist-16.2 pair on another), so neither can move
    onto the other. Stub CONSUMPTION changes later congruences, so a valid
    solve needs a GLOBAL constraint-satisfaction over all 12 stubs at once
    (which 2-subsets pair AND a mover ordering under which every mover's full
    stub set maps congruently), not the greedy per-mover search. Per the
    round's explicit stop rule, this is BANKED at the fourth layer: the durable
    value shipped is the reusable machinery (stale-frame skip, geometric
    congruence pairing, occlusion-robust selection) plus the located wall.
    Level 3+ additionally hide the targets (grey masking) — a separate
    select-and-probe-memory increment, left banked.

**HUD**: row 0 is a step-countdown bar drawn in colours 0 and 4 (the source
``lvealyvptn.render_interface`` writes the top scanline). Colour 0 there is
NOT active-sprite body, so the adapter masks row 0 to background before any
segmentation — otherwise the depleting bar pollutes the colour-0 "active
sprite" reading.

Composition from ``admorphiq.kernels``:
  - :func:`admorphiq.kernels.find_regions` segments the frame into the
    active body (colour 0), the marker stubs (colour 8), and the native
    sprites — the ONLY perception primitive used; the adapter never scans
    pixels itself.

Everything else — "colour 0 = active sprite", "colour 8 = connector marker",
"a marker near the active body is mine", the rigid-transform alignment plan,
and the chirality retry — is role assignment / mechanic hypothesis declared
in THIS module, per the script25 contract (adapters may declare semantics
but may not hardcode coordinates, palettes, target sequences, pixel
algorithms, or their own search).
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    available_action_ids,
    canonical_layer,
    click_action,
    has_frame,
    most_common_color,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import find_regions

GAME_ID = "cn04"

Cell = tuple[int, int]
Region = dict[str, Any]

_ACTIVE_COLOR = 0
_MARKER_COLOR = 8
_SATISFIED_COLOR = 3

_GIVEUP_DEFAULT = 4000
# A stub is "mine" when its centroid sits within this many measured cell
# widths of the active body's bbox. Markers hang one cell off the body edge
# (measured), so a 2-cell margin captures them without ever reaching a
# distinct sprite on the far side of the board.
_ATTACH_CELLS = 2.5


def _centroid_px(region: Region) -> Cell:
    r, c = region["centroid"]
    return (round(r), round(c))


def _sign(v: int) -> int:
    return (v > 0) - (v < 0)


def _mask_hud(grid: tuple[tuple[int, ...], ...], bg: int) -> tuple[tuple[int, ...], ...]:
    """Row 0 (the step-countdown bar) replaced by background.

    Pure reshape: the source draws the countdown bar on the top scanline in
    colours 0 and 4, so leaving row 0 in would misread the depleting bar as
    active-sprite (colour 0) body. Uses a comprehension, no game geometry."""
    if not grid:
        return grid
    width = len(grid[0])
    return tuple((bg,) * width if r == 0 else row for r, row in enumerate(grid))


class Adapter(GameAdapter):
    """Rigid connector-marker alignment composed from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        # Wasting more than the level's step budget triggers the engine's
        # own lose(); restarting keeps retrying within the action budget
        # (mirrors every other script25 adapter's convention).
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1

        self._cell_px = 0
        # Measured (dr_sign, dc_sign) per move action, like m0r0's dir_map.
        self._dir: dict[int, Cell] = {}
        # Target-marker centroids (px), measured ONCE per level while the
        # scene is still cleanly split (no body overlap) — targets never
        # move, so this stays valid all level even after the active body
        # slides on top of them.
        self._targets: list[Cell] = []
        self._targets_locked = False
        # Latched once the active sprite's marker shape matches the target's:
        # from then on the adapter only translates (no more rotation), so a
        # marker momentarily reclassified while approaching can't trigger a
        # spurious re-rotation.
        self._oriented = False
        # My markers as (dr, dc) offsets from the active-body centroid,
        # captured at orientation — the body stays visible while it occludes
        # the targets on approach, so this reconstructs my markers reliably.
        self._marker_offsets: list[Cell] | None = None
        # Chirality attempt: the win pairs markers by a hidden colour the
        # frame can't show, so a full geometric coincidence may not win. Each
        # retry RESETs the level and pre-rotates 2 extra quarter-turns (a
        # 180-degree endpoint swap) before re-solving. Attempt 0 and 1 (0 and
        # 2 pre-rotations) cover both chiralities of a marker line.
        self._pre_rot_remaining = 0
        self._attempt = 0
        self._max_attempts = 1

        self._pending_action: int | None = None
        self._pending_active_centroid: Cell | None = None
        self._prev_grid: tuple[tuple[int, ...], ...] | None = None
        # A level-up shows one STALE transition frame (the previous level's
        # final render, before the engine's one-step next_level delay draws
        # the new board): measured on L1->L2, the first frame still has the
        # old background and NO colour-8 stubs, then the real board (4 sprites,
        # 12 stubs) appears after one action. Locking targets off that stale
        # frame corrupts the whole level, so we idle one benign action until
        # colour-8 stubs actually appear.
        self._awaiting_render = False

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state == "GAME_OVER":
            self._on_restart()
            return reset_action()
        if state == "NOT_PLAYED" or not has_frame(latest_frame):
            self._pending_action = None
            self._prev_grid = None
            self._levels_seen = -1
            return reset_action()

        bg = most_common_color(canonical_layer(latest_frame))
        grid = _mask_hud(canonical_layer(latest_frame), bg)
        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._on_level_up(levels)

        self._step += 1
        regions = find_regions(grid, background=bg)

        simple_ids, action6_ok = available_action_ids(latest_frame)
        move_ids = [a for a in simple_ids if a in (1, 2, 3, 4)]
        # Skip the stale post-level-up transition frame: idle a benign action
        # (NOT tracked, so it never pollutes dir/centroid measurement) until
        # the real board's colour-8 stubs render.
        if self._awaiting_render:
            if any(reg["color"] == _MARKER_COLOR for reg in regions):
                self._awaiting_render = False
            else:
                self._pending_action = None
                self._pending_active_centroid = None
                self._prev_grid = grid
                return simple_action(move_ids[0]) if move_ids else reset_action()

        self._observe_result(regions)
        action = self._decide(regions, simple_ids, action6_ok)
        self._prev_grid = grid
        return action

    # ── level / restart bookkeeping ─────────────────────────────────────

    def _on_level_up(self, levels: int) -> None:
        self._levels_seen = levels
        self._cell_px = 0
        self._dir = {}
        self._targets = []
        self._targets_locked = False
        self._oriented = False
        self._marker_offsets = None
        self._pre_rot_remaining = 0
        self._attempt = 0
        self._pending_action = None
        self._pending_active_centroid = None
        self._prev_grid = None
        # Level 0 renders immediately (NOT_PLAYED -> board), but a mid-game
        # level-up shows one stale transition frame first; idle past it.
        self._awaiting_render = levels > 0

    def _on_restart(self) -> None:
        # Keep the measured control facts (dir signs, cell size) — the marker
        # layout didn't change, only the attempt did — but drop the in-flight
        # orientation and re-lock targets fresh from the clean restarted frame.
        self._targets = []
        self._targets_locked = False
        self._oriented = False
        self._pending_action = None
        self._pending_active_centroid = None
        self._prev_grid = None

    # ── measurement: what did the pending move do to the active body? ────

    def _observe_result(self, regions: list[Region]) -> None:
        action = self._pending_action
        before_centroid = self._pending_active_centroid
        self._pending_action = None
        self._pending_active_centroid = None
        if action is None or action not in (1, 2, 3, 4) or before_centroid is None:
            return
        active = self._active_centroid(regions)
        if active is None:
            return
        dr = active[0] - before_centroid[0]
        dc = active[1] - before_centroid[1]
        if dr == 0 and dc == 0:
            return
        self._dir[action] = (_sign(dr), _sign(dc))
        if self._cell_px == 0:
            self._cell_px = max(abs(dr), abs(dc))

    # ── perception helpers (roles declared here; segmentation via kernel) ─

    def _active_regions(self, regions: list[Region]) -> list[Region]:
        return [reg for reg in regions if reg["color"] == _ACTIVE_COLOR]

    def _active_centroid(self, regions: list[Region]) -> Cell | None:
        active = self._active_regions(regions)
        if not active:
            return None
        cells = [_centroid_px(reg) for reg in active]
        n = len(cells)
        return (round(sum(r for r, _c in cells) / n), round(sum(c for _r, c in cells) / n))

    def _cell(self) -> int:
        return self._cell_px if self._cell_px > 0 else 3

    def _markers(self, regions: list[Region]) -> list[Cell]:
        return [_centroid_px(reg) for reg in regions if reg["color"] == _MARKER_COLOR]

    def _lock_targets(self, regions: list[Region]) -> None:
        """Split visible stubs into MINE (near the active body) vs the rest,
        then lock the active sprite's PARTNER stubs as the target: the other
        sprite whose stub COUNT matches the active sprite's (a level can hold
        several sprite pairs — L1 is one 2-stub pair, L2 is two 2-stub + two
        4-stub sprites). Matching only the partner's stubs, not every other
        stub, is what lets the same rotate+translate coincidence loop solve
        one pair at a time (kernels.assign_pairs-style count/shape pairing)."""
        active = self._active_regions(regions)
        markers = self._markers(regions)
        if not markers or not active:
            return
        margin = _ATTACH_CELLS * self._cell()
        mine = [m for m in markers if self._min_body_dist(m, active) <= margin]
        others = [m for m in markers if self._min_body_dist(m, active) > margin]
        partner = self._partner_group(mine, others, regions) if mine else None
        self._targets = partner if partner else others
        self._targets_locked = True

    def _partner_group(
        self, mine: list[Cell], others: list[Cell], regions: list[Region]
    ) -> list[Cell] | None:
        """The subset of ``others`` that is RIGIDLY CONGRUENT to the active
        sprite's own stubs — the k target stubs whose pairwise-distance
        multiset matches ``mine``'s (rotation/reflection invariant), so the
        active sprite can rotate+translate to coincide its stubs onto them.
        This is the geometric core of kernels.assign_pairs pairing: the
        partner is defined by matching STUB GEOMETRY, not sprite identity or
        stub count alone (measured on L2: the two 2-stub sprites are NOT
        congruent — a diagonal pair vs a horizontal pair — so count matching
        is wrong; the active's diagonal pair matches a diagonal sub-pair of a
        4-stub sprite instead). None when no congruent subset exists."""
        k = len(mine)
        if k < 2 or len(others) < k:
            return None
        mine_sig = self._dist_sig(mine)
        active = self._active_regions(regions)
        candidates: list[list[Cell]] = []
        for sub in combinations(sorted(others), k):
            if self._sig_matches(self._dist_sig(list(sub)), mine_sig):
                candidates.append(list(sub))
        if not candidates:
            return None
        if len(candidates) > 1 and active:
            candidates.sort(key=lambda g: self._min_body_dist(g[0], active))
        return candidates[0]

    def _dist_sig(self, pts: list[Cell]) -> tuple[int, ...]:
        return tuple(
            sorted(
                round(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)
                for i, a in enumerate(pts)
                for b in pts[i + 1 :]
            )
        )

    def _sig_matches(self, a: tuple[int, ...], b: tuple[int, ...]) -> bool:
        """Two distance signatures match within a 1px per-entry tolerance
        (integer-rounded centroids drift up to ~1px)."""
        return len(a) == len(b) and all(abs(x - y) <= 1 for x, y in zip(a, b))

    def _bbox_dist(self, point: Cell, region: Region) -> int:
        r0, c0, r1, c1 = region["bbox"]
        dr = 0 if r0 <= point[0] <= r1 else min(abs(point[0] - r0), abs(point[0] - r1))
        dc = 0 if c0 <= point[1] <= c1 else min(abs(point[1] - c0), abs(point[1] - c1))
        return dr + dc

    def _min_body_dist(self, marker: Cell, active: list[Region]) -> float:
        """Manhattan distance from ``marker`` to the NEAREST active-body bbox
        (0 when inside it). Markers hang one cell off a sprite's edge, so the
        active sprite's own markers score ~1 cell while a distinct sprite's
        markers score many — the bbox edge, not the body centroid, is what
        makes that separation clean for a large hollow body."""
        return min(self._bbox_dist(marker, reg) for reg in active)

    def _split_markers(self, regions: list[Region]) -> tuple[list[Cell], list[Cell]]:
        """(mine, remaining_targets) in pixels. Mine = visible stubs NOT at a
        locked target position; remaining_targets = locked targets that still
        show an unsatisfied stub (a satisfied one has recoloured to 3 and so
        no longer appears among the colour-8 markers)."""
        markers = self._markers(regions)
        # MINE = only the ACTIVE sprite's own stubs (near its body) — NOT every
        # stub far from the partner targets, which on a multi-sprite board
        # would wrongly pull in the OTHER pairs' stubs and make the shape match
        # impossible. Body-proximity is the same signal ``_lock_targets`` uses.
        active = self._active_regions(regions)
        margin = _ATTACH_CELLS * self._cell()
        mine = [m for m in markers if active and self._min_body_dist(m, active) <= margin]
        # Half a cell: a target's OWN still-unsatisfied stub sits essentially
        # on it (so it registers as remaining), and an active-sprite marker
        # only leaves ``mine`` once it has genuinely coincided.
        tol = max(1, self._cell() // 2)
        remaining = [t for t in self._targets if self._nearest(t, markers) <= tol]
        return mine, remaining

    def _nearest(self, point: Cell, pool: list[Cell]) -> float:
        if not pool:
            return float("inf")
        return min(abs(point[0] - p[0]) + abs(point[1] - p[1]) for p in pool)

    # ── planning ─────────────────────────────────────────────────────────

    def _decide(self, regions: list[Region], simple_ids: list[int], action6_ok: bool) -> GameAction:
        move_ids = [a for a in simple_ids if a in (1, 2, 3, 4)]
        can_rotate = 5 in simple_ids

        active = self._active_regions(regions)
        if not active:
            return self._select_a_sprite(regions, action6_ok, move_ids)

        if not self._targets_locked:
            self._lock_targets(regions)

        # Chirality offset: emit the pre-rotations queued by the previous
        # attempt's wrong-chirality RESET before doing anything else.
        if self._pre_rot_remaining > 0 and can_rotate:
            self._pre_rot_remaining -= 1
            return simple_action(5)

        mine, remaining = self._split_markers(regions)
        eight_count = sum(1 for reg in regions if reg["color"] == _MARKER_COLOR)
        three_present = any(reg["color"] == _SATISFIED_COLOR for reg in regions)

        # Full geometric coincidence with no WIN => the hidden 8<->13 pairing
        # is swapped. RESET and retry from the 180-degree-opposite chirality.
        if self._oriented and eight_count == 0 and three_present:
            return self._retry_other_chirality(move_ids)

        cell = self._cell()
        if not self._oriented:
            if not mine:
                if remaining:
                    return self._select_a_sprite(regions, action6_ok, move_ids)
                return self._probe_move(active, move_ids)
            if not remaining:
                return self._probe_move(active, move_ids)
            if self._rel_shape(mine, cell) == self._rel_shape(remaining, cell):
                self._latch_orientation(mine, active)
            elif can_rotate:
                return simple_action(5)
            else:
                return self._probe_move(active, move_ids)

        # Post-orientation: my markers are tracked as fixed offsets from the
        # ALWAYS-VISIBLE active body (colour 0), not read live — the body
        # occludes the target stubs underneath it as it slides across, so a
        # live re-read loses the goal exactly on approach. Targets are the
        # LOCKED positions minus any already satisfied (a colour-3 sits on a
        # satisfied one).
        my_markers = self._body_markers(regions)
        unsatisfied = self._unsatisfied_targets(regions, cell)
        if not unsatisfied:
            # This pair's stubs have all coincided. If any sprite still has
            # unsatisfied (colour-8) stubs, this is a multi-pair level: select
            # the next unsolved sprite and re-lock its own partner.
            if eight_count > 0:
                self._advance_to_next_pair()
                return self._select_a_sprite(regions, action6_ok, move_ids)
            return self._probe_move(active, move_ids)
        if not my_markers:
            return self._probe_move(active, move_ids)
        return self._translate_step(my_markers, unsatisfied, cell, move_ids, active)

    def _advance_to_next_pair(self) -> None:
        """Reset only the per-pair state so the next-selected sprite re-locks
        its own partner and re-orients — the measured control facts (dir signs,
        cell pitch) are level-wide and kept."""
        self._targets = []
        self._targets_locked = False
        self._oriented = False
        self._marker_offsets = None
        self._pre_rot_remaining = 0
        self._attempt = 0

    def _latch_orientation(self, mine: list[Cell], active: list[Region]) -> None:
        """Record my markers as fixed offsets from the active-body centroid at
        the moment the shape first matches the target — so they can be
        reconstructed from the visible body even after the body occludes the
        target region during the translate."""
        self._oriented = True
        bc = self._centroid_of(active)
        if bc is None:
            return
        self._marker_offsets = sorted((r - bc[0], c - bc[1]) for r, c in mine)

    def _body_markers(self, regions: list[Region]) -> list[Cell]:
        bc = self._active_centroid(regions)
        if bc is None or self._marker_offsets is None:
            return []
        return [(bc[0] + dr, bc[1] + dc) for dr, dc in self._marker_offsets]

    def _unsatisfied_targets(self, regions: list[Region], cell: int) -> list[Cell]:
        threes = [_centroid_px(reg) for reg in regions if reg["color"] == _SATISFIED_COLOR]
        return [t for t in self._targets if self._nearest(t, threes) > cell]

    def _translate_step(
        self,
        mine: list[Cell],
        remaining: list[Cell],
        cell: int,
        move_ids: list[int],
        active: list[Region],
    ) -> GameAction:
        """The single measured unit move that most reduces the total distance
        from my markers to their (shape-matched, sorted-paired) targets.

        Hill-climbing on the ACTUAL pixel distance — not a rounded
        centroid-over-cell residual — avoids the sub-cell phase drift that
        makes a division-based step land a cell short and then oscillate. Each
        move is exactly one cell (measured), and the targets sit an integer
        number of cells away (the arrangement is solvable), so the distance
        descends monotonically to 0, i.e. exact overlap."""
        if not self._dirs_ready(move_ids):
            return self._probe_move(active, move_ids)
        ms = sorted(mine)
        ts = sorted(remaining)
        if len(ms) != len(ts):
            return self._probe_move(active, move_ids)
        current = self._pair_cost(ms, ts, (0, 0))
        best_action: int | None = None
        best_cost = current
        for action in move_ids:
            sign = self._dir.get(action)
            if sign is None:
                continue
            delta = (sign[0] * self._cell_px, sign[1] * self._cell_px)
            cost = self._pair_cost(ms, ts, delta)
            if cost < best_cost:
                best_cost = cost
                best_action = action
        if best_action is None:
            # Already at the closest reachable configuration — idle-probe and
            # let the engine's own WIN / coincidence signal drive the next
            # decision.
            return self._probe_move(active, move_ids)
        return self._issue_move(best_action, active)

    def _pair_cost(self, ms: list[Cell], ts: list[Cell], delta: Cell) -> int:
        return sum(
            abs(m[0] + delta[0] - t[0]) + abs(m[1] + delta[1] - t[1]) for m, t in zip(ms, ts)
        )

    def _retry_other_chirality(self, move_ids: list[int]) -> GameAction:
        """A coincidence recoloured every stub to 3 but the level did not
        win: the hidden marker colours are paired the other way. RESET the
        level (restores the clean initial arrangement) and, on the next
        attempt, pre-rotate two extra quarter-turns so the marker line's
        endpoints are swapped. Measured facts (dir signs, cell size) are
        kept; only the spatial attempt restarts."""
        self._attempt += 1
        self._oriented = False
        self._marker_offsets = None
        self._targets = []
        self._targets_locked = False
        self._pending_action = None
        self._pending_active_centroid = None
        if self._attempt > self._max_attempts:
            # Both chiralities exhausted without a win — nothing more this
            # adapter can do here; a harmless move avoids stalling.
            return self._probe_move(self._active_regions([]), move_ids)
        self._pre_rot_remaining = 2 * self._attempt
        return reset_action()

    def _dirs_ready(self, move_ids: list[int]) -> bool:
        """True once every available move's direction sign and the cell pitch
        are measured — required before an EXACT translation step (an
        unmeasured move can't be turned into a reliable direction)."""
        return self._cell_px > 0 and all(a in self._dir for a in move_ids)

    def _rel_shape(self, points: list[Cell], cell: int) -> frozenset[Cell]:
        """Marker centroids as a set of integer CELL offsets from their own
        top-left — a translation-invariant shape fingerprint. Equal shapes
        for ``mine`` and ``target`` mean a pure translation can register them
        (the rotation, if any, is already applied on the board)."""
        if not points:
            return frozenset()
        cells = sorted((round(r / cell), round(c / cell)) for r, c in points)
        r0 = cells[0][0]
        c0 = min(c for _r, c in cells)
        return frozenset((r - r0, c - c0) for r, c in cells)

    def _move_for(self, want: Cell, move_ids: list[int]) -> int | None:
        for action, sign in self._dir.items():
            if action in move_ids and sign == want:
                return action
        return None

    def _issue_move(self, action: int, active: list[Region]) -> GameAction:
        self._pending_action = action
        self._pending_active_centroid = self._centroid_of(active)
        return simple_action(action)

    def _probe_move(self, active: list[Region], move_ids: list[int]) -> GameAction:
        """Issue an as-yet-unmeasured move so its direction sign gets learned
        (or, if all are known, the first available move) — harmless progress
        that keeps the dir_map filling in."""
        if not move_ids:
            return reset_action()
        untried = [a for a in move_ids if a not in self._dir]
        action = untried[0] if untried else move_ids[0]
        return self._issue_move(action, active)

    def _centroid_of(self, active: list[Region]) -> Cell | None:
        if not active:
            return None
        cells = [_centroid_px(reg) for reg in active]
        n = len(cells)
        return (round(sum(r for r, _c in cells) / n), round(sum(c for _r, c in cells) / n))

    def _select_a_sprite(
        self, regions: list[Region], action6_ok: bool, move_ids: list[int]
    ) -> GameAction:
        """Click a visible sprite that still carries unsatisfied markers so it
        becomes active. Prefers a native-colour sprite adjacent to an
        unsatisfied colour-8 stub; falls back to a probe move."""
        if not action6_ok:
            return self._probe_move(self._active_regions(regions), move_ids)
        markers = self._markers(regions)
        bodies = [
            reg
            for reg in regions
            if reg["color"] not in (_ACTIVE_COLOR, _MARKER_COLOR, _SATISFIED_COLOR)
        ]
        target_body = self._body_near_markers(bodies, markers)
        if target_body is None:
            return self._probe_move(self._active_regions(regions), move_ids)
        r, c = self._solid_click_cell(target_body, regions)
        return click_action(x=c, y=r)

    def _solid_click_cell(self, target: Region, regions: list[Region]) -> Cell:
        """A SOLID pixel of ``target`` to click — its centroid can fall in a
        hollow (a box-shaped sprite's hole is transparent, so a centroid click
        selects nothing and the active piece never switches). Prefer a cell
        outside the current active body's bbox too, so the click isn't
        swallowed by an overlapping just-moved sprite on top of it."""
        cells = sorted(target["cells"])  # type: ignore[arg-type]
        active = self._active_regions(regions)
        if active:
            r0, c0, r1, c1 = active[0]["bbox"]
            outside = [(r, c) for r, c in cells if not (r0 <= r <= r1 and c0 <= c <= c1)]
            if outside:
                cells = outside
        return cells[len(cells) // 2]

    def _body_near_markers(self, bodies: list[Region], markers: list[Cell]) -> Region | None:
        if not bodies or not markers:
            return None
        scored = sorted(bodies, key=lambda reg: self._nearest(_centroid_px(reg), markers))
        return scored[0]
