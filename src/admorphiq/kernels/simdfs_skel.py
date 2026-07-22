"""Compact ``simdfs`` FAMILY SKELETON — the faithful-sim mechanics IDEA only.

R94 D5-SKEL (pre-registration frozen in ``.wiki/wiki/rounds/r94_adapter-template.md``,
"D5-SKEL PRE-REGISTRATION"). D5 confounded SIZE with FAMILY (a 75KB portal engine vs
a 6.6KB generic toggle card). This module de-confounds by expressing the SAME family
IDEA — *parse a board into movable pieces + fixed structure, learn a tiny move model
from observed clicks, then plan a short click sequence by shallow search* — in a
COMPACT card (target 5-10KB when assembled by ``source_card``).

It is written FRESH and MINIMAL, NOT extracted from the real ``admorphiq.kernels.simdfs``
engine. It is not required to reproduce sb26's conquest; per the prereg it must only be
sandbox-executable and emit SOME actions on a synthetic board (the smoke gate).

Sandbox contract (see ``tools.code_agent.run_code``): a core may use ONLY ``np``
(numpy), Python builtins, and its own bundled helpers. ``current_frame`` and each
transition's ``before``/``after`` arrive as list-of-lists grids; ``transitions`` is a
list of ``{"action", "xy": [x, y] | None, "before", "after"}`` dicts; ``act(name,
x=None, y=None)`` QUEUES an action (``"CLICK"`` with x=col, y=row).
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

# ── GAME-SPECIFIC PRIORS — RE-DERIVE from your observations ──────────────────
# The SOURCE (sb26) board's small sorted tokens are <= 6 cells and the target
# structure is larger; the shallow search assigns at most this many pieces per
# call and branches over the 3 nearest targets. On a DIFFERENT board of this
# family, RE-DERIVE the movable-vs-fixed size split from YOUR parsed regions
# before trusting any plan.
_SKEL_MOVABLE_MAX_SIZE = 6
_SKEL_SEARCH_DEPTH = 6
_SKEL_BRANCH = 3
_SKEL_NEAR = 5.0  # a click's changed cells centroid this-near the click ⇒ "to_location"


def _skel_background(frame: np.ndarray) -> int:
    """Most common colour = background (list-stack flood needs a bg to skip)."""
    f = np.asarray(frame)
    if f.size == 0:
        return 0
    vals, counts = np.unique(f, return_counts=True)
    return int(vals[int(counts.argmax())])


def _skel_flood_regions(frame: np.ndarray, bg: int) -> list[dict[str, Any]]:
    """4-connected same-colour foreground regions, each as ``{color, cells, cx,
    cy, size}`` with ``(cx, cy)`` the rounded centroid. Compact list-stack flood
    fill (no imports) so it runs unchanged inside the code sandbox."""
    f = np.asarray(frame)
    h, w = f.shape
    seen = [[False] * w for _ in range(h)]
    regions: list[dict[str, Any]] = []
    for y in range(h):
        for x in range(w):
            if seen[y][x]:
                continue
            seen[y][x] = True
            color = int(f[y, x])
            if color == bg:
                continue
            cells = [(y, x)]
            stack = [(y, x)]
            while stack:
                cy, cx = stack.pop()
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < h and 0 <= nx < w and not seen[ny][nx] \
                            and int(f[ny, nx]) == color:
                        seen[ny][nx] = True
                        cells.append((ny, nx))
                        stack.append((ny, nx))
            mx = sum(c[1] for c in cells) / len(cells)
            my = sum(c[0] for c in cells) / len(cells)
            regions.append({
                "color": color, "cells": cells, "size": len(cells),
                "cx": int(round(mx)), "cy": int(round(my)),
            })
    return regions


def _skel_classify(
    regions: list[dict[str, Any]], trace: list[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split regions into (movable, fixed) by size: small regions are the pieces
    the mechanic moves; larger ones are the fixed structure / target slots."""
    movable = [r for r in regions if r["size"] <= _SKEL_MOVABLE_MAX_SIZE]
    fixed = [r for r in regions if r["size"] > _SKEL_MOVABLE_MAX_SIZE]
    if trace is not None:
        trace.append(f"parse regions={len(regions)} movable={len(movable)} "
                     f"fixed={len(fixed)}")
    return movable, fixed


def _skel_learn_move(
    transitions: list[dict[str, Any]], bg: int, trace: list[str] | None = None,
) -> str:
    """The TINY move model. From the xy-carrying click transitions, learn ONE
    abstraction: does clicking at a location MOVE a piece toward that location
    ('to_location'), or does clicking a piece CYCLE it in place ('cycle')? Vote
    per click by whether the changed cells cluster near the click (a move to the
    cursor) or stay put while the foreground count holds (an in-place cycle)."""
    to_loc = 0
    cycle = 0
    for t in transitions:
        xy = t.get("xy")
        if xy is None:
            continue
        before = np.asarray(t["before"])
        after = np.asarray(t["after"])
        if before.shape != after.shape:
            continue
        ys, xs = np.where(before != after)
        if len(xs) == 0:
            continue
        d = abs(float(xs.mean()) - xy[0]) + abs(float(ys.mean()) - xy[1])
        same_count = int((before != bg).sum()) == int((after != bg).sum())
        if d <= _SKEL_NEAR and same_count:
            to_loc += 1
        else:
            cycle += 1
    mode = "to_location" if to_loc >= cycle and to_loc > 0 else (
        "cycle" if cycle > 0 else "none")
    if trace is not None:
        trace.append(f"move-model to_location={to_loc} cycle={cycle} -> {mode}")
    return mode


def _skel_plan_to_location(
    movers: list[dict[str, Any]], targets: list[dict[str, Any]],
    trace: list[str] | None = None,
) -> list[tuple[int, int]]:
    """Shallow bounded DFS over the learned move model: assign movers to DISTINCT
    target cells, MAXIMIZING the number placed then MINIMIZING total L1 travel (each
    mover clicked toward its target). Branches over the ``_SKEL_BRANCH`` nearest
    targets plus a skip, depth-capped at ``_SKEL_SEARCH_DEPTH`` — a faithful tiny
    search, not a sort. The (−placed, cost) key handles fewer targets than movers."""
    tgt = [(t["cx"], t["cy"]) for t in targets]
    best: dict[str, Any] = {"key": None, "assign": []}
    limit = min(len(movers), _SKEL_SEARCH_DEPTH)

    def leaf(cost: float, assign: list[tuple[int, int]]) -> None:
        key = (-len(assign), cost)
        if best["key"] is None or key < best["key"]:
            best["key"] = key
            best["assign"] = list(assign)

    def dfs(i: int, used: set[int], cost: float, assign: list[tuple[int, int]]) -> None:
        if i >= limit:
            leaf(cost, assign)
            return
        mx, my = movers[i]["cx"], movers[i]["cy"]
        order = sorted(range(len(tgt)),
                       key=lambda j: abs(tgt[j][0] - mx) + abs(tgt[j][1] - my))
        placed = False
        for j in order[:_SKEL_BRANCH]:
            if j in used:
                continue
            placed = True
            used.add(j)
            assign.append(tgt[j])
            dfs(i + 1, used, cost + abs(tgt[j][0] - mx) + abs(tgt[j][1] - my), assign)
            assign.pop()
            used.discard(j)
        if not placed:  # no free target for this mover: skip it, keep searching
            dfs(i + 1, used, cost, assign)

    dfs(0, set(), 0.0, [])
    if trace is not None:
        trace.append(f"dfs placed={len(best['assign'])} key={best['key']}")
    return best["assign"]


def simdfs_skel_core(
    current_frame: Any,
    transitions: list[dict[str, Any]],
    act: Callable[..., None],
    trace: list[str] | None = None,
) -> None:
    """Compact faithful-sim family core: parse the board into movable pieces and
    fixed structure, learn a tiny move model from the observed clicks, then plan a
    short click sequence by shallow search toward a simple goal (pieces onto
    distinct target cells). Falls back to probing an untried piece when nothing
    has been learned yet."""
    frame = np.asarray(current_frame)
    bg = _skel_background(frame)
    movers, fixed = _skel_classify(_skel_flood_regions(frame, bg), trace)
    mode = _skel_learn_move(transitions, bg, trace)

    if mode == "to_location" and movers and fixed:
        plan = _skel_plan_to_location(movers, fixed, trace)
        for (x, y) in plan:
            act("CLICK", int(x), int(y))
        if plan:
            return
    if mode == "cycle" and movers:
        if trace is not None:
            trace.append(f"cycle -> click {len(movers)} pieces")
        for r in movers:
            act("CLICK", int(r["cx"]), int(r["cy"]))
        return

    # Probe fallback: click an untried movable piece to elicit the mechanic.
    clicked = {
        (int(t["xy"][0]), int(t["xy"][1]))
        for t in transitions if t.get("xy") is not None
    }
    for r in movers:
        if (r["cx"], r["cy"]) not in clicked:
            if trace is not None:
                trace.append(f"probe untried piece ({r['cx']},{r['cy']})")
            act("CLICK", int(r["cx"]), int(r["cy"]))
            return
    if trace is not None:
        trace.append("nothing learned and no untried piece -> no-op")
