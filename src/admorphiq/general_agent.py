"""Efficiency-first general agent: cheap discovery + efficient grid navigation.

This is the first increment of the Milestone-1 architecture
(`docs/sprint_m1_architecture_20260625.md`). The competition metric squares
the human/agent action-efficiency ratio, so the spine is *efficiency*, not
*completion*: a level cleared in a small multiple of the human action count
scores well, brute force in hundreds scores ~0.

Pipeline (per level, driven one action at a time by the harness):

1. **Cheap discovery** (``_PHASE_DISCOVERY``) — probe each available movement
   action (1-5, 7) once; diff the canonical layer before/after; detect the
   *player* as the small connected component that TRANSLATES, and learn the
   action -> (dx, dy) cell-shift map. Bounded to ``DISCOVERY_BUDGET`` actions.
2. **Entity extraction** — connected-components on the canonical layer to find
   the player, obstacle/wall cells (large clusters / background), and a goal
   (a distinct rare cluster).
3. **Efficient nav plan** (``_PHASE_EXECUTE``) — if a player + plausible goal
   are found and the direction map is known, BFS over the GRID CELL state
   (player position, walls blocking) for the SHORTEST path, translate to the
   learned action sequence, and emit those actions. On level-up, re-discover
   and re-plan. When no player/goal is identified, fall back to a disciplined
   cheap-explore (``_PHASE_EXPLORE``).

The agent reads ONLY the official frame observation (``frame``, ``state``,
``available_actions``, ``levels_completed``); no game internals, no
game-title / game-id branching, no hardcoded sequences. It is therefore
general and transfers to the private Kaggle test set.

The grid-abstraction and BFS logic are pure functions (``infer_direction_map``,
``grid_bfs``, ``frame_to_cells`` ...) so they can be unit-tested without an env.
"""

from __future__ import annotations

import os
import random
from collections import Counter, deque

import numpy as np

# ── Tunables ────────────────────────────────────────────────────────────────

# Movement (no-coordinate) actions we probe during discovery, in id order.
_MOVE_ACTION_IDS: tuple[int, ...] = (1, 2, 3, 4, 5, 7)
# Max actions spent on discovery probing per level. Kept small — wasted probe
# actions also hurt the efficiency ratio (human L1 baselines are ~16-42).
#
# Discovery is *recentering-aware*: a naive single sweep that probes 1->2->3->4
# without restoring the player's position mislearns games where the player
# starts wall-bound. After the player moves right+down, the up/left probes only
# produce ~1px diffs (blocked) and their vectors are never inferred — leaving a
# 2-direction map the grid planner cannot navigate with. Instead, after each
# clean translation we record the vector and, before probing an action that did
# NOT move the player, issue a *counter-move* (the inverse of an already-learned
# direction) to free the player from the wall, then re-probe. Each action gets
# up to ``_DISCOVERY_MAX_ATTEMPTS`` clean tries before it is declared null.
DISCOVERY_BUDGET = 16
_DISCOVERY_MAX_ATTEMPTS = 3
# A centroid shift this fraction of the cell pitch (or, before pitch is known,
# this many pixels) counts as a clean translation rather than blocked jitter.
_MIN_TRANSLATION_PX = 2.0
# A connected component is "small" enough to be a player if it is at most this
# many cells (players are compact sprites, not background fields).
_MAX_PLAYER_SIZE = 64
# A real player sprite is more than a single pixel; size-1 movers are cursor /
# anti-aliasing dots that track the player but give a noisy 1-pixel step.
_MIN_PLAYER_SIZE = 3
# A player colour appears in only a few instances (typically 1). Colours with
# more components than this tile the background / maze and are not the player.
_MAX_PLAYER_INSTANCES = 3
# Minimum component size to be considered a real object (filters single-pixel
# HUD flicker / anti-aliasing).
_MIN_COMPONENT_SIZE = 1
# A goal marker must be at least this large; single-pixel rare colours are
# anti-aliasing / cursor artefacts, not the target.
_MIN_GOAL_SIZE = 3
# Epsilon-greedy exploration rate in the cheap-explore fallback.
_EXPLORE_EPSILON = 0.15
# Consecutive EXECUTE steps with no player-cell change before bailing to
# cheap-explore (the abstract model is too wrong to navigate).
_STUCK_LIMIT = 4


# ── Pure connected-components / entity helpers ───────────────────────────────


def canonical_layer(frame: list | np.ndarray) -> np.ndarray:
    """Return the canonical (top-most) 2-D layer of a multi-layer frame.

    ``frame`` is ``(num_layers, 64, 64)`` int values 0-15. The last layer is
    the canonical render surface (matches the repo's StochasticGoose
    convention). Returns an empty ``(0, 0)`` array when there is no frame.
    """
    arr = np.asarray(frame)
    if arr.size == 0:
        return np.zeros((0, 0), dtype=np.int32)
    if arr.ndim == 3:
        return arr[-1].astype(np.int32)
    if arr.ndim == 2:
        return arr.astype(np.int32)
    return arr.reshape(arr.shape[-2:]).astype(np.int32)


def connected_components(
    layer: np.ndarray, background: int | None = None, min_size: int = _MIN_COMPONENT_SIZE
) -> list[dict]:
    """4-connected components of same-colour cells, excluding the background.

    Returns one dict per component with keys ``color``, ``size``, ``cx``,
    ``cy`` (centroid, column/row), and ``cells`` (set of (row, col)).
    Background defaults to the single most frequent colour.
    """
    if layer.size == 0:
        return []
    if background is None:
        vals, counts = np.unique(layer, return_counts=True)
        background = int(vals[int(counts.argmax())])

    h, w = layer.shape
    visited = np.zeros((h, w), dtype=bool)
    out: list[dict] = []
    for sy in range(h):
        for sx in range(w):
            if visited[sy, sx]:
                continue
            color = int(layer[sy, sx])
            if color == background:
                visited[sy, sx] = True
                continue
            cells: list[tuple[int, int]] = []
            stack = [(sy, sx)]
            while stack:
                y, x = stack.pop()
                if y < 0 or y >= h or x < 0 or x >= w or visited[y, x]:
                    continue
                if int(layer[y, x]) != color:
                    continue
                visited[y, x] = True
                cells.append((y, x))
                stack.extend(((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)))
            if len(cells) < min_size:
                continue
            ys = [c[0] for c in cells]
            xs = [c[1] for c in cells]
            out.append(
                {
                    "color": color,
                    "size": len(cells),
                    "cx": sum(xs) / len(xs),
                    "cy": sum(ys) / len(ys),
                    "cells": set(cells),
                }
            )
    return out


def _candidate_shifts(
    before: np.ndarray, after: np.ndarray, background: int
) -> list[tuple[dict, tuple[float, float]]]:
    """All small before-components that translated >= ~1 cell to an after twin.

    Each result is ``(before_component, (dx, dy))``. Unlike a single best
    match this returns every plausible mover, so a 1-pixel cursor cannot
    mask the real (larger, multi-probe-consistent) player — selection across
    probes is left to :func:`infer_direction_map`.
    """
    before_comps = connected_components(before, background)
    # Count components per colour in the BEFORE frame. A colour that tiles the
    # maze (many identical blocks) produces spurious nearest-twin "shifts", so
    # only treat colours with few instances as plausible movers — players are
    # rare-instance sprites, not repeated wall tiles.
    color_count: Counter[int] = Counter(c["color"] for c in before_comps)
    cb = [
        c
        for c in before_comps
        if _MIN_PLAYER_SIZE <= c["size"] <= _MAX_PLAYER_SIZE
        and color_count[c["color"]] <= _MAX_PLAYER_INSTANCES
    ]
    ca = connected_components(after, background)
    by_color: dict[int, list[dict]] = {}
    for c in ca:
        by_color.setdefault(c["color"], []).append(c)

    out: list[tuple[dict, tuple[float, float]]] = []
    for b in cb:
        cands = by_color.get(b["color"], [])
        if not cands:
            continue
        nearest = min(
            cands,
            key=lambda a: (a["cx"] - b["cx"]) ** 2 + (a["cy"] - b["cy"]) ** 2,
        )
        if abs(nearest["size"] - b["size"]) > max(2, b["size"] // 2):
            continue
        dx = nearest["cx"] - b["cx"]
        dy = nearest["cy"] - b["cy"]
        # Require a real translation, not sub-pixel HUD/progress-bar drift. A
        # game player steps by the cell pitch (typically >= a few px); a timer
        # bar or counter creeps ~1px/action and would otherwise be mistaken for
        # a mover and pollute the direction map (the tu93 HUD-bar bug).
        if (dx * dx + dy * dy) ** 0.5 < _MIN_TRANSLATION_PX:
            continue
        out.append((b, (dx, dy)))
    return out


def infer_direction_map(
    probes: list[dict], background: int
) -> tuple[dict[int, tuple[int, int]], dict | None]:
    """Learn the action -> (dx, dy) cell-shift map from movement probes.

    ``probes`` is a list of ``{"aid", "before", "after"}`` (frames as 2-D
    arrays). Returns ``(dir_map, player_component)`` where ``dir_map`` maps an
    action id to a quantised step ``(dx, dy)`` in pixels, and
    ``player_component`` is the chosen player.

    Two-pass selection: first tally, per colour, how many *distinct action
    directions* moved a component of that colour and the total shift. The
    player is the colour with the most distinct directions (tie-broken by
    total shift, then by larger size to skip 1-pixel cursor sprites). The
    dir_map is then built only from that player colour's moves — so a tiny
    cursor that happens to translate cannot hijack the mapping.
    """
    # color -> {"dirs": {aid: (rdx, rdy)}, "shift": float, "size": int, "comp": dict}
    tally: dict[int, dict] = {}
    for probe in probes:
        for comp, (dx, dy) in _candidate_shifts(probe["before"], probe["after"], background):
            rdx, rdy = int(round(dx)), int(round(dy))
            if rdx == 0 and rdy == 0:
                continue
            color = comp["color"]
            entry = tally.setdefault(
                color, {"dirs": {}, "shift": 0.0, "size": comp["size"], "comp": comp}
            )
            entry["dirs"][probe["aid"]] = (rdx, rdy)
            entry["shift"] += (rdx * rdx + rdy * rdy) ** 0.5
            entry["size"] = max(entry["size"], comp["size"])
    if not tally:
        return {}, None

    def _rank(item: tuple[int, dict]) -> tuple:
        _, e = item
        return (len(e["dirs"]), e["shift"], e["size"])

    best_color, best = max(tally.items(), key=_rank)
    return dict(best["dirs"]), best["comp"]


def player_centroid(
    layer: np.ndarray, player_color: int, background: int
) -> tuple[float, float] | None:
    """Centroid ``(cx, cy)`` of the largest player-coloured component, or None.

    Used during discovery to measure the player's translation between probes
    directly from the live frame (independent of nearest-twin matching), so a
    blocked / no-op probe is detectable as a near-zero shift.
    """
    comps = [
        c
        for c in connected_components(layer, background)
        if c["color"] == player_color and c["size"] <= _MAX_PLAYER_SIZE
    ]
    if not comps:
        return None
    p = max(comps, key=lambda c: c["size"])
    return (p["cx"], p["cy"])


def floor_colors_from_probes(
    probes: list[dict], player_color: int, background: int
) -> set[int]:
    """Colours revealed where the player vacated — i.e. the walkable floor.

    For each probe, take the player's cells in the ``before`` frame and read
    what colour occupies those same cells in ``after``. Where the player has
    moved away, the revealed colour is the floor the player stood on. The
    background is always implicitly floor and is excluded from the returned
    set (callers add it separately). The player colour is excluded (the player
    may not have fully vacated a multi-cell footprint).
    """
    floor: set[int] = set()
    for probe in probes:
        before = probe.get("before")
        after = probe.get("after")
        if before is None or after is None or before.shape != after.shape:
            continue
        player_mask = before == player_color
        if not player_mask.any():
            continue
        revealed = after[player_mask]
        for v in np.unique(revealed):
            c = int(v)
            if c not in (player_color, background):
                floor.add(c)
    return floor


def _opposite_action(
    aid: int, learned: dict[int, tuple[int, int]]
) -> int | None:
    """A learned action whose step opposes ``aid``'s expected direction.

    Used to free a wall-bound player before re-probing ``aid``: if ``aid`` is
    not yet learned we cannot know its axis, so we pick *any* learned action
    (it relocates the player and a later re-probe sees the real translation).
    Prefers an action whose vector is most anti-parallel to ``aid``'s when
    ``aid`` is already partially known; otherwise returns the first learned
    action. None when nothing is learned yet.
    """
    if not learned:
        return None
    if aid in learned:
        ax, ay = learned[aid]
        # Most anti-parallel learned move (largest negative dot product).
        ranked = sorted(
            learned.items(),
            key=lambda kv: kv[1][0] * ax + kv[1][1] * ay,
        )
        for cand, _ in ranked:
            if cand != aid:
                return cand
    # Fall back to any learned action (deterministic: lowest id).
    return min(learned)


def pick_next_probe(
    targets: list[int],
    learned: dict[int, tuple[int, int]],
    attempts: dict[int, int],
    last_moved: bool,
    last_was_probe_of: int | None,
    max_attempts: int = _DISCOVERY_MAX_ATTEMPTS,
) -> tuple[str, int | None]:
    """Decide the next discovery action (pure, env-free, unit-tested).

    Returns ``(kind, aid)`` where ``kind`` is:
      * ``"probe"`` — issue ``aid`` and measure the player's translation;
      * ``"recenter"`` — issue ``aid`` (a learned inverse) to free a wall-bound
        player, then a later call re-probes the blocked action;
      * ``"done"`` — every target is learned or out of attempts.

    Policy (breadth-first sweep, then recenter-and-retry):
      * Every unlearned target is probed ONCE before any is retried — the cheap
        first sweep reveals which directions are unblocked from the start cell
        and gives us learned inverses to recenter with.
      * On a *retry* (attempts >= 1) of a still-unlearned target, the player was
        blocked there last time, so we recenter first (move via a learned action
        to free the player) and re-probe on the following call.
      * A target is abandoned after ``max_attempts`` probe attempts.
    """
    pending = [
        a for a in targets if a not in learned and attempts.get(a, 0) < max_attempts
    ]
    if not pending:
        return ("done", None)
    # Breadth-first: lowest attempt count first (then id order) so each target
    # is tried once before any second attempt.
    nxt = min(pending, key=lambda a: (attempts.get(a, 0), a))
    if attempts.get(nxt, 0) >= 1:
        # This target already failed once → relocate the player before retrying.
        recenter = _opposite_action(nxt, learned)
        if recenter is not None and not (
            last_was_probe_of is None and not last_moved
        ):
            # Only recenter if the previous call was not itself a recenter move
            # (avoid two recenters in a row without an intervening probe).
            return ("recenter", recenter)
    return ("probe", nxt)


def _step_cell_size(dir_map: dict[int, tuple[int, int]]) -> int:
    """Estimate the grid cell size (pixels per move) from the shift vectors.

    Uses the smallest non-zero absolute component of any learned step. Falls
    back to 1 when nothing usable is present.
    """
    mags: list[int] = []
    for dx, dy in dir_map.values():
        for v in (abs(dx), abs(dy)):
            if v > 0:
                mags.append(v)
    if not mags:
        return 1
    return max(1, min(mags))


def frame_to_cells(
    layer: np.ndarray,
    cell: int,
    player_color: int,
    background: int,
    floor_colors: set[int] | None = None,
) -> tuple[np.ndarray, str]:
    """Downsample the pixel layer to a coarse grid, classifying walkability.

    Each ``cell``x``cell`` block becomes one grid cell. A block is a WALL
    (``False`` = blocked) when its dominant colour is a *solid obstacle*: not
    the background, not the player, and not one of the observed ``floor_colors``
    (colours the player was seen standing on during discovery), and the block
    is (near-)uniformly that colour. Background / player / floor / mixed blocks
    are walkable (``True``).

    ``floor_colors`` is the key generalisation lever: in many games the
    walkable floor is itself a non-background colour, so without it almost the
    whole maze is mislabelled as wall. When None, only background + player are
    treated as walkable.

    Returns ``(walkable_grid, mode)``. ``mode`` is ``"grid"`` when the layer
    divided cleanly; informational only.
    """
    if layer.size == 0 or cell <= 0:
        return np.ones((0, 0), dtype=bool), "empty"
    if floor_colors:
        # We observed the actual walkable floor: trust it. The global
        # most-frequent colour is then NOT assumed walkable — on coloured-floor
        # mazes the most-frequent colour is the WALL field, so including it
        # inverts walkability (the ls20-class bug).
        walkable_colors = set(floor_colors) | {player_color}
    else:
        walkable_colors = {background, player_color}
    h, w = layer.shape
    gh, gw = h // cell, w // cell
    if gh == 0 or gw == 0:
        return np.ones((1, 1), dtype=bool), "degenerate"
    walkable = np.ones((gh, gw), dtype=bool)
    for gy in range(gh):
        for gx in range(gw):
            block = layer[gy * cell : (gy + 1) * cell, gx * cell : (gx + 1) * cell]
            vals, counts = np.unique(block, return_counts=True)
            dom = int(vals[int(counts.argmax())])
            dom_frac = counts.max() / block.size
            if dom not in walkable_colors and dom_frac >= 0.75:
                walkable[gy, gx] = False
    return walkable, "grid"


def grid_bfs(
    walkable: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    step_dirs: dict[int, tuple[int, int]],
) -> list[int] | None:
    """Shortest action sequence from ``start`` cell to ``goal`` cell.

    ``walkable`` is a 2-D bool grid (``True`` = passable). ``start``/``goal``
    are ``(row, col)``. ``step_dirs`` maps an action id to a unit grid step
    ``(d_col, d_row)`` (note: x = col, y = row). Moves into blocked or
    out-of-bounds cells are rejected. Returns the list of action ids, or None
    if unreachable.
    """
    gh, gw = walkable.shape
    if gh == 0 or gw == 0:
        return None
    sr, sc = start
    gr, gc = goal
    if not (0 <= sr < gh and 0 <= sc < gw and 0 <= gr < gh and 0 <= gc < gw):
        return None
    if not walkable[gr, gc]:
        return None
    if start == goal:
        return []

    visited = {start}
    queue: deque[tuple[tuple[int, int], list[int]]] = deque([(start, [])])
    while queue:
        (r, c), path = queue.popleft()
        for aid, (dcol, drow) in step_dirs.items():
            nr, nc = r + drow, c + dcol
            if not (0 <= nr < gh and 0 <= nc < gw):
                continue
            if not walkable[nr, nc]:
                continue
            if (nr, nc) in visited:
                continue
            npath = path + [aid]
            if (nr, nc) == goal:
                return npath
            visited.add((nr, nc))
            queue.append(((nr, nc), npath))
    return None


def corridor_color_from_probes(
    probes: list[dict], player_color: int, background: int
) -> int | None:
    """Colour of the open *edge* the player traverses when it moves.

    In interleaved-pitch mazes (tu93-class) the node a player stops on renders
    as wall colour, while the corridor connecting two adjacent nodes is a
    distinct ``open`` colour. The player's *destination node* therefore looks
    like a wall, but the midpoint between its start and end centroid sits on
    the corridor. For every probe where the player translated, sample the
    before-frame colour at the midpoint of its (before, after) centroids; the
    most frequent such colour is the corridor/edge-open colour.

    Returns None when no probe produced a clean translation (callers then fall
    back to the node-dominant-colour walkability model). Fully observation
    driven — never keys on a game id/title or a hardcoded colour.
    """
    votes: Counter[int] = Counter()
    for probe in probes:
        before = probe.get("before")
        after = probe.get("after")
        if before is None or after is None or before.shape != after.shape:
            continue
        cb = player_centroid(before, player_color, background)
        ca = player_centroid(after, player_color, background)
        if cb is None or ca is None:
            continue
        if (ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2 < _MIN_TRANSLATION_PX**2:
            continue
        mx = int(round((cb[0] + ca[0]) / 2))
        my = int(round((cb[1] + ca[1]) / 2))
        h, w = before.shape
        if 0 <= my < h and 0 <= mx < w:
            c = int(before[my, mx])
            if c not in (player_color, background):
                votes[c] += 1
    if not votes:
        return None
    return max(votes, key=lambda k: votes[k])


def _block_dominant(layer: np.ndarray, r0: int, c0: int, size: int) -> int:
    """Dominant colour of the ``size``x``size`` block at ``(r0, c0)`` (clamped)."""
    h, w = layer.shape
    r0c, c0c = max(0, r0), max(0, c0)
    block = layer[r0c : r0c + size, c0c : c0c + size]
    if block.size == 0:
        return -1
    vals, counts = np.unique(block, return_counts=True)
    return int(vals[int(counts.argmax())])


def edge_grid_bfs(
    layer: np.ndarray,
    anchor: tuple[float, float],
    pitch: int,
    goal_px: tuple[float, float],
    step_dirs: dict[int, tuple[int, int]],
    corridor_color: int,
    player_color: int,
    background: int,
    grid_radius: int = 12,
) -> list[int] | None:
    """Shortest action sequence over an *edge-walkable* node grid.

    Nodes are spaced ``pitch`` pixels apart, anchored at the player's current
    centroid ``anchor`` (px ``(cx, cy)``). A move in a learned direction is
    legal iff the half-pitch *midpoint* block toward the neighbour is the
    ``corridor_color`` (the open edge) — this captures interleaved-pitch mazes
    where the destination node itself renders as wall colour. The goal node is
    the grid node nearest the goal marker ``goal_px``.

    ``step_dirs`` maps an action id to a unit grid step ``(d_col, d_row)``.
    Returns the action-id path, or None if the goal node is unreachable.
    Pure / env-free so it is unit-testable.
    """
    if pitch <= 0 or not step_dirs:
        return None
    ax, ay = anchor
    gx, gy = goal_px
    goal_gr = int(round((gy - ay) / pitch))
    goal_gc = int(round((gx - ax) / pitch))
    goal = (goal_gr, goal_gc)
    if goal == (0, 0):
        return []
    half = max(1, pitch // 2)
    block = max(1, pitch // 2)

    def edge_open(gr: int, gc: int, dcol: int, drow: int) -> bool:
        # Midpoint pixel of the edge between this node and the neighbour.
        cx = ax + gc * pitch + dcol * half
        cy = ay + gr * pitch + drow * half
        dom = _block_dominant(
            layer, int(round(cy)) - block // 2, int(round(cx)) - block // 2, block
        )
        return dom in (corridor_color, player_color)

    visited = {(0, 0)}
    queue: deque[tuple[tuple[int, int], list[int]]] = deque([((0, 0), [])])
    while queue:
        (gr, gc), path = queue.popleft()
        for aid, (dcol, drow) in step_dirs.items():
            ngr, ngc = gr + drow, gc + dcol
            if (ngr, ngc) in visited:
                continue
            if abs(ngr) > grid_radius or abs(ngc) > grid_radius:
                continue
            if not edge_open(gr, gc, dcol, drow):
                continue
            npath = path + [aid]
            if (ngr, ngc) == goal:
                return npath
            visited.add((ngr, ngc))
            queue.append(((ngr, ngc), npath))
    return None


def goal_centroid_px(
    layer: np.ndarray,
    player_color: int,
    background: int,
    target_color: int | None = None,
) -> tuple[float, float] | None:
    """Pixel centroid ``(cx, cy)`` of the goal marker, or None.

    Same selection policy as :func:`pick_goal_cell` (explicit ``target_color``
    else the rarest non-player non-background colour's largest cluster) but
    returns sub-pixel pixel coordinates, which the edge-grid navigator needs to
    anchor the goal node precisely. For tu93 this resolves to the colour-14
    exit marker's centroid.
    """
    comps = [
        c
        for c in connected_components(layer, background)
        if c["color"] != player_color and c["size"] >= _MIN_GOAL_SIZE
    ]
    if not comps:
        return None
    if target_color is not None:
        tc_comps = [c for c in comps if c["color"] == target_color]
        if tc_comps:
            t = max(tc_comps, key=lambda c: c["size"])
            return (t["cx"], t["cy"])
    color_area: Counter[int] = Counter()
    for c in comps:
        color_area[c["color"]] += c["size"]
    rare_color = min(color_area, key=lambda k: color_area[k])
    rare_comps = [c for c in comps if c["color"] == rare_color]
    t = max(rare_comps, key=lambda c: c["size"])
    return (t["cx"], t["cy"])


def pick_goal_cell(
    layer: np.ndarray,
    cell: int,
    player_color: int,
    background: int,
    target_color: int | None = None,
) -> tuple[int, int] | None:
    """Choose the most plausible goal grid-cell.

    When ``target_color`` is given (e.g. supplied by the LLM reasoning layer)
    and that colour has a usable cluster in the frame, the goal is the largest
    cluster of that colour. Otherwise the goal is the centroid (in grid
    coordinates) of the rarest non-player, non-background colour cluster —
    distinct rare clusters are usually the target / exit. Returns ``(row,
    col)`` or None when nothing qualifies.
    """
    comps = [
        c
        for c in connected_components(layer, background)
        if c["color"] != player_color and c["size"] >= _MIN_GOAL_SIZE
    ]
    if not comps:
        return None
    if target_color is not None:
        tc_comps = [c for c in comps if c["color"] == target_color]
        if tc_comps:
            target = max(tc_comps, key=lambda c: c["size"])
            gr = int(round(target["cy"])) // cell
            gc = int(round(target["cx"])) // cell
            gh, gw = layer.shape[0] // cell, layer.shape[1] // cell
            gr = max(0, min(gh - 1, gr))
            gc = max(0, min(gw - 1, gc))
            return (gr, gc)
    # Rarest colour overall (fewest cells of that colour) → most likely target.
    color_area: Counter[int] = Counter()
    for c in comps:
        color_area[c["color"]] += c["size"]
    rare_color = min(color_area, key=lambda k: color_area[k])
    rare_comps = [c for c in comps if c["color"] == rare_color]
    # Largest cluster of the rare colour (the actual goal marker).
    target = max(rare_comps, key=lambda c: c["size"])
    gr = int(round(target["cy"])) // cell
    gc = int(round(target["cx"])) // cell
    gh, gw = layer.shape[0] // cell, layer.shape[1] // cell
    gr = max(0, min(gh - 1, gr))
    gc = max(0, min(gw - 1, gc))
    return (gr, gc)


# ── Agent FSM ────────────────────────────────────────────────────────────────

_PHASE_DISCOVERY = "discovery"
_PHASE_EXECUTE = "execute"
_PHASE_EXPLORE = "explore"
# Pattern-match primitive (paint-to-match / GF(2) toggle). Dispatched after
# discovery when no navigation plan exists but a pattern detector fires.
_PHASE_PATTERN = "pattern"
# Max candidate cells to probe when measuring a toggle stencil (2 clicks each).
_PATTERN_TOGGLE_PROBE_CAP = 12


class GeneralAgent:
    """Stateful efficiency-first agent driven one action per call.

    Harness-friendly: exposes ``is_done(frames, latest_frame)`` and
    ``choose_action(frames, latest_frame)`` accepting the raw arcengine
    observation (``.frame``, ``.state``, ``.available_actions``,
    ``.levels_completed``). It owns no env; it only observes the frame the
    harness hands it and emits the next action.
    """

    MAX_ACTIONS = 600

    def __init__(
        self,
        seed: int = 0,
        use_llm: bool | None = None,
        llm_candidate: str = "qwen_3_14b_q4",
    ) -> None:
        self._rng = random.Random(seed)
        self._action_count = 0
        self._levels_completed = 0
        # LLM reasoning layer is opt-in: explicit constructor flag wins, else
        # the ADMORPHIQ_USE_LLM=1 env gate. Off by default so the pure
        # deterministic path (and the no-LLM test harness) is unaffected. The
        # backend is loaded lazily on the first discovery so construction never
        # requires Ollama / GGUF to be present.
        if use_llm is None:
            use_llm = os.environ.get("ADMORPHIQ_USE_LLM", "") == "1"
        self._use_llm = bool(use_llm)
        self._llm_candidate = llm_candidate
        self._llm = None
        self._llm_loaded = False
        # Most recent LLM hypothesis (recorded for tracing / inspection).
        self.last_hypothesis: dict | None = None
        # Game-scope control memory (NOT cleared on level-up). The action ->
        # (dx, dy) map, player colour and corridor colour are properties of the
        # game's CONTROLS / rendering, which are constant across levels — only
        # the layout changes. Persisting them lets later levels skip the costly
        # (and, in step-budgeted games like tu93, dangerous) re-probe sweep and
        # plan immediately from the clean level-start position.
        self._known_dir_map: dict[int, tuple[int, int]] = {}
        self._known_player_color: int | None = None
        self._known_corridor_color: int | None = None
        self._reset_level_state()

    def _reset_level_state(self) -> None:
        """Clear all per-level discovery / plan state (called on level-up)."""
        self._phase = _PHASE_DISCOVERY
        # Discovery budget is PER LEVEL, not per game: record the global action
        # count at which this level's discovery begins so the budget gate
        # measures actions spent on THIS level. Without this, ``_action_count``
        # (which never resets) is already past ``DISCOVERY_BUDGET`` by L2, so
        # discovery is skipped on every level after the first — the agent never
        # re-learns the direction map on the new layout and wanders to GAME_OVER.
        self._level_action_base = getattr(self, "_action_count", 0)
        # One-shot guard: try reusing carried control knowledge once per level
        # before falling back to active probing.
        self._seed_attempted = False
        self._probes: list[dict] = []
        self._pending_probe: dict | None = None
        self._dir_map: dict[int, tuple[int, int]] = {}
        self._player_color: int | None = None
        self._background: int | None = None
        # Open-edge colour for the interleaved-pitch maze model (derived from
        # probe midpoints at end of discovery); None ⇒ use node-dominant model.
        self._corridor_color: int | None = None
        # LLM-supplied goal colour for this level (overrides pick_goal_cell's
        # rarest-colour heuristic when set); None ⇒ pure deterministic goal.
        self._llm_target_color: int | None = None
        # Recentering-aware discovery bookkeeping.
        self._disc_targets: list[int] | None = None
        self._disc_learned: dict[int, tuple[int, int]] = {}
        self._disc_attempts: Counter[int] = Counter()
        self._disc_last_centroid: tuple[float, float] | None = None
        self._disc_last_probe_aid: int | None = None
        self._disc_last_moved: bool = False
        # Closed-loop execution bookkeeping.
        self._last_player_cell: tuple[int, int] | None = None
        self._stuck_steps = 0
        # Pattern-match primitive bookkeeping (paint / GF(2) toggle).
        self._pat_kind: str | None = None
        self._pat_queue: list[tuple[int, int, int]] = []
        self._pat_cells: list[tuple[int, int]] = []
        self._pat_sub: str | None = None
        self._pat_j: int = 0
        self._pat_before: np.ndarray | None = None
        self._pat_click_probes: list[dict] = []
        # Cheap-explore fallback bookkeeping.
        self._explore_last_sig: tuple = ()
        self._explore_pending: int | None = None
        self._explore_tries: Counter[int] = Counter()
        self._explore_changes: Counter[int] = Counter()
        self._explore_cursor = 0

    # ── official-shaped interface ────────────────────────────────────────────

    def is_done(self, frames: list, latest_frame) -> bool:
        """Stop on WIN (biggest efficiency lever) or when out of budget."""
        if _state_name(latest_frame) == "WIN":
            return True
        return self._action_count >= self.MAX_ACTIONS

    def choose_action(self, frames: list, latest_frame):
        """Emit the next action for the current observation."""
        from arcengine import GameAction

        self._maybe_level_up(latest_frame)

        avail = _avail_ids(latest_frame)
        layer = canonical_layer(getattr(latest_frame, "frame", latest_frame))

        if _state_name(latest_frame) == "GAME_OVER" or layer.size == 0 or not avail:
            return self._emit(GameAction.RESET)

        if self._background is None and layer.size:
            vals, counts = np.unique(layer, return_counts=True)
            self._background = int(vals[int(counts.argmax())])

        if self._phase == _PHASE_DISCOVERY:
            return self._discovery_step(layer, avail, latest_frame)
        if self._phase == _PHASE_EXECUTE:
            return self._execute_step(layer, avail, latest_frame)
        if self._phase == _PHASE_PATTERN:
            return self._pattern_step(layer, avail, latest_frame)
        return self._explore_step(layer, avail, latest_frame)

    # ── level-transition handling ────────────────────────────────────────────

    def _maybe_level_up(self, latest_frame) -> None:
        lvl = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if lvl > self._levels_completed:
            self._levels_completed = lvl
            # New level: discard the old plan and re-discover.
            self._reset_level_state()

    # ── discovery phase ──────────────────────────────────────────────────────

    def _discovery_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Probe movement actions with recentering until all dirs are learned.

        Two stages share one probe buffer. The player colour and per-action
        vectors are re-derived after every probe by :func:`infer_direction_map`
        — the proven multi-direction-consistency identifier — so a wall block /
        animated tile cannot be mistaken for the player. Live centroid tracking
        (with the now-known player colour) only decides *did this probe move
        the player*; an unmoved action is re-probed after a recentering move
        that frees the player from the wall. Bounded by ``DISCOVERY_BUDGET``.
        """
        from arcengine import GameAction

        bg = self._background if self._background is not None else 0

        # Reuse control knowledge from a prior level before spending any probe
        # actions. Controls don't change between levels, so if a plan can be
        # built straight away from the carried map we skip discovery entirely.
        if (
            not self._seed_attempted
            and self._pending_probe is None
            and not self._probes
            and self._known_dir_map
        ):
            self._seed_attempted = True
            if self._seed_from_known(layer, avail):
                return self._execute_step(layer, avail, latest_frame)

        if self._disc_targets is None:
            self._disc_targets = [a for a in _MOVE_ACTION_IDS if a in avail]

        # Credit the probe issued on the previous call (its "after" is now).
        if self._pending_probe is not None:
            probe = self._pending_probe
            probe["after"] = layer
            self._probes.append(probe)
            self._disc_attempts[probe["aid"]] += 1
            # Re-derive player colour + learned directions from all probes.
            self._disc_learned, player = infer_direction_map(self._probes, bg)
            if player is not None:
                self._player_color = player["color"]
            # Decide whether the just-probed action actually moved the player.
            aid = probe["aid"]
            moved = aid in self._disc_learned
            if not moved and self._player_color is not None:
                before_c = probe.get("centroid")
                after_c = player_centroid(layer, self._player_color, bg)
                if before_c is not None and after_c is not None:
                    shift = (
                        (after_c[0] - before_c[0]) ** 2
                        + (after_c[1] - before_c[1]) ** 2
                    ) ** 0.5
                    moved = shift >= _MIN_TRANSLATION_PX
            self._disc_last_probe_aid = aid
            self._disc_last_moved = moved
            self._pending_probe = None

        if self._action_count - self._level_action_base >= DISCOVERY_BUDGET:
            self._finish_discovery(layer, avail)
            if self._phase == _PHASE_EXECUTE:
                return self._execute_step(layer, avail, latest_frame)
            return self._explore_step(layer, avail, latest_frame)

        kind, aid = pick_next_probe(
            self._disc_targets,
            self._disc_learned,
            dict(self._disc_attempts),
            self._disc_last_moved,
            self._disc_last_probe_aid,
        )
        if kind == "done" or aid is None or aid not in avail:
            self._finish_discovery(layer, avail)
            if self._phase == _PHASE_EXECUTE:
                return self._execute_step(layer, avail, latest_frame)
            return self._explore_step(layer, avail, latest_frame)

        if kind == "recenter":
            # A relocation move, not a probe: don't buffer it as a vector probe.
            self._disc_last_probe_aid = None
            self._disc_last_moved = False
            return self._emit(GameAction.from_id(aid))

        before_c = (
            player_centroid(layer, self._player_color, bg)
            if self._player_color is not None
            else None
        )
        self._pending_probe = {"aid": aid, "before": layer, "centroid": before_c}
        return self._emit(GameAction.from_id(aid))

    def _finish_discovery(self, layer: np.ndarray, avail: list[int]) -> None:
        """Build the direction map, then choose the next phase.

        Prefer the centroid-measured ``_disc_learned`` map (robust to blocked
        probes via recentering); fall back to nearest-twin inference only when
        centroid tracking learned nothing. We require a *planable* path to a
        goal (BFS returns a non-empty action list) before committing to the
        EXECUTE phase. Execution itself is closed-loop (re-planned each step),
        so we do not store the path here.
        """
        # _disc_learned + _player_color were re-derived after each probe by
        # infer_direction_map during stepping; commit them as the dir map.
        self._dir_map = dict(self._disc_learned)

        # Derive the open-edge (corridor) colour from probe midpoints. When the
        # player traversed a maze whose nodes render as wall colour, this is the
        # only reliable walkability signal (the tu93-class interleaved pitch).
        if self._player_color is not None:
            bg = self._background if self._background is not None else 0
            self._corridor_color = corridor_color_from_probes(
                self._probes, self._player_color, bg
            )

        # Optional LLM goal/strategy hypothesis — called ONCE here, at the end
        # of discovery (never per action). Used to override the deterministic
        # goal-cell colour; any error falls back to the pure path.
        self._maybe_hypothesize(layer, avail)

        # Persist the learned controls at game scope so later levels can skip
        # the probe sweep (controls are level-invariant; only layout changes).
        if self._dir_map and self._player_color is not None:
            self._known_dir_map = dict(self._dir_map)
            self._known_player_color = self._player_color
            self._known_corridor_color = self._corridor_color

        plan = self._try_build_plan(layer, avail)
        if plan:
            self._phase = _PHASE_EXECUTE
            self._last_player_cell = None
            self._stuck_steps = 0
        elif self._init_pattern(layer, avail):
            self._phase = _PHASE_PATTERN
        else:
            self._phase = _PHASE_EXPLORE

    def _seed_from_known(self, layer: np.ndarray, avail: list[int]) -> bool:
        """Seed this level from carried control knowledge; arm EXECUTE if usable.

        Controls (action -> shift map, player colour, corridor colour) learned
        on an earlier level are reapplied to the new layout. When the player
        colour is present and a shortest path to the goal can be planned right
        away, the agent enters EXECUTE having spent ZERO probe actions — both an
        efficiency win and, in step-budgeted / fall-off games (tu93), a safety
        win (no probe moves displacing the player before planning). Returns
        False (leaving level state clean for normal probing) when the carried
        map does not apply to the new layout.
        """
        if not self._known_dir_map or self._known_player_color is None:
            return False
        present = set(np.unique(layer).tolist()) if layer.size else set()
        if self._known_player_color not in present:
            return False
        self._dir_map = dict(self._known_dir_map)
        self._player_color = self._known_player_color
        self._corridor_color = self._known_corridor_color
        plan = self._try_build_plan(layer, avail)
        if plan:
            self._phase = _PHASE_EXECUTE
            self._last_player_cell = None
            self._stuck_steps = 0
            return True
        # Carried map could not plan on this layout → reset and probe normally.
        self._dir_map = {}
        self._player_color = None
        self._corridor_color = None
        return False

    def _ensure_llm(self):
        """Lazily load the LLM backend once; None when unavailable.

        Loaded on first discovery, not at construction, so the no-LLM test
        harness and the pure deterministic path never require Ollama / a GGUF.
        Any import/connection failure disables the layer for the rest of the
        run (``_use_llm`` cleared) rather than crashing the agent.
        """
        if self._llm_loaded:
            return self._llm
        self._llm_loaded = True
        try:
            from admorphiq.llm import load_candidate

            self._llm = load_candidate(self._llm_candidate)
        except Exception:
            self._llm = None
            self._use_llm = False
        return self._llm

    def _maybe_hypothesize(self, layer: np.ndarray, avail: list[int]) -> None:
        """Call the LLM once for a goal hypothesis; record + apply target_color.

        Builds the compact symbolic state, asks the LLM, and stores the parsed
        hypothesis on ``self.last_hypothesis``. The ``target_color`` (when it
        names a colour actually present in the frame) overrides the
        deterministic rarest-colour goal heuristic. Any LLM/timeout error
        leaves the deterministic path fully intact.
        """
        if not self._use_llm:
            return
        llm = self._ensure_llm()
        if llm is None:
            return
        from admorphiq.llm_reasoner import build_symbolic_state, hypothesize

        bg = self._background if self._background is not None else 0
        try:
            state_text = build_symbolic_state(
                layer, self._probes, avail, self._dir_map, self._player_color
            )
            hyp = hypothesize(state_text, llm)
        except Exception:
            return
        self.last_hypothesis = hyp
        tc = hyp.get("target_color")
        if isinstance(tc, int) and not isinstance(tc, bool):
            present = set(np.unique(layer).tolist()) if layer.size else set()
            if tc in present and tc != bg and tc != self._player_color:
                self._llm_target_color = tc

    def _try_build_plan(self, layer: np.ndarray, avail: list[int]) -> list[int] | None:
        """Grid-BFS a shortest path from player to goal. None if not possible."""
        if not self._dir_map or self._player_color is None:
            return None
        bg = self._background if self._background is not None else 0
        cell = _step_cell_size(self._dir_map)

        # Locate the player component in the CURRENT frame.
        player_comps = [
            c
            for c in connected_components(layer, bg)
            if c["color"] == self._player_color and c["size"] <= _MAX_PLAYER_SIZE
        ]
        if not player_comps:
            return None
        player = max(player_comps, key=lambda c: c["size"])

        # Direction map quantised to unit grid steps (one cell per move).
        step_dirs: dict[int, tuple[int, int]] = {}
        for aid in avail:
            if aid not in self._dir_map:
                continue
            dx, dy = self._dir_map[aid]
            ucol = _unit(dx)
            urow = _unit(dy)
            if ucol == 0 and urow == 0:
                continue
            step_dirs[aid] = (ucol, urow)
        if not step_dirs:
            return None

        # Preferred model: edge-walkable node grid keyed on the corridor colour.
        # This is the only model that navigates interleaved-pitch mazes where a
        # node renders as wall colour but its connecting edge is the open
        # corridor (verified on tu93). Falls back to the node-dominant model
        # when no corridor colour was observed.
        if self._corridor_color is not None:
            goal_px = goal_centroid_px(
                layer, self._player_color, bg, target_color=self._llm_target_color
            )
            if goal_px is not None:
                edge_plan = edge_grid_bfs(
                    layer,
                    (player["cx"], player["cy"]),
                    cell,
                    goal_px,
                    step_dirs,
                    self._corridor_color,
                    self._player_color,
                    bg,
                )
                if edge_plan is not None:
                    return edge_plan

        goal = pick_goal_cell(
            layer, cell, self._player_color, bg, target_color=self._llm_target_color
        )
        if goal is None:
            return None

        floor_colors = floor_colors_from_probes(self._probes, self._player_color, bg)
        walkable, _ = frame_to_cells(
            layer, cell, self._player_color, bg, floor_colors=floor_colors
        )
        if walkable.size == 0:
            return None
        gh, gw = walkable.shape
        start = (
            max(0, min(gh - 1, int(round(player["cy"])) // cell)),
            max(0, min(gw - 1, int(round(player["cx"])) // cell)),
        )
        # The goal marker cell may itself be flagged non-walkable (it is a
        # coloured object); force it passable so BFS can terminate there.
        gh, gw = walkable.shape
        if 0 <= goal[0] < gh and 0 <= goal[1] < gw:
            walkable[goal[0], goal[1]] = True

        return grid_bfs(walkable, start, goal, step_dirs)

    # ── pattern-match primitive (paint / GF(2) toggle) ───────────────────────

    def _init_pattern(self, layer: np.ndarray, avail: list[int]) -> bool:
        """Dispatch a pattern-match plan when a detector fires. Additive hook.

        Tried only after the navigation plan failed (no player/goal). Prefers
        paint (a congruent reference+editable pair is a strong, specific signal)
        over toggle. For toggle we only stage the candidate cells here; the
        stencil is measured interactively in :meth:`_pattern_step` via a
        self-inverse click sweep. Returns True when a plan was staged.
        """
        from admorphiq.primitives.pattern_match import (
            detect_paint_task,
            detect_toggle_task,
            plan_paint,
        )

        if 6 in avail:
            paint = detect_paint_task(layer, self._probes)
            if paint is not None:
                queue = plan_paint(paint, layer)
                if queue:
                    self._pat_kind = "paint"
                    self._pat_queue = queue
                    return True
            tog = detect_toggle_task(layer, self._probes)
            if tog is not None and len(tog["cells"]) >= 2:
                self._pat_kind = "toggle"
                self._pat_cells = tog["cells"][:_PATTERN_TOGGLE_PROBE_CAP]
                self._pat_sub = "probe"
                self._pat_j = 0
                self._pat_click_probes = []
                return True
        return False

    def _pattern_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Drive the staged pattern plan one action per call.

        * paint — pop the precomputed ``(action_id, x, y)`` click queue.
        * toggle — interactive stencil measurement (click cell j, observe the
          flip, click again to undo — clicks are self-inverse so the base state
          is restored), then GF(2)-solve for the most-homogeneous target and
          execute only the solution-subset clicks.
        When the plan is exhausted without a win, fall back to cheap-explore.
        """
        if 6 not in avail:
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)

        if self._pat_kind == "paint":
            return self._pattern_paint_step(layer, avail, latest_frame)
        if self._pat_kind == "toggle":
            return self._pattern_toggle_step(layer, avail, latest_frame)
        self._phase = _PHASE_EXPLORE
        return self._explore_step(layer, avail, latest_frame)

    def _pattern_paint_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        if not self._pat_queue:
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)
        _aid, x, y = self._pat_queue.pop(0)
        return self._emit_click(x, y)

    def _pattern_toggle_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        from admorphiq.primitives.pattern_match import build_stencil, plan_toggle

        cells = self._pat_cells
        if self._pat_sub == "probe":
            if self._pat_j >= len(cells):
                # Measurement complete → solve and stage the solution clicks.
                stencil = build_stencil(cells, self._pat_click_probes)
                self._pat_queue = [
                    (6, x, y) for (x, y) in plan_toggle(cells, stencil)
                ]
                self._pat_sub = "execute"
                return self._pattern_toggle_step(layer, avail, latest_frame)
            self._pat_before = layer.copy()
            self._pat_sub = "undo"
            cx, cy = cells[self._pat_j]
            return self._emit_click(cx, cy)
        if self._pat_sub == "undo":
            cx, cy = cells[self._pat_j]
            self._pat_click_probes.append(
                {"x": cx, "y": cy, "before": self._pat_before, "after": layer.copy()}
            )
            self._pat_j += 1
            self._pat_sub = "probe"
            return self._emit_click(cx, cy)  # self-inverse: restore base state
        # execute
        if self._pat_queue:
            _aid, x, y = self._pat_queue.pop(0)
            return self._emit_click(x, y)
        self._phase = _PHASE_EXPLORE
        return self._explore_step(layer, avail, latest_frame)

    # ── execute phase (closed-loop) ──────────────────────────────────────────

    def _execute_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Re-plan from the live frame and emit the first action of the path.

        Closed-loop execution is robust to abstraction errors (wrong cell
        pitch, mislabelled walls): each step re-locates the player and
        re-runs BFS toward the goal, so a blocked or surprising move
        self-corrects on the next call instead of drifting open-loop. A
        stuck-counter bails to cheap-explore when the player stops making
        progress (the abstraction is too wrong to navigate).
        """
        from arcengine import GameAction

        cur_cell = self._current_player_cell(layer)
        if cur_cell is not None and cur_cell == self._last_player_cell:
            self._stuck_steps += 1
        else:
            self._stuck_steps = 0
        self._last_player_cell = cur_cell

        if self._stuck_steps >= _STUCK_LIMIT:
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)

        plan = self._try_build_plan(layer, avail)
        if not plan:
            # No path (reached goal cell already, or unreachable) → explore.
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)
        aid = plan[0]
        if aid not in avail:
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)
        return self._emit(GameAction.from_id(aid))

    def _current_player_cell(self, layer: np.ndarray) -> tuple[int, int] | None:
        """Grid cell of the player in the live frame (for the stuck-counter)."""
        if self._player_color is None or not self._dir_map:
            return None
        bg = self._background if self._background is not None else 0
        cell = _step_cell_size(self._dir_map)
        comps = [
            c
            for c in connected_components(layer, bg)
            if c["color"] == self._player_color and c["size"] <= _MAX_PLAYER_SIZE
        ]
        if not comps:
            return None
        p = max(comps, key=lambda c: c["size"])
        return (int(round(p["cy"])) // cell, int(round(p["cx"])) // cell)

    # ── cheap-explore fallback ───────────────────────────────────────────────

    def _explore_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Disciplined cheap explore: prefer change-producing actions, click rare."""
        from arcengine import GameAction

        sig = layer.tobytes()
        if self._explore_pending is not None and self._explore_pending != 0:
            self._explore_tries[self._explore_pending] += 1
            if sig != self._explore_last_sig:
                self._explore_changes[self._explore_pending] += 1
        self._explore_last_sig = sig
        self._explore_pending = None

        if 6 in avail:
            target = self._rare_centroid(layer)
            if target is not None:
                return self._emit_click(*target)

        simple = [a for a in _MOVE_ACTION_IDS if a in avail]
        if simple:
            choice = self._pick_explore_simple(simple)
            self._explore_pending = choice
            return self._emit(GameAction.from_id(choice))

        if 6 in avail:
            return self._emit_click(32, 32)
        return self._emit(GameAction.RESET)

    def _pick_explore_simple(self, simple: list[int]) -> int:
        under = [a for a in simple if self._explore_tries[a] < 1]
        if under:
            return under[0]
        if self._rng.random() < _EXPLORE_EPSILON:
            return self._rng.choice(simple)
        rates = {a: self._explore_rate(a) for a in simple}
        best = max(rates.values())
        useful = [a for a in simple if rates[a] >= 0.8 * best] if best > 0 else simple
        choice = useful[self._explore_cursor % len(useful)]
        self._explore_cursor += 1
        return choice

    def _explore_rate(self, aid: int) -> float:
        t = self._explore_tries[aid]
        return self._explore_changes[aid] / t if t else 0.0

    def _rare_centroid(self, layer: np.ndarray) -> tuple[int, int] | None:
        if layer.size == 0:
            return None
        bg = self._background if self._background is not None else int(layer[0, 0])
        comps = [c for c in connected_components(layer, bg) if c["color"] != bg]
        if not comps:
            return None
        color_area: Counter[int] = Counter()
        for c in comps:
            color_area[c["color"]] += c["size"]
        rare = min(color_area, key=lambda k: color_area[k])
        rc = [c for c in comps if c["color"] == rare]
        target = max(rc, key=lambda c: c["size"])
        return (int(round(target["cx"])), int(round(target["cy"])))

    # ── action emission ──────────────────────────────────────────────────────

    def _emit(self, action):
        self._action_count += 1
        return action

    def _emit_click(self, x: int, y: int):
        from arcengine import GameAction

        action = GameAction.ACTION6
        action.set_data({"x": int(max(0, min(63, x))), "y": int(max(0, min(63, y)))})
        self._action_count += 1
        return action


# ── small obs-shape helpers ──────────────────────────────────────────────────


def _unit(v: int) -> int:
    return (v > 0) - (v < 0)


def _state_name(frame) -> str:
    state = getattr(frame, "state", None)
    if state is None:
        return "PLAYING"
    return getattr(state, "name", str(state))


def _avail_ids(frame) -> list[int]:
    raw = getattr(frame, "available_actions", None) or []
    out: list[int] = []
    for a in raw:
        aid = a if isinstance(a, int) else getattr(a, "value", getattr(a, "id", None))
        if aid is not None and int(aid) != 0:
            out.append(int(aid))
    return out
