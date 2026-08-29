"""The two MODEL repairs `gantry` needs beyond perception, applied by monkeypatch.

  A (bit 0)  an AIMED warp.  `_warps[(click, pos)] -> landed` is keyed on the press and the cell it
     was pressed from, so the same press from the same cell can only ever land in one place.  On
     dc22 level 6 a second control RE-AIMS the teleport: after it has been pressed k times the same
     press from the same tile lands somewhere else.  The key gains the phase of every OTHER ring,
     and a destination is believed for an unmeasured phase only when every measured phase agrees.

  B (bit 1)  the exploration that makes A observable.  Standing on a paired tile, the tool tests
     each control ONCE and never again; with an aimed warp that measures one of four answers and
     records the other three as "no warp".  While it is standing there and some ring still has an
     untried phase for this tile, one press of that ring costs one action and is the only way the
     other destinations are ever seen.

Not a probe — imported by the dc22 probes.  `apply(mask)` is idempotent.
"""
from __future__ import annotations

from collections import deque

import numpy as np

_APPLIED: int | None = None
_ORIG_RIGID = None
# Ring presses spent, per paired tile, purely to re-aim a warp before it is tested again.  The
# board that needs this has one aiming ring of period 4 and two paired tiles.
_MAX_AIM_PRESSES = 24
# Presses spent standing on paired tiles, over the whole level.  The board that needs this has
# four paired tiles, eight controls and an aiming ring of period 4; the cap is what stops a board
# with many lookalike tiles from spending its level on them.
_MAX_PORTAL_PROBES = 80
# Every press this tool makes, with where it was made from and where the avatar ended up.
PRESSES: list = []


def _cfgkey(tool, click, pcfg):
    """The phase of every ring EXCEPT the one being pressed, NAMED by the ring's own control.

    ⛔ The pressed ring's own phase is left out on purpose: pressing it advances it, so including
    it would make every measurement of the same press look like a different experiment.

    ⛔ And the key names its rings rather than counting them.  A control can be UNLOCKED partway
    through a level — dc22 level 6's aiming ring appears only after a key is picked up — so a key
    that is a positional tuple changes LENGTH when that happens and every measurement taken before
    it becomes unmatchable.  Measured: the teleport's four destinations were all read correctly and
    the route could use none of them.  A named key taken before a ring existed still matches, on
    the rings it does name.
    """
    return frozenset((tuple(tool._groups[i]["click"]), int(p))
                     for i, p in enumerate(pcfg)
                     if i < len(tool._groups) and tool._groups[i]["click"] != click)


def _warp_at(tool, click, pos, pcfg):
    """Where `click` pressed at `pos` lands, under the ring phases `pcfg`."""
    entry = tool._warps.get((click, pos))
    if not entry:
        return pos
    now = _cfgkey(tool, click, pcfg)
    # The most specific measurement that AGREES with the phases in force here.
    best = None
    for key, landed in entry.items():
        if key <= now and (best is None or len(key) > len(best[0])):
            best = (key, landed)
    if best is not None:
        return best[1]
    seen = set(entry.values())
    # ⛔ One destination measured under every phase tried is evidence that the phases do not aim
    # it; two destinations is evidence that they do, and then an untried phase is simply unknown.
    return next(iter(seen)) if len(seen) == 1 else pos


def _components(mask_arr):
    """Connected components (4-neighbour) of a boolean mask, as boolean masks."""
    h, w = mask_arr.shape
    seen = np.zeros_like(mask_arr)
    out = []
    for sy, sx in np.argwhere(mask_arr):
        sy, sx = int(sy), int(sx)
        if seen[sy, sx]:
            continue
        comp = np.zeros_like(mask_arr)
        stack = [(sy, sx)]
        seen[sy, sx] = True
        while stack:
            y, x = stack.pop()
            comp[y, x] = True
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask_arr[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append(comp)
    return out


def _rigid_translation_component(before, after, skip):
    """`rigid_translation`, and if no COLOUR translates, ask whether one of its BODIES did.

    ⛔ The inherited rule reads a colour's whole footprint as one body: a colour qualifies only if
    every pixel of it reappears translated. Its docstring already allows for a body drawn partly in
    a colour it shares with scenery — and expects ANOTHER colour to carry the evidence. Measured on
    dc22 level 6, the crane is drawn in ONE colour and that colour is shared with static scenery
    elsewhere on the board, so NO colour translates and a real, plain, 4-row slide of a 28-pixel
    body reads as "the board answered but not as a clean slide".

    A connected component is the same evidence standard applied to the right object: its pixels all
    reappear translated, and every changed pixel lies where it was or where it went. The candidate
    steps are not searched — a pure translation makes the changed region the union of the body and
    its image, so the step is the corner-to-corner offset, and there are exactly two of those.
    """
    from admorphiq.tools.gantry import _shifted
    got = _ORIG_RIGID(before, after, skip)
    if got is not None:
        return got
    if before.shape != after.shape:
        return None
    diff = before != after
    if not diff.any():
        return None
    dys, dxs = np.where(diff)
    dy0, dx0, dy1, dx1 = int(dys.min()), int(dxs.min()), int(dys.max()), int(dxs.max())
    colours = set(int(v) for v in np.unique(before)) | set(int(v) for v in np.unique(after))
    best = None
    for colour in sorted(colours - skip):
        mb_all = before == colour
        if not mb_all.any():
            continue
        after_col = after == colour
        for comp in _components(mb_all):
            if not (comp & diff).any():
                continue
            ys, xs = np.where(comp)
            y0, x0, y1, x1 = int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())
            for delta in {(dy0 - y0, dx0 - x0), (dy1 - y1, dx1 - x1)}:
                if delta == (0, 0):
                    continue
                sh = _shifted(comp, delta)
                if int(sh.sum()) != int(comp.sum()):
                    continue
                if not bool((sh & ~after_col).sum() == 0):
                    continue
                if (diff & ~(comp | sh)).any():
                    continue
                if best is None or int(comp.sum()) > int(best[1].sum()):
                    best = (delta, comp)
    return best


def apply(mask: int = 3) -> None:
    global _APPLIED
    if _APPLIED == mask:
        return
    _APPLIED = mask
    from admorphiq.tools import gantry as GG
    global _ORIG_RIGID
    if _ORIG_RIGID is None:
        _ORIG_RIGID = GG.rigid_translation

    G = GG.GantryCraneTool
    use_a, use_b, use_c = bool(mask & 1), bool(mask & 2), bool(mask & 4)
    use_d = bool(mask & 8)
    use_e = bool(mask & 16)
    use_f = bool(mask & 32)
    use_g = bool(mask & 64)

    if use_d:
        GG.rigid_translation = _rigid_translation_component
        import admorphiq.tools.gantry as _g
        _g.rigid_translation = _rigid_translation_component

    if use_g:
        orig_act_g = G._act

        def _act_g(self, geom, start, goal, panel):
            """Retire on running out of IDEAS, not on running out of ROUTE.

            ⛔ `_stall` counts consecutive turns with nothing to propose and hands the level back at
            three, and `_stalls` is reset only when a ROUTE is found. On a board whose route needs a
            machine the tool has not met yet, every turn spent discovering that machine is a stall.
            Measured on dc22 level 6: the tool presses the crane's up-button from the up-plate,
            reads a 28-pixel body sliding four rows — the exact fact the level turns on — and
            RETIRES ON THAT ACTION, because learning it was not progress by the only definition the
            tool had. A measurement is progress. A turn that adds a fact resets the count.
            """
            facts = (len(self._kind) + len(self._warps) + len(self._slid) + len(self._edges)
                     + len(self._objects) + len(self._visited) + len(self._groups))
            if facts != getattr(self, "_facts", -1):
                self._facts = facts
                self._stalls = 0
            return orig_act_g(self, geom, start, goal, panel)

        G._act = _act_g

    if use_f:
        orig_register = G._register_slide

        def _register_slide(self, click, before, board, slide):
            if self._shape is None:
                cells = getattr(self, "_slidcell", None)
                if cells is None:
                    cells = self._slidcell = []
                if self._before_pos is not None and self._before_pos not in cells:
                    cells.append(self._before_pos)
            return orig_register(self, click, before, board, slide)

        G._register_slide = _register_slide

        orig_act_f = G._act

        def _act_f(self, geom, start, goal, panel):
            """Walk to the NEIGHBOURS of where a body slid, before believing the slide is a picture.

            ⛔ A slide stays provisional until a SECOND control moves the same shape, and that rule
            is right — a terrain control cycling a bar through six positions is four exact rigid
            translations in a row. What it assumes is that the second control can be asked from
            where the tool is standing. Measured on dc22 level 6: each of the four crane drives acts
            only while the avatar stands on ITS OWN pressure plate, and the four plates are four
            adjacent cells. So the confirmation the tool needs is one step away and it never takes
            it, because a plate is not an object and nothing routes there.
            """
            cells = getattr(self, "_slidcell", None)
            if (self._shape is None and cells and not self._steps and not self._dirty
                    and getattr(self, "_nearprobes", 0) < 24):
                near = set()
                for (cy, cx) in cells:
                    for (dy, dx) in self._deltas.values():
                        near.add((cy + dy, cx + dx))
                near -= self._visited
                near.discard(start)
                if near:
                    steps = self._plan_full(geom["board"], start, near)
                    if steps:
                        self._nearprobes = getattr(self, "_nearprobes", 0) + 1
                        self._steps = steps
                        return [self._emit_planned(geom, start)]
            return orig_act_f(self, geom, start, goal, panel)

        G._act = _act_f

    if use_e:
        orig_reset_e = G.reset

        def reset_e(self):
            orig_reset_e(self)
            self._cellprobe = set()

        G.reset = reset_e

        orig_confirm = G._confirm_probe

        def _confirm_probe(self, geom, start):
            """Retry an INERT control from a cell it has not been tried at.

            ⛔ The tool already knows that "a control that did nothing" is not an inert control
            until it has been tried somewhere else — it says so, and it applies it across RAIL
            positions. On this board the coordinate that matters is the AVATAR's: each of the four
            crane drives acts only while the avatar stands on its own pressure plate, and is a
            dead button from all ~500 other cells. Measured: pressing (32,50) from (55,34) slides a
            28-pixel body four rows; the same press from the start cell does nothing at all.
            """
            if self._presses < GG._MAX_RAIL_PRESSES:
                for click in sorted(c for c, k in self._kind.items() if k == "idle"):
                    if (click, start) in self._cellprobe:
                        continue
                    self._cellprobe.add((click, start))
                    self._presses += 1
                    return [self._press(geom, start, click, "probe")]
            return orig_confirm(self, geom, start)

        G._confirm_probe = _confirm_probe

    if use_c:
        def _portals(self, board):
            """Paired tiles, with the ONE tile under the avatar read from memory.

            ⛔ The inherited version re-reads every remembered object's picture off the live board,
            and the avatar's own square is exactly the size of a tile — so the tile the avatar is
            STANDING ON reads as a square of the avatar's colour, pairs with nothing, and drops out
            of the set.  The branch that presses a control while standing on a paired tile is
            therefore unreachable: measured on dc22 level 6, 268 presses over a whole game and not
            one of them from the tile whose teleport is the level's only way off the island.

            ⛔ Only the occluded tile is taken from memory.  Remembering ALL of them is MEASURED
            HARMFUL — dc22 goes 5 levels to 3 — because a stale picture pairs tiles the board has
            since repainted, and this family repaints tiles for a living.
            """
            side = self._side
            pics = getattr(self, "_pics", None)
            if pics is None:
                pics = self._pics = {}
            grid = np.asarray(board)
            groups: dict = {}
            for (y, x) in self._objects:
                tile = grid[y:y + side, x:x + side]
                if tile.size != side * side:
                    continue
                vals = frozenset(int(v) for v in tile.ravel())
                if vals == {self._avatar}:
                    vals = pics.get((y, x))
                    if vals is None:
                        continue
                else:
                    pics[(y, x)] = vals
                groups.setdefault(vals, []).append((y, x))
            return {c for cells in groups.values() if len(cells) == 2 for c in cells}

        G._portals = _portals

        orig_reset_c = G.reset

        def reset_c(self):
            orig_reset_c(self)
            self._pics = {}

        G.reset = reset_c

    if use_a:
        orig_resolve = G._resolve_press

        def _resolve_press(self, geom, click):
            board = geom["board"]
            if self._before_pos is not None:
                landed = self._at(board, self._avatar)
                key = _cfgkey(self, click, self._config())
                self._warp_tested.add((click, self._before_pos, key))
                # ⛔ The two-element key stays too: the inherited `_act` reads it to decide whether
                # a tile still has an untested control, and a key it cannot find reads as untested
                # for ever, which is a press every turn and no progress.
                self._warp_tested.add((click, self._before_pos))
                if landed is not None:
                    self._warps.setdefault((click, self._before_pos), {})[key] = landed
                PRESSES.append((tuple(click), tuple(self._before_pos),
                                tuple(landed) if landed else None, key))
            keep_pos, self._before_pos = self._before_pos, None
            try:
                orig_resolve(self, geom, click)
            finally:
                self._before_pos = keep_pos

        G._resolve_press = _resolve_press

        def _plan_full(self, board, start, goals):
            """`gantry._plan_full` with the warp read through its aim."""
            if not self._deltas or self._step() <= 0 or not goals:
                return []
            cache: dict = {}
            cap = GG._BFS_CAP if self._settled_model() else GG._SCOUT_CAP
            moves = list(self._deltas.items())
            rings = [(i, gr["click"], gr["period"])
                     for i, gr in enumerate(self._groups) if gr["period"]]
            drives = self._drives()
            gated = getattr(self, "_gate", {})
            hidden = getattr(self, "_hidden", set())
            origin = (start, self._config(), self._off)
            seen: dict = {origin: (None, None)}
            queue: deque = deque([origin])
            found = None
            while queue and len(seen) < cap:
                state = queue.popleft()
                pos, pcfg, off = state
                if pos in goals:
                    found = state
                    break
                here = self._grid(cache, board, pcfg, off)
                for action, (dy, dx) in moves:
                    nxt = (pos[0] + dy, pos[1] + dx)
                    key = (nxt, pcfg, off)
                    if nxt not in here or key in seen:
                        continue
                    seen[key] = (state, ((action, None), "walk", nxt, off))
                    queue.append(key)
                for index, click, period in rings:
                    nc = list(pcfg)
                    nc[index] = (pcfg[index] + 1) % period
                    ncfg = tuple(nc)
                    land = _warp_at(self, click, pos, pcfg)
                    key = (land, ncfg, off)
                    if key in seen or land not in self._grid(cache, board, ncfg, off):
                        continue
                    seen[key] = (state, ((6, (click[1], click[0])), "press", land, off))
                    queue.append(key)
                for click in drives:
                    nxt_off = self._edges.get(off, {}).get(click)
                    if nxt_off is None:
                        continue
                    if click in hidden and pos not in gated.get(click, set()):
                        # ⛔ A drive that only EXISTS while the avatar stands somewhere cannot be
                        # pressed from anywhere else; planning it from anywhere else spends the
                        # level proving that.
                        continue
                    land = _warp_at(self, click, pos, pcfg)
                    key = (land, pcfg, nxt_off)
                    if key in seen or land not in self._grid(cache, board, pcfg, nxt_off):
                        continue
                    seen[key] = (state, ((6, (click[1], click[0])), "drive", land, nxt_off))
                    queue.append(key)
            if found is None:
                return []
            out: list = []
            while True:
                parent, step = seen[found]
                if step is None:
                    break
                out.append(step)
                found = parent
            return out[::-1]

        G._plan_full = _plan_full

    if use_b:
        orig_reset = G.reset

        def reset(self):
            orig_reset(self)
            self._gate = {}
            self._hidden = set()
            self._aims = 0
            self._probes = 0

        G.reset = reset

        orig_act = G._act

        def _act(self, geom, start, goal, panel):
            """`gantry._act` with the warp probes re-run once per AIM, not once per tile."""
            board = geom["board"]
            ps = set(panel)
            gate = self._gate
            for click in ps:
                gate.setdefault(click, set()).add(start)
            for click in list(self._kind):
                if click not in ps:
                    self._hidden.add(click)
            if self._steps or self._dirty:
                return orig_act(self, geom, start, goal, panel)
            key_now = {click: _cfgkey(self, click, self._config()) for click in panel}
            if start in self._portals(board):
                for click in panel:
                    if (click, start, key_now[click]) not in self._warp_tested:
                        return [self._press(geom, start, click, "probe")]
                # ⛔ Every control tested AT THIS AIM.  A ring press costs one action and is the
                # only thing that can produce a different answer from this tile; without it the
                # tool measures one of four destinations and calls the tile understood.
                if self._aims < _MAX_AIM_PRESSES:
                    for index, group in enumerate(self._groups):
                        period = group["period"]
                        ring = group["click"]
                        if not period or period < 2 or ring not in ps:
                            continue
                        if any((click, start, _cfgkey(self, click, self._after(index)))
                               not in self._warp_tested for click in panel):
                            self._aims += 1
                            return [self._press(geom, start, ring, "probe")]
            return orig_act(self, geom, start, goal, panel)

        G._act = _act

        def _after(self, index):
            cfg = list(self._config())
            period = self._groups[index]["period"] or 1
            cfg[index] = (cfg[index] + 1) % period
            return tuple(cfg)

        G._after = _after

    _ = np
