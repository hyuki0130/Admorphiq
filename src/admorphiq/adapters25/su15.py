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
# Enemy chase is deterministic (source ``sgmsqapcxe``): every enemy steps
# 1-2 px/axis toward the NEAREST non-vacuumed fruit each vacuum sub-step, ~4
# sub-steps per click, so it converges up to this many px toward its target
# per click. Used to PREDICT where the swarm will be next click when choosing
# a merge zone.
_ENEMY_REACH = 8.0
# A merge midpoint at least this far from every predicted enemy position is
# treated as safe for the ~4-step merge; below it, lure the swarm first. Set
# above _ENEMY_REACH so the pair is out of one click's convergence.
_ENEMY_CLEARANCE = 12.0
# A dominant frame change smaller than this (px, on the diff bbox) counts as
# "nothing usefully moved" for lead escalation.
_MIN_USEFUL_DIFF = 1.5


# value -> sprite side length (laalrfemee sizes). A fruit-model position is the
# sprite TOP-LEFT in (x=col, y=row); a value-0 fruit is a single cell.
_SIZE = (1, 2, 3, 4, 5, 7, 8, 9, 10)
_SUBSTEPS = 4  # gdamdvokm (bjetwxoaq) — vacuum sub-steps per click
_PULL_PX = 4  # ikskfqldi (stqbquzms) — fruit pull px/axis per sub-step
# Enemy sprite (source ``sprites["enemy"]``): a 4-row × 5-col star. Its centre
# (``qmecbepbyz``) is top-left + (width//2, height//2) = (x+2, y+2).
_ENEMY_W = 5
_ENEMY_H = 4
# A class-1 enemy (source tag ``gulrbtyssc``, the ONLY enemy kind on L3) steps
# this many px/axis toward the nearest fruit each vacuum sub-step (``wwvazosegn``:
# ``lvkjczbkpm = 1``; classes 2/3 step 2, absent on L3).
_ENEMY_STEP = 1
# A vacuumed class-1 enemy is pulled along the fixed enemy-centre->click unit ray
# at ``_PULL_PX * 0.85`` px/sub-step (source ``cmfhziahuk``), NOT clamped at the
# click (unlike fruits). Over _SUBSTEPS that is ~13.6 px toward the click.
_ENEMY_VAC_FRAC = 0.85
# Play-area clamp bounds (source ``gnexwlqinp`` / ``ncfmodluov`` + grid 64).
_CLAMP_TOP = 10
_CLAMP_BOTTOM = 63
_GRID_WH = 64


def _euclid_in_radius(cx: int, cy: int, x: int, y: int, w: int, h: int, radius: int = _VACUUM_RADIUS) -> bool:
    """Engine ``yrufkxnmou``: is ``(cx, cy)`` within ``radius`` (EUCLIDEAN) of the
    sprite's bbox? The click point is clamped to ``[x, x+w-1] × [y, y+h-1]`` and
    the squared distance to that nearest bbox cell compared to ``radius²``."""
    px = x if cx < x else (x + w - 1 if cx > x + w - 1 else cx)
    py = y if cy < y else (y + h - 1 if cy > y + h - 1 else cy)
    dx = cx - px
    dy = cy - py
    return dx * dx + dy * dy <= radius * radius


def _clamp_pos(x: float, y: float, w: int, h: int) -> tuple[int, int]:
    """Engine play-area clamp: ``x`` into ``[0, 64-w]``; ``y`` into
    ``[10, min(63, 64-h)]``."""
    xi = int(round(x))
    yi = int(round(y))
    if xi < 0:
        xi = 0
    if xi > _GRID_WH - w:
        xi = _GRID_WH - w
    if yi < _CLAMP_TOP:
        yi = _CLAMP_TOP
    if yi > _CLAMP_BOTTOM:
        yi = _CLAMP_BOTTOM
    if yi > _GRID_WH - h:
        yi = _GRID_WH - h
    return xi, yi


def _bbox_overlap(ax: int, ay: int, aw: int, ah: int, bx: int, by: int, bw: int, bh: int) -> bool:
    """Engine ``rukauvoumh`` half-open-bbox overlap test."""
    if ax + aw <= bx or bx + bw <= ax:
        return False
    if ay + ah <= by or by + bh <= ay:
        return False
    return True


def _sim_click_full(
    fruits: list[list[int]], enemies: list[list[int]], cx: int, cy: int
) -> tuple[list[list[int]], list[list[int]], bool]:
    """FAITHFUL one-click sim of fruits AND enemies (source ``ctohhyezgx`` →
    ``lyaaynsyhw`` ×``_SUBSTEPS`` → ``ivbqcpwjdw`` merge), interleaving the
    per-sub-step enemy chase (``wwvazosegn``) exactly as the engine does.

    ``fruits`` are ``[x=col, y=row, value]`` sprite top-lefts; ``enemies`` are
    ``[x=col, y=row]`` top-lefts of the 5×4 star. Returns
    ``(fruits', enemies', contact)`` where ``contact`` is True iff a
    NON-vacuumed enemy's bbox overlapped a fruit's bbox during any sub-step —
    i.e. a downgrade (``sbfzybbszx``) would have fired. The margin search treats
    ``contact=True`` as an unsafe plan and never relies on the post-contact
    knockback dynamics (which this sim deliberately does not model, since a
    margin-safe plan never triggers them). The fruit half is byte-identical to
    :func:`_sim_click`; with ``enemies=[]`` this returns exactly ``_sim_click``'s
    fruit result and ``contact=False``."""
    fs = [f[:] for f in fruits]
    es = [e[:] for e in enemies]

    # ── ctohhyezgx: select vacuumed fruits and enemies by the engine's EXACT
    # euclidean bbox test (yrufkxnmou). (The older _sim_click used a looser
    # Chebyshev test — validated only on the win sequence; it OVER-selects
    # diagonal fruits and mis-merges on arbitrary clicks, so the faithful sim
    # uses euclidean.) ──
    sel_fruit = [f for f in fs if _euclid_in_radius(cx, cy, f[0], f[1], _SIZE[f[2]], _SIZE[f[2]])]
    # Vacuumed enemies: fixed unit ray from enemy CENTRE to the click, float
    # top-left accumulator (source itlxknnsz / rzfgsshuk).
    vac_enemy: dict[int, tuple[float, float, float, float]] = {}
    for i, e in enumerate(es):
        if _euclid_in_radius(cx, cy, e[0], e[1], _ENEMY_W, _ENEMY_H):
            ecx = e[0] + _ENEMY_W // 2
            ecy = e[1] + _ENEMY_H // 2
            vx = float(cx - ecx)
            vy = float(cy - ecy)
            d = (vx * vx + vy * vy) ** 0.5
            ux, uy = (vx / d, vy / d) if d > 0.0 else (0.0, 0.0)
            vac_enemy[i] = (ux, uy, float(e[0]), float(e[1]))

    contact = False
    for _ in range(_SUBSTEPS):
        # 1) Move vacuumed fruits toward the click (clamped per axis).
        for f in sel_fruit:
            dx, dy = cx - f[0], cy - f[1]
            if dx > 0:
                f[0] += min(_PULL_PX, dx)
            elif dx < 0:
                f[0] += max(-_PULL_PX, dx)
            if dy > 0:
                f[1] += min(_PULL_PX, dy)
            elif dy < 0:
                f[1] += max(-_PULL_PX, dy)
        # 2) Move vacuumed enemies along their fixed ray (float accumulate).
        step = _PULL_PX * _ENEMY_VAC_FRAC
        for i, (ux, uy, fx, fy) in list(vac_enemy.items()):
            fx += ux * step
            fy += uy * step
            xi, yi = _clamp_pos(fx, fy, _ENEMY_W, _ENEMY_H)
            es[i][0], es[i][1] = xi, yi
            vac_enemy[i] = (ux, uy, float(xi), float(yi))
        # 3) wwvazosegn: chase for every NON-vacuumed enemy, 1px/axis toward the
        #    nearest fruit's centre (recomputed each sub-step).
        for i, e in enumerate(es):
            if i in vac_enemy:
                continue
            if not fs:
                continue
            ecx = e[0] + _ENEMY_W // 2
            ecy = e[1] + _ENEMY_H // 2
            best = min(
                fs, key=lambda f: (f[0] + _SIZE[f[2]] // 2 - ecx) ** 2 + (f[1] + _SIZE[f[2]] // 2 - ecy) ** 2
            )
            tx = best[0] + _SIZE[best[2]] // 2
            ty = best[1] + _SIZE[best[2]] // 2
            sx = _ENEMY_STEP if tx > ecx else (-_ENEMY_STEP if tx < ecx else 0)
            sy = _ENEMY_STEP if ty > ecy else (-_ENEMY_STEP if ty < ecy else 0)
            e[0], e[1] = _clamp_pos(e[0] + sx, e[1] + sy, _ENEMY_W, _ENEMY_H)
        # 4) Collision: a NON-vacuumed enemy overlapping a fruit downgrades it
        #    (sbfzybbszx). Margin-safe plans avoid this — flag and keep going.
        for i, e in enumerate(es):
            if i in vac_enemy:
                continue
            for f in fs:
                if _bbox_overlap(e[0], e[1], _ENEMY_W, _ENEMY_H, f[0], f[1], _SIZE[f[2]], _SIZE[f[2]]):
                    contact = True
                    break
        # Two same-tag enemies that overlap MERGE UP a tier (source fzolkosujg →
        # vwucsjocjy: a faster class-2/3 enemy spawns). That is not modelled here,
        # so a plan that collides two enemies is flagged unsafe (reject) — it must
        # keep them apart, which a margin-safe lure does anyway. No-op for the
        # single-enemy L3 (needs ≥2 enemies, e.g. L4).
        for i in range(len(es)):
            for j in range(i + 1, len(es)):
                if _bbox_overlap(es[i][0], es[i][1], _ENEMY_W, _ENEMY_H, es[j][0], es[j][1], _ENEMY_W, _ENEMY_H):
                    contact = True

    # ── ivbqcpwjdw: union-find same-value OVERLAP merge (identical to
    # _sim_click). ──
    def touch(a: list[int], b: list[int]) -> bool:
        sa, sb = _SIZE[a[2]], _SIZE[b[2]]
        return not (a[0] + sa <= b[0] or b[0] + sb <= a[0] or a[1] + sa <= b[1] or b[1] + sb <= a[1])

    n = len(fs)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if fs[i][2] == fs[j][2] and touch(fs[i], fs[j]):
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out: list[list[int]] = []
    for idxs in groups.values():
        if len(idxs) >= 2:
            v = fs[idxs[0]][2] + 1
            nsz = _SIZE[v] if v < len(_SIZE) else _SIZE[-1]
            gx = round(sum(fs[k][0] for k in idxs) / len(idxs))
            gy = round(sum(fs[k][1] for k in idxs) / len(idxs))
            out.append([gx - (nsz - 1) // 2, gy - (nsz - 1) // 2, v])
        else:
            out.append(fs[idxs[0]])
    return out, es, contact


# Cooldown (sub-steps) an enemy gets after eating a fruit — source
# ``tfaferyux + djoqfdlzu + 1``. During it the enemy's chase is frozen.
_ENEMY_COOLDOWN = 9


def _sim_click_sacrifice(
    fruits: list[list[int]], enemies: list[list[int]], cx: int, cy: int
) -> tuple[list[list[int]], list[list[int]], bool]:
    """Variant of :func:`_sim_click_full` for the spare-sacrifice plan (multi-
    enemy levels whose target needs only a SUBSET of the fruits, e.g. L4's four
    value-1s): a value-0 enemy contact DESTROYS that spare (source ``rzdkhogqmi``
    branch — removed + the enemy frozen ``_ENEMY_COOLDOWN`` sub-steps), while a
    value≥1 contact sets ``bad`` (a cascade-fruit downgrade the plan must avoid).
    ``enemies`` are ``[x, y, cooldown]`` sprite top-lefts. Returns
    ``(fruits', enemies', bad)``."""
    fs = [f[:] for f in fruits]
    es = [e[:] for e in enemies]
    sel_fruit = [f for f in fs if _euclid_in_radius(cx, cy, f[0], f[1], _SIZE[f[2]], _SIZE[f[2]])]
    vac: dict[int, tuple[float, float, float, float]] = {}
    for i, e in enumerate(es):
        if _euclid_in_radius(cx, cy, e[0], e[1], _ENEMY_W, _ENEMY_H):
            ecx, ecy = e[0] + _ENEMY_W // 2, e[1] + _ENEMY_H // 2
            vx, vy = float(cx - ecx), float(cy - ecy)
            d = (vx * vx + vy * vy) ** 0.5
            ux, uy = (vx / d, vy / d) if d > 0 else (0.0, 0.0)
            vac[i] = (ux, uy, float(e[0]), float(e[1]))
    bad = False
    dead: set[int] = set()
    for _ in range(_SUBSTEPS):
        for f in sel_fruit:
            dx, dy = cx - f[0], cy - f[1]
            if dx > 0:
                f[0] += min(_PULL_PX, dx)
            elif dx < 0:
                f[0] += max(-_PULL_PX, dx)
            if dy > 0:
                f[1] += min(_PULL_PX, dy)
            elif dy < 0:
                f[1] += max(-_PULL_PX, dy)
        step = _PULL_PX * _ENEMY_VAC_FRAC
        for i, (ux, uy, fx, fy) in list(vac.items()):
            fx += ux * step
            fy += uy * step
            xi, yi = _clamp_pos(fx, fy, _ENEMY_W, _ENEMY_H)
            es[i][0], es[i][1] = xi, yi
            vac[i] = (ux, uy, float(xi), float(yi))
        alive = [k for k in range(len(fs)) if k not in dead]
        for i, e in enumerate(es):
            if i in vac or e[2] > 0 or not alive:
                continue
            ecx, ecy = e[0] + _ENEMY_W // 2, e[1] + _ENEMY_H // 2
            best = min(
                alive,
                key=lambda k: (fs[k][0] + _SIZE[fs[k][2]] // 2 - ecx) ** 2
                + (fs[k][1] + _SIZE[fs[k][2]] // 2 - ecy) ** 2,
            )
            tx = fs[best][0] + _SIZE[fs[best][2]] // 2
            ty = fs[best][1] + _SIZE[fs[best][2]] // 2
            sx = _ENEMY_STEP if tx > ecx else (-_ENEMY_STEP if tx < ecx else 0)
            sy = _ENEMY_STEP if ty > ecy else (-_ENEMY_STEP if ty < ecy else 0)
            e[0], e[1] = _clamp_pos(e[0] + sx, e[1] + sy, _ENEMY_W, _ENEMY_H)
        for i, e in enumerate(es):
            if i in vac:
                continue
            for k in range(len(fs)):
                if k in dead:
                    continue
                if _bbox_overlap(e[0], e[1], _ENEMY_W, _ENEMY_H, fs[k][0], fs[k][1], _SIZE[fs[k][2]], _SIZE[fs[k][2]]):
                    if fs[k][2] == 0:
                        dead.add(k)
                        e[2] = _ENEMY_COOLDOWN
                    else:
                        bad = True
        for e in es:
            if e[2] > 0:
                e[2] -= 1
    fs = [f for k, f in enumerate(fs) if k not in dead]

    def touch(a: list[int], b: list[int]) -> bool:
        sa, sb = _SIZE[a[2]], _SIZE[b[2]]
        return not (a[0] + sa <= b[0] or b[0] + sb <= a[0] or a[1] + sa <= b[1] or b[1] + sb <= a[1])

    n = len(fs)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if fs[i][2] == fs[j][2] and touch(fs[i], fs[j]):
                parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out: list[list[int]] = []
    for idxs in groups.values():
        if len(idxs) >= 2:
            v = fs[idxs[0]][2] + 1
            nsz = _SIZE[v] if v < len(_SIZE) else _SIZE[-1]
            gx = round(sum(fs[k][0] for k in idxs) / len(idxs))
            gy = round(sum(fs[k][1] for k in idxs) / len(idxs))
            out.append([gx - (nsz - 1) // 2, gy - (nsz - 1) // 2, v])
        else:
            out.append(fs[idxs[0]])
    return out, es, bad


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
    return goals, fruits, _fuse_enemies(enemies)


# A star ENEMY renders (at gap=0) as several tiny disconnected fragments within
# its own small sprite bbox. Fragments of ONE enemy sit within this many px of
# each other; two DISTINCT enemies are farther apart. Single-linkage chaining
# below this distance fuses one star's fragments into one entity — WITHOUT this,
# each fragment was counted as a separate enemy (a 1-enemy L3 star read as ~6
# phantom enemies, mis-driving the chase prediction and lure — the measured
# root cause of L3=0).
_ENEMY_FUSE_DIST = 7.0


def _fuse_enemies(fragments: list[Region]) -> list[Region]:
    """Single-linkage cluster enemy fragments into one region per real enemy.

    Each output region carries a size-weighted centroid, unioned bbox, and
    summed size so the downstream chase-prediction / lure / danger logic sees
    ONE entity per star, not its fragments."""
    if len(fragments) <= 1:
        return fragments
    n = len(fragments)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if _dist(_centroid(fragments[i]), _centroid(fragments[j])) <= _ENEMY_FUSE_DIST:
                parent[find(i)] = find(j)
    groups: dict[int, list[Region]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(fragments[i])
    fused: list[Region] = []
    for members in groups.values():
        total = sum(m["size"] for m in members) or 1
        cr = sum(_centroid(m)[0] * m["size"] for m in members) / total
        cc = sum(_centroid(m)[1] * m["size"] for m in members) / total
        r0 = min(m["bbox"][0] for m in members)
        c0 = min(m["bbox"][1] for m in members)
        r1 = max(m["bbox"][2] for m in members)
        c1 = max(m["bbox"][3] for m in members)
        fused.append({"color": members[0]["color"], "centroid": (cr, cc), "bbox": (r0, c0, r1, c1), "size": total})
    return fused


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

    @classmethod
    def _detect_mechanic(cls, latest_frame: Any) -> bool:
        """A vacuum-merge delivery board: undo-only controls AND both entity kinds present.

        1. **Vacuum controls.** The mechanic is played by clicking a point to pull nearby
           items toward it, with an undo and nothing else — no movement, no confirm. That
           control set (ACTION7 plus clicks) is unique among the 25 public games.
        2. **Fruits AND goals on the board.** `_classify` separates goal disks (non-solid,
           holey — density below 1.0) from solid value-coloured fruit blocks. A delivery
           puzzle needs both; a board with only one of them is not this mechanic, whatever
           its controls look like.
        """
        simple_ids, has_click = available_action_ids(latest_frame)
        if not has_click or sorted(simple_ids) != [7]:
            return False
        goals, fruits, _enemies = _classify(canonical_layer(latest_frame))
        return bool(goals) and bool(fruits)

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
        # Internal fruit model (list of [x=col, y=row, value]) for enemy levels:
        # parsed once from the settled frame, then advanced by _sim_click_full
        # per click (fruits AND enemy in one faithful sim) so the exact-parity
        # cascade + enemy-lure choreography run OPEN-LOOP, immune to the per-step
        # perception noise that sinks a frame-reactive planner. None until the
        # level's opening frame settles; re-seeded from live only on divergence.
        self._model: list[list[int]] | None = None
        # Internal enemy model (list of [x=col, y=row] sprite top-lefts), seeded
        # and advanced alongside _model by _sim_click_full — the enemy is now
        # simulated open-loop, NOT read live each step (the live read + Chebyshev
        # fruit sim was the measured cause of the 3/9 L3 stall).
        self._enemy_model: list[list[int]] | None = None
        self._model_settle = 0
        self._last_click_xy: Cell | None = None
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
            self._model = None
            self._enemy_model = None
            self._model_settle = 0
            self._last_click_xy = None

        self._step += 1
        self._observe_result(grid)

        _simple_ids, action6_ok = available_action_ids(latest_frame)
        if not action6_ok:
            self._prev_grid = grid
            self._pending_click = None
            return reset_action()

        n_layers = len(getattr(latest_frame, "frame", None) or [])
        model_target = self._model_action(grid, n_layers)
        target = model_target if model_target is not None else self._plan(grid)
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

    # Corners (in x=col, y=row) the enemy is lured toward — far from the fruits
    # so vacuuming it there does not also grab a merge fruit.
    _MODEL_CORNERS = ((2, 12), (2, 60), (60, 12), (60, 60), (2, 36), (60, 36), (2, 53), (60, 53))
    # Base lure-danger radius. MEASURED optimum of the enemy-in-sim margin
    # search (`scripts/_su15_enemy_sim.py --search`): with the FAITHFUL
    # fruits+enemy sim, lure_base=20 WINS 9/9 under all ±1px seed perturbations
    # (23-click plan); 15 is a fragile 6/9, 12 contacts, ≥28 over-lures and
    # starves the cascade. The corner set does not affect the outcome — the lure
    # aggression is the sole sensitive knob. (The prior comment claimed "20
    # starves"; that was measured under the Chebyshev _sim_click fruit model,
    # which over-merges — the faithful euclidean _sim_click_full inverts it.)
    _MODEL_LURE_BASE = 20.0

    def _model_action(self, grid: tuple[tuple[int, ...], ...], n_layers: int) -> Cell | None:
        """OPEN-LOOP model-driven cascade for enemy levels (L3+): seed a fruit +
        enemy model ONCE from the settled frame, then advance BOTH with the
        faithful :func:`_sim_click_full` per click and emit the margin-robust
        lure choreography. The enemy is simulated, not read live — the live read
        + Chebyshev fruit sim was the measured 3/9 stall. A live re-parse each
        step corrects the model only on divergence (a downgrade the sim's
        margin-safe plan should never cause). Returns the ``(row, col)`` click,
        or ``None`` to defer to the byte-identical no-enemy :meth:`_plan`
        (L0-L2, or a detection miss)."""
        goals, fruits, enemies = _classify(grid)
        if not enemies:
            return None
        goals = self._prefer_static_goals(goals) or self._anchor_goals()

        if self._model is None or self._enemy_model is None:
            # A multi-layer transient at level entry mis-reads the board; wait a
            # few frames (a click at row 0 is out of play — the engine ignores
            # it — so it is a harmless settle action). Seed both models once the
            # frame settles and a full fruit set is visible.
            if n_layers > 1 and self._model_settle < 4:
                self._model_settle += 1
                return (0, 0)
            if len(fruits) < 2:
                return None
            self._model = [
                [int(round(_centroid(f)[1])), int(round(_centroid(f)[0])), _value(f)] for f in fruits
            ]
            self._enemy_model = [self._enemy_topleft(e) for e in enemies]

        # TWO+ enemies (e.g. L4): the single-lure cascade can't keep both off the
        # merge targets (measured — no fruit-free park exists). Route to the
        # spare-sacrifice plan, which drives the enemies into the value-0 field to
        # eat spares while the value-1 cascade + delivery proceed. Gated on enemy
        # count, so the single-enemy L3 path below stays byte-identical (floor 4/9).
        if len(enemies) >= 2:
            return self._sacrifice_action(goals)

        # PURE OPEN-LOOP after the settle-seed — NO per-click live re-sync. The
        # merge/vacuum animation resolves over several engine sub-steps, so a
        # live re-parse LAGS the sim by ~1 click; a naive mid-cascade reseed
        # reverts a good merge and strands the exact-parity cascade (measured,
        # commit 4a2d044). The sim is faithful (validated: contact-free fruit
        # multiset 0 mismatches / 200 frames, enemy chase ≤4px) and the plan is
        # margin-robust (9/9 under ±1px seed drift), so the sim is trusted end
        # to end — this is exactly what cleared L3 live (22 clicks).
        model = self._model
        enemy_model = self._enemy_model
        if not model or not enemy_model:
            return None

        def to_xy(region: Region) -> tuple[float, float]:
            r, c = _centroid(region)
            return (c, r)

        # Enemy position comes from the SIM model (open-loop), picking the enemy
        # nearest the fruit cascade as the threat the choreography reacts to.
        enemy_xy = min(
            ((e[0] + _ENEMY_W // 2.0, e[1] + _ENEMY_H // 2.0) for e in enemy_model),
            key=lambda e: min((_dist(e, (f[0], f[1])) for f in model), default=0.0),
        )
        goal_xy = to_xy(goals[0]) if goals else (float(_GRID // 2), float(_GRID // 2))

        click_xy = self._model_heuristic(model, enemy_xy, goal_xy)
        if click_xy is None:
            return None
        cx = max(0, min(_GRID - 1, int(round(click_xy[0]))))
        cy = max(_PLAY_TOP, min(_PLAY_BOTTOM, int(round(click_xy[1]))))
        self._model, self._enemy_model, _contact = _sim_click_full(model, enemy_model, cx, cy)
        return (cy, cx)

    @staticmethod
    def _enemy_topleft(region: Region) -> list[int]:
        """Sprite top-left ``[x=col, y=row, cooldown=0]`` of a fused enemy region,
        from its centroid minus the 5×4 star's half-extent — the seed for the
        enemy model. The single-enemy path (:func:`_sim_click_full`) ignores the
        cooldown field; the sacrifice path (:func:`_sim_click_sacrifice`) uses it."""
        cr, cc = _centroid(region)
        return [int(round(cc)) - _ENEMY_W // 2, int(round(cr)) - _ENEMY_H // 2, 0]

    # Spare-sacrifice plan tuning (multi-enemy levels, e.g. L4). MEASURED margin
    # optimum (`scripts/_su15_enemy_sim.py --sacrifice --level 4`): lure 16-28 ×
    # sink 52-60 all WIN 9/9 under ±1px perturbations; 20/56 sits mid-plateau.
    _SACRIFICE_LURE = 20.0
    _SACRIFICE_SINK = 56.0

    def _sacrifice_action(self, goals: list[Region]) -> Cell | None:
        """OPEN-LOOP spare-sacrifice cascade for multi-enemy levels: lure any
        enemy threatening a cascade fruit (value≥1) DOWN into the value-0 field
        (where it eats spares and freezes), merge the value-1s and deliver the
        value-3 — advancing the fruit+enemy model with :func:`_sim_click_sacrifice`
        (value-0 destruction modelled). Live-verified to clear L4."""
        model = self._model
        enemy_model = self._enemy_model
        if not model or not enemy_model:
            return None
        goal_xy = (float(_GRID // 2), float(_GRID // 2))
        if goals:
            gr, gc = _centroid(goals[0])
            goal_xy = (gc, gr)
        click_xy = self._sacrifice_heuristic(model, enemy_model, goal_xy)
        if click_xy is None:
            return None
        cx = max(0, min(_GRID - 1, int(round(click_xy[0]))))
        cy = max(_PLAY_TOP, min(_PLAY_BOTTOM, int(round(click_xy[1]))))
        self._model, self._enemy_model, _bad = _sim_click_sacrifice(model, enemy_model, cx, cy)
        return (cy, cx)

    def _sacrifice_heuristic(
        self, model: list[list[int]], enemies: list[list[int]], goal_xy: tuple[float, float]
    ) -> tuple[float, float] | None:
        """One sacrifice click. Deliver the top fruit once value≥3 (from its
        centre, grab-safe lead); else lure a NON-frozen enemy that threatens a
        cascade (value≥1) fruit DOWN to its side of the value-0 sink; else merge
        the lowest-value pair (cascade first)."""
        r = _VACUUM_RADIUS
        top = max(model, key=lambda f: f[2])
        if top[2] >= 3:
            sz = _SIZE[top[2]]
            cx0, cy0 = top[0] + sz // 2, top[1] + sz // 2
            dx, dy = goal_xy[0] - cx0, goal_xy[1] - cy0
            d = (dx * dx + dy * dy) ** 0.5 or 1.0
            lead = max(1.0, min(d, r - sz / 2.0 - 0.5))
            return (cx0 + dx / d * lead, cy0 + dy / d * lead)
        cascade = [f for f in model if f[2] >= 1]
        threat: list[int] | None = None
        best = 1e9
        for e in enemies:
            if e[2] > 0 or not cascade:
                continue
            ex, ey = e[0] + _ENEMY_W // 2, e[1] + _ENEMY_H // 2
            g = min(((ex - f[0]) ** 2 + (ey - f[1]) ** 2) ** 0.5 for f in cascade)
            if g < self._SACRIFICE_LURE and g < best:
                best = g
                threat = e
        if threat is not None:
            ex, ey = threat[0] + _ENEMY_W // 2, threat[1] + _ENEMY_H // 2
            tx = 2 if ex < _GRID // 2 else _GRID - 3
            dx, dy = tx - ex, self._SACRIFICE_SINK - ey
            d = (dx * dx + dy * dy) ** 0.5 or 1.0
            return (ex + dx / d * r, ey + dy / d * r)
        by_val: dict[int, list[list[int]]] = {}
        for f in model:
            by_val.setdefault(f[2], []).append(f)
        pv = sorted(v for v, fs in by_val.items() if len(fs) >= 2 and v >= 1)
        if not pv:
            pv = sorted(v for v, fs in by_val.items() if len(fs) >= 2)
        if not pv:
            return None
        grp = by_val[pv[0]]
        a, b = min(
            ((grp[i], grp[j]) for i in range(len(grp)) for j in range(i + 1, len(grp))),
            key=lambda p: (p[0][0] - p[1][0]) ** 2 + (p[0][1] - p[1][1]) ** 2,
        )
        d = ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
        if d <= _MERGE_DIST:
            return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        return (a[0] + ux * 7.0, a[1] + uy * 7.0)

    def _model_heuristic(
        self, model: list[list[int]], enemy_xy: tuple[float, float], goal_xy: tuple[float, float]
    ) -> tuple[float, float] | None:
        """The proven L3 choreography (a full live win in 17-19 clicks): deliver
        the top fruit once it reaches the target value, else merge the nearest
        lowest-value pair, but first LURE the enemy to the fruit-farthest corner
        when it threatens an idle fruit (aggression scales with value and as the
        board thins). Operates on model fruits ``[x, y, value]``; returns a
        click ``(x, y)`` or ``None`` when nothing is left to do."""
        top = max(model, key=lambda f: f[2])
        if top[2] >= 3:
            dx, dy = goal_xy[0] - top[0], goal_xy[1] - top[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < 3.5:
                return None
            return (top[0] + dx / dist * _VACUUM_RADIUS, top[1] + dy / dist * _VACUUM_RADIUS)
        best: tuple[float, int, int] | None = None
        for i in range(len(model)):
            for j in range(i + 1, len(model)):
                if model[i][2] == model[j][2]:
                    d = _dist((model[i][0], model[i][1]), (model[j][0], model[j][1]))
                    if best is None or d < best[0]:
                        best = (d, i, j)
        if best is None:
            return None
        d, i, j = best
        a, b = model[i], model[j]
        others = [f for k, f in enumerate(model) if k not in (i, j)]
        max_val = max(f[2] for f in model)
        danger = self._MODEL_LURE_BASE + 4.0 * max_val + max(0, 5 - len(model)) * 3.0
        if others and min(_dist(enemy_xy, (f[0], f[1])) for f in others) < danger:
            park = max(
                self._MODEL_CORNERS,
                key=lambda c: min((_dist(c, (f[0], f[1])) for f in model), default=0.0),
            )
            dx, dy = park[0] - enemy_xy[0], park[1] - enemy_xy[1]
            dist = (dx * dx + dy * dy) ** 0.5 or 1.0
            return (enemy_xy[0] + dx / dist * _VACUUM_RADIUS, enemy_xy[1] + dy / dist * _VACUUM_RADIUS)
        if d <= _MERGE_DIST:
            return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        ux, uy = (b[0] - a[0]) / d, (b[1] - a[1]) / d
        return (a[0] + ux * 7.0, a[1] + uy * 7.0)

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

        # With an enemy on the board (L3+), the cascade only survives if the
        # enemy is driven OUT of play — a proven reactive choreography (a full
        # L3 clear in 19 clicks was found against the live engine): merge the
        # nearest low-value pair, but whenever the enemy threatens any idle
        # (non-merging) fruit, first lure it to the fruit-emptiest corner, with
        # aggression that scales up as fruit values climb and the board thins
        # (the late v2->v3 merge is the fragile one). Gated on enemies so the
        # no-enemy L0-L2 path below stays byte-identical (3/9 floor).
        if enemies:
            return self._enemy_plan(goals, fruits, enemies)

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

    def _enemy_plan(self, goals: list[Region], fruits: list[Region], enemies: list[Region]) -> Cell:
        """Reactive enemy-aware cascade (proven to clear L3 live in 19 clicks).

        Merge the nearest lowest-value pair; but if any enemy is within a
        value-scaled danger radius of a fruit NOT in that pair, first LURE the
        enemy toward the corner farthest from all fruits (vacuuming it there
        pulls it off the cascade and, at a wall, pins it). Deliver the top fruit
        once no pair remains."""
        by_value: dict[int, list[Region]] = {}
        for f in fruits:
            by_value.setdefault(_value(f), []).append(f)
        pair_values = sorted(v for v, fs in by_value.items() if len(fs) >= 2)
        if not pair_values:
            undelivered = [f for f in fruits if not any(_inside_goal(f, g) for g in goals)]
            if not undelivered:
                return (_GRID // 2, _GRID // 2)
            fruit = max(undelivered, key=lambda f: (_value(f), f["size"]))
            goal = _nearest(_centroid(fruit), goals)
            if goal is None:
                return (_GRID // 2, _GRID // 2)
            return self._deliver_click(fruit, _centroid(goal), enemies)

        group = by_value[pair_values[0]]
        a, b = self._parity_safe_pair(group)
        pair_c = {id(a), id(b)}
        others = [f for f in fruits if id(f) not in pair_c]
        max_val = max(_value(f) for f in fruits)
        # Aggression climbs with the value being built and as the board thins.
        danger = _ENEMY_DANGER + 4.0 * max_val + max(0, 5 - len(fruits)) * 3.0
        if others:
            for e in enemies:
                ec = _centroid(e)
                if min(_dist(ec, _centroid(f)) for f in others) < danger:
                    return self._lure_to_corner(e, fruits)
        return self._merge_pair_click(a, b, enemies)

    @staticmethod
    def _parity_safe_pair(group: list[Region]) -> tuple[Region, Region]:
        """The nearest same-value pair whose merge midpoint has NO third group
        member within a vacuum radius — so the single merge click grabs exactly
        two fruits. The source's union-find collapses a clump of N same-value
        fruits to ONE value+1 (not N/2), so a 3-fruit grab loses cascade parity
        (8->4->2->1 needs every merge to consume exactly a pair); this keeps the
        count even. Falls back to the plain nearest pair if none is isolated."""
        ordered: list[tuple[float, Region, Region]] = []
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ordered.append((_dist(_centroid(group[i]), _centroid(group[j])), group[i], group[j]))
        ordered.sort(key=lambda t: t[0])
        for _d, a, b in ordered:
            mid = ((_centroid(a)[0] + _centroid(b)[0]) / 2.0, (_centroid(a)[1] + _centroid(b)[1]) / 2.0)
            if all(id(o) in (id(a), id(b)) or _dist(mid, _centroid(o)) > _VACUUM_RADIUS for o in group):
                return a, b
        return ordered[0][1], ordered[0][2]

    def _lure_to_corner(self, enemy: Region, fruits: list[Region]) -> Cell:
        """Vacuum the enemy one hop toward the play-field corner that is
        farthest from every fruit — pulls it off the cascade toward an empty
        wall where repeated lures pin it, without grabbing a merge fruit."""
        corners = [
            (_PLAY_TOP, 2), (_PLAY_TOP, _GRID - 2), (_PLAY_BOTTOM, 2), (_PLAY_BOTTOM, _GRID - 2),
            (_PLAY_TOP, _GRID // 2), (_PLAY_BOTTOM, _GRID // 2),
        ]
        park = max(corners, key=lambda c: min((_dist(c, _centroid(f)) for f in fruits), default=0.0))
        ec = _centroid(enemy)
        d = _dist(ec, park)
        if d <= 1e-9:
            return _clamp_click(*ec)
        row = ec[0] + (park[0] - ec[0]) / d * _VACUUM_RADIUS
        col = ec[1] + (park[1] - ec[1]) / d * _VACUUM_RADIUS
        return _clamp_click(row, col)

    def _merge_move(self, fruits: list[Region], enemies: list[Region]) -> Cell | None:
        """One click toward merging the lowest value that still has a pair.

        Picks the lowest value with ≥2 fruits. With NO enemies (L0-L2), the
        two NEAREST members are merged — midpoint click within _MERGE_DIST,
        else pull one toward the other (byte-identical to the pre-enemy
        behaviour, so the 3/9 floor is untouched). With enemies present (L3+),
        the pair is instead chosen for maximum clearance from the PREDICTED
        enemy swarm (:meth:`_predict_enemies`): the merge zone that the chasing
        pack is least able to reach during the ~4-step merge. If even the best
        pair sits inside the swarm's one-click reach, the pack is LURED
        (:meth:`_lure_click`) instead of feeding it a fruit to downgrade.
        Returns None only when no value has a pair.
        """
        by_value: dict[int, list[Region]] = {}
        for f in fruits:
            by_value.setdefault(_value(f), []).append(f)
        pair_values = sorted(v for v, fs in by_value.items() if len(fs) >= 2)
        if not pair_values:
            return None
        group = by_value[pair_values[0]]

        if not enemies:
            a, b = self._nearest_pair(group)
            return self._merge_pair_click(a, b, enemies)

        predicted = self._predict_enemies(fruits, enemies)
        best: tuple[float, Region, Region] | None = None
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                mid = self._midpoint(group[i], group[j])
                clearance = min((_dist(mid, p) for p in predicted), default=_ENEMY_CLEARANCE)
                # Tie-break toward closer pairs (cheaper merge) by subtracting
                # a small fraction of the pair distance from the clearance key.
                key = clearance - 0.01 * _dist(_centroid(group[i]), _centroid(group[j]))
                if best is None or key > best[0]:
                    best = (key, group[i], group[j])
        assert best is not None
        _key, a, b = best
        if min((_dist(self._midpoint(a, b), p) for p in predicted), default=_ENEMY_CLEARANCE) < _ENEMY_CLEARANCE:
            return self._lure_click(a, b, enemies)
        return self._merge_pair_click(a, b, enemies)

    def _merge_pair_click(self, a: Region, b: Region, enemies: list[Region]) -> Cell:
        """Midpoint click when the pair is within one vacuum's grab of both,
        else pull one member toward the other."""
        ac, bc = _centroid(a), _centroid(b)
        if _dist(ac, bc) <= _MERGE_DIST:
            return _clamp_click((ac[0] + bc[0]) / 2.0, (ac[1] + bc[1]) / 2.0)
        return self._deliver_click(a, bc, enemies)

    @staticmethod
    def _midpoint(a: Region, b: Region) -> tuple[float, float]:
        ac, bc = _centroid(a), _centroid(b)
        return ((ac[0] + bc[0]) / 2.0, (ac[1] + bc[1]) / 2.0)

    @staticmethod
    def _predict_enemies(fruits: list[Region], enemies: list[Region]) -> list[tuple[float, float]]:
        """Where each enemy will be next click: ``_ENEMY_REACH`` px toward its
        nearest fruit (the source's deterministic chase). A frame-derived
        forecast used only to place merges out of the swarm's reach."""
        out: list[tuple[float, float]] = []
        for e in enemies:
            ec = _centroid(e)
            target = _nearest(ec, fruits)
            if target is None:
                out.append(ec)
                continue
            tc = _centroid(target)
            d = _dist(ec, tc)
            if d <= 1e-9:
                out.append(ec)
                continue
            step = min(_ENEMY_REACH, d)
            out.append((ec[0] + (tc[0] - ec[0]) / d * step, ec[1] + (tc[1] - ec[1]) / d * step))
        return out

    def _lure_click(self, a: Region, b: Region, enemies: list[Region]) -> Cell:
        """Click on the enemy swarm's centroid to VACUUM the pack (the source
        exempts vacuumed enemies from chasing and gives them a cooldown),
        clearing the merge zone for the next click. Biased slightly AWAY from
        the merge pair so the lure pulls the swarm off the fruits rather than
        onto them."""
        ex = sum(_centroid(e)[0] for e in enemies) / len(enemies)
        ey = sum(_centroid(e)[1] for e in enemies) / len(enemies)
        mid = self._midpoint(a, b)
        d = _dist((ex, ey), mid)
        if d > 1e-9:
            ex += (ex - mid[0]) / d * _VACUUM_RADIUS
            ey += (ey - mid[1]) / d * _VACUUM_RADIUS
        return _clamp_click(ex, ey)

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
