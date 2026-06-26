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

import itertools
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
# Consecutive EXECUTE steps with no player-cell change before bailing to
# cheap-explore (the abstract model is too wrong to navigate).
_STUCK_LIMIT = 4
# Bail-fast: max actions a committed plan may run on the CURRENT level WITHOUT
# completing a level before it is abandoned for cheap-explore. The competition
# metric gives NO partial credit, so a plan that has not cleared the level in
# far more than the human action budget (L1 baselines ~16-42) is the wrong plan
# — continuing only burns the action budget that disciplined exploration could
# instead spend stumbling into an easy level. Navigation (EXECUTE) clears fast
# or never, so its cap is tight; the pattern-solve (PATTERN) legitimately spends
# actions probing a toggle stencil (~55 actions to clear ft09 L1), so its cap is
# looser, but both are far below the 600-action hard cap that the agent used to
# squander on a single dead plan (e.g. su15: 600 -> 0).
_EXECUTE_BAIL_LIMIT = 50
_PATTERN_BAIL_LIMIT = 120
# Cheap-explore: a candidate (move or click) tried this many times that NEVER
# once changed the frame is treated as dead and dropped from the rotation, so
# the budget is spent on actions that actually do something.
_EXPLORE_DEAD_TRIES = 3
# Coarse click-grid stride (px) for ACTION6 exploration: clicks are scattered on
# a regular lattice so a responsive cell anywhere on the board is eventually hit.
_EXPLORE_GRID_STRIDE = 16
# Max rare-colour cluster centroids offered as click targets per explore build.
_EXPLORE_MAX_CLUSTERS = 16
# Bounded sequence-search (extends single-action explore): single actions can
# only ever stumble a level that completes on ONE input. Many ARC-AGI-3 levels
# instead complete on a short ACTION SEQUENCE (press A2 then A4, a 3-4 action
# combo, sustained pushing, or an alternating pattern). After the single-action
# sweep has revealed which actions/clicks actually move the frame, we run a
# bounded search over short combos of ONLY those frame-changers (no-op actions
# are pruned at construction, so the budget is spent on inputs that do
# something). The caps below keep the search far below the 600-action game
# budget so it stays efficient and still leaves room for the rotate fallback.
_SEQ_REPEAT_LENGTHS: tuple[int, ...] = (2, 4, 8)
_SEQ_COMBO_KS: tuple[int, ...] = (2, 3, 4)
# Alternating ABAB / ABABABAB lengths (rhythm + short zigzag traversal). A
# single ABAB cannot traverse a zigzag corridor; the longer block can.
_SEQ_ALT_LENGTHS: tuple[int, ...] = (4, 8)
_SEQ_MAX_PER_K = 16
_SEQ_MAX_TOTAL_ACTIONS = 256
# Max distinct click targets (responsive / rare-cluster cells, busiest first)
# admitted as sequence tokens alongside the frame-changing move actions.
_SEQ_MAX_CLICK_TOKENS = 3


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


def select_explore_action(
    candidates: list[tuple],
    tries: dict[tuple, int],
    changes: dict[tuple, int],
    cursor: int,
) -> tuple[tuple | None, int]:
    """Pick the next exploration candidate from observed try/change history.

    ``candidates`` is an ordered list of opaque descriptors (the agent uses
    ``("m", aid)`` for a simple move and ``("c", x, y)`` for an ACTION6 click).
    ``tries``/``changes`` count how often each descriptor was issued and how
    often issuing it changed the frame. ``cursor`` is a rotating counter the
    caller persists across calls. Returns ``(descriptor, new_cursor)`` (or
    ``(None, cursor)`` when there is nothing to do).

    Policy — a smarter-than-random explorer that maximises the chance of
    stumbling the winning interaction within budget:
      1. Drop *dead* candidates (tried ``_EXPLORE_DEAD_TRIES`` times, never
         changed the frame) so no-op spots are not re-clicked forever.
      2. Try every still-untried candidate first (breadth — cover all actions
         and all click targets before repeating any).
      3. Once everything has been tried, ROTATE but BIAS toward candidates that
         have changed the frame (2 of every 3 picks come from the changer set),
         while still revisiting the full pool periodically so a delayed-effect
         cell is not abandoned.

    Pure / env-free so the selection logic is unit-testable without an env.
    """
    if not candidates:
        return None, cursor
    live = [
        d
        for d in candidates
        if not (tries.get(d, 0) >= _EXPLORE_DEAD_TRIES and changes.get(d, 0) == 0)
    ]
    pool = live or candidates
    untried = [d for d in pool if tries.get(d, 0) == 0]
    if untried:
        return untried[0], cursor
    cursor += 1
    changers = [d for d in pool if changes.get(d, 0) > 0]
    if changers and cursor % 3 != 0:
        return changers[cursor % len(changers)], cursor
    return pool[cursor % len(pool)], cursor


def build_action_sequences(
    changers: list,
    *,
    repeat_lengths: tuple[int, ...] = _SEQ_REPEAT_LENGTHS,
    combo_ks: tuple[int, ...] = _SEQ_COMBO_KS,
    alt_lengths: tuple[int, ...] = _SEQ_ALT_LENGTHS,
    max_per_k: int = _SEQ_MAX_PER_K,
    max_total_actions: int = _SEQ_MAX_TOTAL_ACTIONS,
) -> list[tuple]:
    """Bounded set of short action SEQUENCES built from frame-changing tokens.

    ``changers`` is an ordered list of opaque, hashable tokens — the agent uses
    a move action id (``int``) or a click descriptor (``("c", x, y)``) — that
    were each individually observed to change the frame. Single-action
    exploration can only stumble a level that completes on one input; this
    generates the short multi-action combos that levels needing a SEQUENCE
    require, while spending the budget only on inputs that actually do
    something (no-op tokens are excluded by the caller, so every emitted token
    is a real changer — branch-level no-op pruning).

    Output ordering encodes priority (cheapest / most-common-mechanic first):

      1. **Sustained repeats** — ``(a,)*n`` for each token and each ``n`` in
         ``repeat_lengths`` (games that need held / repeated pushing).
      2. **Distinct-token permutations** for each ``k`` in ``combo_ks`` (k=2
         ordered pairs "A then B", k=3, k=4 combos), capped at ``max_per_k``
         per ``k`` so the count cannot explode with the token set.
      3. **Alternating ``(a, b)`` runs** of each length in ``alt_lengths`` for
         each unordered pair (rhythm / toggle patterns, and short zigzag
         traversal — a plain permutation can't express these because it has no
         repeats).

    Sequences are de-duplicated preserving first-seen order, and the running
    total of emitted actions is capped at ``max_total_actions`` so the search
    stays far below the game budget. Pure / env-free → unit-testable.
    """
    uniq = list(dict.fromkeys(changers))  # dedup, preserve order
    if not uniq:
        return []

    seqs: list[tuple] = []
    seen: set[tuple] = set()
    total = 0

    def _add(seq: tuple) -> None:
        nonlocal total
        if not seq or seq in seen:
            return
        if total + len(seq) > max_total_actions:
            return
        seen.add(seq)
        seqs.append(seq)
        total += len(seq)

    # 1) Sustained repeats.
    for n in repeat_lengths:
        for a in uniq:
            _add((a,) * n)

    # 2) Distinct-token permutations per k (k=2 → ordered pairs, then k=3, k=4).
    for k in combo_ks:
        if k < 2 or k > len(uniq):
            continue
        count = 0
        for combo in itertools.permutations(uniq, k):
            before = len(seqs)
            _add(combo)
            if len(seqs) > before:
                count += 1
                if count >= max_per_k:
                    break

    # 3) Alternating (a, b) runs of each requested length, shortest first.
    for length in alt_lengths:
        reps = max(1, length // 2)
        count = 0
        for i, a in enumerate(uniq):
            for b in uniq[i + 1 :]:
                before = len(seqs)
                _add((a, b) * reps)
                if len(seqs) > before:
                    count += 1
                    if count >= max_per_k:
                        break
            if count >= max_per_k:
                break

    return seqs


# ── Agent FSM ────────────────────────────────────────────────────────────────

_PHASE_DISCOVERY = "discovery"
_PHASE_EXECUTE = "execute"
_PHASE_EXPLORE = "explore"
# Pattern-match primitive (paint-to-match / GF(2) toggle). Dispatched after
# discovery when no navigation plan exists but a pattern detector fires.
_PHASE_PATTERN = "pattern"
# Max candidate cells to probe when measuring a toggle stencil. Interactive
# buttons are indistinguishable from decorative same-colour tiles without
# probing, so the candidate set is a superset filtered by measurement.
_PATTERN_TOGGLE_PROBE_CAP = 48
# A probe click "toggles" a cell when it flips a compact, LOCAL region: at
# least 1 and at most this many pixels change. Larger global changes are
# animations / HUD flashes, not an independent cell toggle.
_TOGGLE_DIFF_MAX = 120
# The flipped region's centroid must be within this many px of the clicked
# point to count as that cell's own toggle (rejects far-away HUD/animation).
_TOGGLE_LOCALITY_PX = 8.0
# Minimum LLM ``confidence`` for the agent to act on the LLM's primitive
# SELECTION. The LLM is consulted ONLY after the deterministic pipeline has
# already failed to build a plan (see :meth:`GeneralAgent._finish_discovery`),
# so it competes with cheap-explore, never with a working deterministic plan.
# Below this threshold the LLM pick is discarded and the agent falls through to
# cheap-explore — so a hesitant or malformed hypothesis can never derail the
# proven default path.
_LLM_MIN_CONFIDENCE = 0.5


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
        llm_candidate: str = "qwen_3_8b_q4",
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
        # Bail-fast watchdog: global action count when the current committed plan
        # (EXECUTE / PATTERN) began. A plan that has run longer than its cap on
        # this level without a level-up is abandoned for cheap-explore.
        self._plan_commit_action = getattr(self, "_action_count", 0)
        # Pattern-match primitive bookkeeping (paint / GF(2) toggle).
        self._pat_kind: str | None = None
        self._pat_queue: list[tuple[int, int, int]] = []
        self._pat_cells: list[tuple[int, int]] = []
        self._pat_sub: str | None = None
        self._pat_j: int = 0
        self._pat_before: np.ndarray | None = None
        self._pat_click_probes: list[dict] = []
        # Interactive toggle-solve bookkeeping.
        self._pat_base_layer: np.ndarray | None = None
        self._pat_toggled: list[tuple[int, int]] = []
        self._pat_candidates: list[list[tuple[int, int]]] = []
        self._pat_cand_k: int = 0
        self._pat_applied: set[tuple[int, int]] = set()
        self._pat_delta: list[tuple[int, int]] = []
        # Cheap-explore fallback bookkeeping (keyed by candidate descriptor so
        # try/change stats survive a candidate-list rebuild as the frame evolves).
        self._xp_tries: Counter[tuple] = Counter()
        self._xp_changes: Counter[tuple] = Counter()
        self._xp_last_desc: tuple | None = None
        self._xp_last_sig: bytes = b""
        self._xp_cursor = 0
        self._xp_cluster_sig: bytes = b""
        self._xp_cluster_cands: list[tuple] = []
        # Bounded sequence-search bookkeeping (runs after the single-action
        # sweep identifies the frame-changers). ``_seq_sweep_queue`` is a
        # one-shot snapshot swept once to learn the changers; once
        # ``_seq_built`` flips, the combos in ``_seq_list`` are emitted one
        # token per call. Reset on level-up like all other explore state.
        self._seq_sweep_queue: list[tuple] | None = None
        self._seq_built = False
        self._seq_list: list[tuple] = []
        self._seq_i = 0
        self._seq_pos = 0

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
        """Build the direction map, then choose the next phase — DETERMINISTIC FIRST.

        Prefer the centroid-measured ``_disc_learned`` map (robust to blocked
        probes via recentering); fall back to nearest-twin inference only when
        centroid tracking learned nothing. We require a *planable* path to a
        goal (BFS returns a non-empty action list) before committing to the
        EXECUTE phase. Execution itself is closed-loop (re-planned each step),
        so we do not store the path here.

        Selection order (the regression guarantee):

          1. **Deterministic pipeline** — nav plan, then pattern detectors, run
             with ZERO LLM influence (``_llm_target_color`` is still None, so
             goal selection is pure). If a deterministic primitive yields a
             valid plan it is committed and the LLM is NEVER consulted. This is
             what keeps the proven clears (tu93/ft09/lp85/tn36): the LLM cannot
             override a working deterministic plan. R6 inverted this order and
             a wrong target_color hypothesis broke tu93.
          2. **LLM fallback** — reached ONLY when the deterministic pipeline
             produced no plan (the case that would otherwise drop straight to
             cheap-explore). Here the LLM competes with EXPLORE, never with a
             working plan: it may name a buildable primitive (nav with a goal
             colour, toggle, paint) that gets a bounded shot, bailing to explore
             on no progress via the EXECUTE/PATTERN watchdog.
          3. **Cheap-explore** — the final fallback.
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

        # Persist the learned controls at game scope so later levels can skip
        # the probe sweep (controls are level-invariant; only layout changes).
        if self._dir_map and self._player_color is not None:
            self._known_dir_map = dict(self._dir_map)
            self._known_player_color = self._player_color
            self._known_corridor_color = self._corridor_color

        # 1) Deterministic-first. No LLM influence on goal selection here.
        plan = self._try_build_plan(layer, avail)
        if plan:
            self._phase = _PHASE_EXECUTE
            self._last_player_cell = None
            self._stuck_steps = 0
            self._plan_commit_action = self._action_count
            return
        if self._init_pattern(layer, avail):
            self._phase = _PHASE_PATTERN
            self._plan_commit_action = self._action_count
            return

        # 2) LLM fallback — only when the deterministic pipeline found nothing.
        # The hypothesis call is ONLY made here, so games the deterministic path
        # already clears never spend an LLM call and can never be overridden.
        if self._use_llm:
            self._maybe_hypothesize(layer, avail)
            if self._dispatch_llm_primitive(layer, avail):
                return

        # 3) Cheap-explore fallback.
        self._phase = _PHASE_EXPLORE

    def _dispatch_llm_primitive(self, layer: np.ndarray, avail: list[int]) -> bool:
        """Commit the phase to the LLM's SELECTED primitive; False to fall back.

        Reads ``self.last_hypothesis`` (set by :meth:`_maybe_hypothesize`) and
        maps the enum ``primitive`` field to the agent's actual dispatch:

          * ``nav``    -> grid-BFS navigation plan (EXECUTE), using the LLM's
            ``target_color`` goal when it named one (already applied upstream);
          * ``toggle`` -> interactive GF(2) toggle solver (PATTERN);
          * ``paint``  -> paint-to-match solver (PATTERN);
          * ``explore``-> disciplined cheap-explore (EXPLORE).

        The pick is honoured ONLY when ``confidence >= _LLM_MIN_CONFIDENCE`` and
        the primitive is one of the closed enum names; a nav/toggle/paint pick
        additionally requires the corresponding plan/detector to be stageable on
        the current frame, else this returns False and the caller falls through
        to cheap-explore. ``explore`` is always stageable. Never raises.

        Called by :meth:`_finish_discovery` ONLY when the deterministic pipeline
        produced no plan, so this dispatch can only ADD a clear on a game that
        would otherwise explore — it can never override a working deterministic
        plan.
        """
        hyp = self.last_hypothesis
        if not hyp:
            return False
        primitive = hyp.get("primitive")
        confidence = hyp.get("confidence")
        if primitive not in ("nav", "toggle", "paint", "explore"):
            return False
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            return False
        if confidence < _LLM_MIN_CONFIDENCE:
            return False

        if primitive == "nav":
            if self._try_build_plan(layer, avail):
                self._phase = _PHASE_EXECUTE
                self._last_player_cell = None
                self._stuck_steps = 0
                self._plan_commit_action = self._action_count
                return True
            return False
        if primitive == "toggle":
            if 6 in avail and self._stage_toggle(layer):
                self._phase = _PHASE_PATTERN
                self._plan_commit_action = self._action_count
                return True
            return False
        if primitive == "paint":
            if 6 in avail and self._stage_paint(layer):
                self._phase = _PHASE_PATTERN
                self._plan_commit_action = self._action_count
                return True
            return False
        # explore — always available as the disciplined fallback.
        self._phase = _PHASE_EXPLORE
        return True

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
            self._plan_commit_action = self._action_count
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
        if 6 not in avail:
            return False
        return self._stage_paint(layer) or self._stage_toggle(layer)

    def _stage_paint(self, layer: np.ndarray) -> bool:
        """Stage a paint-to-match plan if a congruent reference/canvas pair fires.

        Returns True (and arms ``_pat_kind="paint"`` + the click queue) when the
        paint detector finds a copyable pattern; False when no paint signature is
        present. Split out of :meth:`_init_pattern` so the LLM selector can
        request the paint primitive directly.
        """
        from admorphiq.primitives.pattern_match import detect_paint_task, plan_paint

        paint = detect_paint_task(layer, self._probes)
        if paint is not None:
            queue = plan_paint(paint, layer)
            if queue:
                self._pat_kind = "paint"
                self._pat_queue = queue
                return True
        return False

    def _stage_toggle(self, layer: np.ndarray) -> bool:
        """Stage the interactive GF(2) toggle solve if a clickable lattice fires.

        Returns True (and arms ``_pat_kind="toggle"`` plus the candidate cells
        for the interactive stencil sweep) when at least two grid cells are
        detected; False otherwise. Split out of :meth:`_init_pattern` so the LLM
        selector can request the toggle primitive directly.
        """
        from admorphiq.primitives.pattern_match import detect_toggle_task

        tog = detect_toggle_task(layer, self._probes)
        if tog is not None and len(tog["cells"]) >= 2:
            self._pat_kind = "toggle"
            self._pat_cells = tog["cells"][:_PATTERN_TOGGLE_PROBE_CAP]
            self._pat_sub = "probe"
            self._pat_j = 0
            self._pat_click_probes = []
            self._pat_base_layer = layer.copy()
            self._pat_toggled = []
            self._pat_candidates = []
            self._pat_cand_k = 0
            self._pat_applied = set()
            self._pat_delta = []
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

        # Bail-fast: cap how long the pattern-solve may run on this level without
        # a level-up. The toggle/paint solve legitimately spends actions probing,
        # but past this cap it is grinding a wrong hypothesis and should yield the
        # remaining budget to exploration.
        if self._action_count - self._plan_commit_action >= _PATTERN_BAIL_LIMIT:
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
        """Interactive GF(2) toggle solve, driven one action per call.

        Two sub-phases:

        * MEASURE (``probe`` / ``observe``) — click each candidate cell; on the
          next frame, classify the change. A compact LOCAL flip near the click
          marks a real interactive cell (its self-inverse undo restores the base
          state); a far-away / global change is HUD/animation and is skipped
          with no undo (saves the limited move budget). The kept cells are the
          board's actual toggle buttons.
        * SOLVE (``solve``) — derive candidate target flip-sets (indicator
          polarities first, then all-on, then the homogeneity GF(2) solve) and
          execute them one at a time via a reset-free delta-chain (clicks are
          self-inverse, so moving from one candidate to the next clicks only the
          symmetric difference). A cleared level is observed by the harness as a
          level-up (state reset); an exhausted candidate that did not clear
          advances to the next. No game id / title — pure observable signature.
        """
        cells = self._pat_cells
        sub = self._pat_sub

        if sub == "probe":
            if self._pat_j >= len(cells):
                return self._begin_toggle_solve(layer, avail, latest_frame)
            self._pat_before = layer.copy()
            self._pat_sub = "observe"
            cx, cy = cells[self._pat_j]
            return self._emit_click(cx, cy)

        if sub == "observe":
            cx, cy = cells[self._pat_j]
            before = self._pat_before
            if _is_local_toggle(before, layer, cx, cy):
                self._pat_click_probes.append(
                    {"x": cx, "y": cy, "before": before, "after": layer.copy()}
                )
                self._pat_toggled.append((cx, cy))
                self._pat_j += 1
                self._pat_sub = "probe"
                return self._emit_click(cx, cy)  # self-inverse: restore base
            # Non-toggle (no change or far HUD/animation): no undo, probe next.
            self._pat_j += 1
            self._pat_sub = "probe"
            return self._pattern_toggle_step(layer, avail, latest_frame)

        if sub == "solve":
            return self._toggle_solve_step(layer, avail, latest_frame)

        self._phase = _PHASE_EXPLORE
        return self._explore_step(layer, avail, latest_frame)

    def _begin_toggle_solve(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Build the ordered candidate flip-sets and enter the SOLVE sub-phase."""
        from admorphiq.primitives.pattern_match import (
            build_stencil,
            indicator_flip_sets,
            plan_toggle,
        )

        toggle = self._pat_toggled
        base = self._pat_base_layer if self._pat_base_layer is not None else layer
        candidates: list[list[tuple[int, int]]] = []

        def _add(flip: list[tuple[int, int]]) -> None:
            if flip and flip not in candidates:
                candidates.append(list(flip))

        # 1) Indicator-defined target patterns (both polarities), smallest first.
        for flip in indicator_flip_sets(base, toggle):
            _add(flip)
        # 2) Flip every cell (the simplest non-trivial uniform target).
        _add(list(toggle))
        # 3) Homogeneity GF(2) solve — the classic "all cells equal" lights-out.
        stencil = build_stencil(toggle, self._pat_click_probes) if self._pat_click_probes else None
        if stencil is not None:
            _add(plan_toggle(toggle, stencil))

        if not candidates:
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)

        self._pat_candidates = candidates
        self._pat_cand_k = 0
        self._pat_applied = set()
        self._pat_delta = sorted(candidates[0])
        self._pat_sub = "solve"
        return self._toggle_solve_step(layer, avail, latest_frame)

    def _toggle_solve_step(self, layer: np.ndarray, avail: list[int], latest_frame):
        """Emit the next delta click for the current candidate, or advance."""
        if not self._pat_delta:
            # Current candidate fully applied without a level-up → try the next.
            self._pat_cand_k += 1
            if self._pat_cand_k >= len(self._pat_candidates):
                self._phase = _PHASE_EXPLORE
                return self._explore_step(layer, avail, latest_frame)
            target = set(self._pat_candidates[self._pat_cand_k])
            self._pat_delta = sorted(target ^ self._pat_applied)
            if not self._pat_delta:
                return self._toggle_solve_step(layer, avail, latest_frame)

        cell = self._pat_delta.pop(0)
        if cell in self._pat_applied:
            self._pat_applied.discard(cell)
        else:
            self._pat_applied.add(cell)
        return self._emit_click(cell[0], cell[1])

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

        # Bail-fast: a navigation plan clears the level in a small multiple of the
        # human action count or not at all. If it has run this long without a
        # level-up, the abstraction is wrong — abandon it and explore so the rest
        # of the budget can stumble an easy level instead of wandering to 0.
        if self._action_count - self._plan_commit_action >= _EXECUTE_BAIL_LIMIT:
            self._phase = _PHASE_EXPLORE
            return self._explore_step(layer, avail, latest_frame)

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
        """Disciplined cheap explore in THREE stages — a smarter-than-random
        easy-level stumbler that also probes short action SEQUENCES.

        Every call first credits the previously-issued candidate (did its action
        change the frame?) so the changer statistics accumulate. Then:

          1. **Single-action sweep** — try each candidate (simple moves + click
             targets) once to learn which inputs actually move the frame. Levels
             that complete on ONE input are stumbled here, as in R10.
          2. **Bounded sequence search** — once the sweep is done, run short
             combos (repeats / "A then B" / k=3-4 / alternating) built ONLY from
             the observed frame-changers via :func:`build_action_sequences`.
             Levels that complete on a short SEQUENCE are stumbled here. A
             combo is abandoned the moment one of its tokens stops changing the
             frame (no-op branch pruning), and the whole search is capped well
             below the game budget.
          3. **Rotate fallback** — once the sequences are exhausted, the R10
             :func:`select_explore_action` rotation handles delayed-effect cells
             and keeps spending the remaining budget productively.

        On a level-up the harness resets this state (re-discovery), so working
        nav / toggle clears and the R10 single-action clears are all retained.
        """
        from arcengine import GameAction

        # Credit the candidate issued on the previous call against the new frame.
        sig = layer.tobytes()
        changed = self._xp_last_desc is not None and sig != self._xp_last_sig
        if self._xp_last_desc is not None:
            self._xp_tries[self._xp_last_desc] += 1
            if changed:
                self._xp_changes[self._xp_last_desc] += 1
        self._xp_last_sig = sig

        candidates = self._build_explore_candidates(layer, avail)

        # Stage 1: sweep a one-shot snapshot of the candidates once so every
        # input is observed at least once before any combo is built.
        if not self._seq_built:
            if self._seq_sweep_queue is None:
                self._seq_sweep_queue = list(candidates)
            while self._seq_sweep_queue:
                d = self._seq_sweep_queue.pop(0)
                if self._xp_tries.get(d, 0) == 0:
                    self._xp_last_desc = d
                    return self._emit_desc(d)
            # Sweep exhausted → build the bounded sequence search.
            self._build_sequence_search(avail)
            self._seq_built = True

        # Stage 2: emit the next token of the bounded sequence search.
        act = self._next_sequence_action(changed, avail)
        if act is not None:
            return act

        # Stage 3: R10 rotate fallback (delayed effects, busiest-cell bias).
        desc, self._xp_cursor = select_explore_action(
            candidates, self._xp_tries, self._xp_changes, self._xp_cursor
        )
        if desc is None:
            self._xp_last_desc = None
            if 6 in avail:
                return self._emit_click(32, 32)
            return self._emit(GameAction.RESET)
        self._xp_last_desc = desc
        return self._emit_desc(desc)

    def _build_sequence_search(self, avail: list[int]) -> None:
        """Stage the bounded sequence search from the observed frame-changers.

        Tokens are the move actions that changed the frame during the sweep
        (still available) followed by up to ``_SEQ_MAX_CLICK_TOKENS`` click
        targets that changed the frame, busiest first. With no observed changer
        the list stays empty and the explorer falls straight through to the
        rotate fallback.
        """
        move_tokens = [
            aid
            for aid in _MOVE_ACTION_IDS
            if aid in avail and self._xp_changes.get(("m", aid), 0) > 0
        ]
        click_changers = [
            d
            for d in self._xp_changes
            if d[0] == "c" and self._xp_changes.get(d, 0) > 0
        ]
        click_changers.sort(key=lambda d: -self._xp_changes[d])
        click_tokens: list[tuple] = (
            click_changers[:_SEQ_MAX_CLICK_TOKENS] if 6 in avail else []
        )
        tokens: list = list(move_tokens) + list(click_tokens)
        self._seq_list = build_action_sequences(tokens)
        self._seq_i = 0
        self._seq_pos = 0

    def _next_sequence_action(self, changed: bool, avail: list[int]):
        """Emit the next token of the current combo, or None when exhausted.

        Walks the staged ``_seq_list`` one token per call. A *homogeneous*
        combo (a sustained repeat of one token) is abandoned the moment a token
        already emitted within it failed to change the frame (``changed`` False
        with ``_seq_pos > 0``): repeating an action that just hit a wall is
        wasted budget. *Heterogeneous* combos (ordered pairs / alternating
        zigzags) are NOT pruned on a single no-op — one leg being momentarily
        wall-blocked is exactly when the other leg matters, so the combo must
        run to completion. Tokens referencing a now-unavailable action skip the
        whole combo.
        """
        while self._seq_i < len(self._seq_list):
            seq = self._seq_list[self._seq_i]
            # Prune the no-op branch only for pure-repeat combos: a sustained
            # push whose last token did nothing is dead. Mixed combos run on.
            if (
                self._seq_pos > 0
                and not changed
                and len(set(seq)) == 1
            ):
                self._seq_i += 1
                self._seq_pos = 0
                continue
            if self._seq_pos >= len(seq):
                self._seq_i += 1
                self._seq_pos = 0
                continue
            token = seq[self._seq_pos]
            desc = ("m", token) if isinstance(token, int) else token
            if (desc[0] == "m" and desc[1] not in avail) or (
                desc[0] == "c" and 6 not in avail
            ):
                # This combo is not executable in the current action set.
                self._seq_i += 1
                self._seq_pos = 0
                continue
            self._seq_pos += 1
            self._xp_last_desc = desc
            return self._emit_desc(desc)
        return None

    def _emit_desc(self, desc: tuple):
        """Emit a move (``("m", aid)``) or click (``("c", x, y)``) descriptor."""
        from arcengine import GameAction

        if desc[0] == "m":
            return self._emit(GameAction.from_id(desc[1]))
        return self._emit_click(desc[1], desc[2])

    def _build_explore_candidates(
        self, layer: np.ndarray, avail: list[int]
    ) -> list[tuple]:
        """Ordered explore candidates: simple moves + rare clusters + click grid.

        Cluster centroids are recomputed only when the frame changed since the
        last build (the clusters are otherwise identical), keeping per-action
        cost low across the 600-action budget. Descriptors are de-duplicated
        preserving order so a grid point coinciding with a centroid is offered
        once. Returns ``[("m", aid) | ("c", x, y), ...]``.
        """
        cands: list[tuple] = [("m", a) for a in _MOVE_ACTION_IDS if a in avail]
        if 6 in avail:
            sig = layer.tobytes()
            if sig != self._xp_cluster_sig or not self._xp_cluster_cands:
                self._xp_cluster_sig = sig
                self._xp_cluster_cands = self._cluster_click_cands(layer)
            cands.extend(self._xp_cluster_cands)
            for y in range(_EXPLORE_GRID_STRIDE // 2, 64, _EXPLORE_GRID_STRIDE):
                for x in range(_EXPLORE_GRID_STRIDE // 2, 64, _EXPLORE_GRID_STRIDE):
                    cands.append(("c", x, y))
        seen: set[tuple] = set()
        out: list[tuple] = []
        for d in cands:
            if d not in seen:
                seen.add(d)
                out.append(d)
        return out

    def _cluster_click_cands(self, layer: np.ndarray) -> list[tuple]:
        """Click targets at non-background cluster centroids, rarest colour first.

        Rare colours are the most likely interactive markers (buttons / goals),
        so they are offered before common ones; capped at
        ``_EXPLORE_MAX_CLUSTERS`` to keep the candidate list small.
        """
        if layer.size == 0:
            return []
        bg = self._background if self._background is not None else int(layer[0, 0])
        comps = [c for c in connected_components(layer, bg) if c["color"] != bg]
        if not comps:
            return []
        color_area: Counter[int] = Counter()
        for c in comps:
            color_area[c["color"]] += c["size"]
        # Rarest colour (fewest total cells) first, then larger clusters first.
        comps.sort(key=lambda c: (color_area[c["color"]], -c["size"]))
        out: list[tuple] = []
        for c in comps[:_EXPLORE_MAX_CLUSTERS]:
            out.append(("c", int(round(c["cx"])), int(round(c["cy"]))))
        return out

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


def _is_local_toggle(
    before: np.ndarray | None,
    after: np.ndarray,
    cx: int,
    cy: int,
    diff_max: int = _TOGGLE_DIFF_MAX,
    locality_px: float = _TOGGLE_LOCALITY_PX,
) -> bool:
    """True when clicking ``(cx, cy)`` flipped a compact region AT that cell.

    A real interactive toggle button changes a small, local block of pixels
    centred on the click. A HUD counter, progress bar or first-level animation
    instead changes pixels far from the click (or the whole frame). Requiring
    the changed region to be both small (``<= diff_max`` px) and centred within
    ``locality_px`` of the click rejects those, so the move-budgeted board is
    not polluted with phantom cells. Pure / env-free.
    """
    if before is None or before.shape != after.shape:
        return False
    changed = before != after
    n = int(np.count_nonzero(changed))
    if n < 1 or n > diff_max:
        return False
    ys, xs = np.nonzero(changed)
    mx = float(xs.mean())
    my = float(ys.mean())
    return abs(mx - cx) <= locality_px and abs(my - cy) <= locality_px


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
