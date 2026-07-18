"""re86 L8 FULL 2-leg run, frame-only: two hollow-square OUTLINES, each
recolour -> reshape -> place onto a rectangle-corner target, snapshot win 7->8.

L8 mechanic (probe re86_l8_probe.py + reshape re86_l8_reshape.py):
- 2 outlines (13x13, perim 48), colours {10,12}; 2 rect-corner targets colour-11
  = 19x7 (tall/narrow -> HORIZONTAL reshape h+3/w-3) and colour-6 = 10x16
  (short/wide -> VERTICAL reshape h-3/w+3). Both reshapes CONFIRMED against the
  TOP-RIGHT CORNER obstacle (rows 1-5, cols 58-62).
- Movable colours {10,12} != target colours {11,6}; 7 SCATTERED changer stations
  (incl. target colours + decoys) so each outline recolours first via a
  station-avoiding route (_l5_route). Stations: 11@(7,7) 6@(22,7) 12@(30,20)
  9@(30,27) 8@(30,41) 10@(30,52) 14@(30,59). station-6 sits directly BELOW
  station-11 on col 7 -> col-7 ascent must avoid it.
- Movables don't collide with each other (L7 finding) -> free leg order, snapshot.

dir 1=up 2=down 3=left 4=right.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import (
    Adapter, _station_boxes, _target_boxes, _l6_obstacle_box, _l5_route,
)
from admorphiq.adapters25.base import canonical_layer
from re86_l7_ctrl import marker, l7_regions, region_at  # type: ignore

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
DIRMAP = {1: (-1, 0), 2: (1, 0), 3: (0, -1), 4: (0, 1)}
MOVE_IDS = [1, 2, 3, 4]


def step(env, a):
    return env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)


def sel_true_color(env):
    """GROUND-TRUTH colour of the SELECTED outline sprite (dev-time only)."""
    from collections import Counter as _C
    for s in env._game.current_level.get_sprites_by_tag("0036ilsgwuvbxv"):
        if int(s.pixels[s.height // 2, s.width // 2]) == 0:
            cc = _C(int(v) for row in s.pixels for v in row if v not in (-1, 0))
            return (cc.most_common(1)[0][0] if cc else None, s.x, s.y, s.width, s.height)
    return None


class Ctx:
    def __init__(self, env, obs, stations, sboxes, sbox, ob, tby, idx_color):
        self.env = env; self.obs = obs
        self.stations = stations; self.sboxes = sboxes; self.sbox = sbox
        self.ob = ob; self.tby = tby; self.idx_color = idx_color
        self.sel = 0


def leg_outline(ctx, color, tgt_color, verbose=True):
    env = ctx.env; ob = ctx.ob; sboxes = ctx.sboxes
    tgt = sorted(ctx.tby[tgt_color])
    tr = [r for r, _c in tgt]; tc = [c for _r, c in tgt]
    rect = (min(tr), max(tr), min(tc), max(tc))
    th, tw = rect[1] - rect[0] + 1, rect[3] - rect[2] + 1
    tall = th >= tw  # tall/narrow -> horizontal reshape; wide -> vertical
    scen = ctx.stations[tgt_color]
    other_boxes = [b for c, b in ctx.sbox.items() if c != tgt_color]
    walls: set = set()
    phase = "recolour"; last_act = 1
    for it in range(700):
        g = canonical_layer(ctx.obs)
        mk = marker(g)
        if mk is None:
            ctx.obs = step(env, A[last_act]); continue
        if ctx.idx_color[ctx.sel] != color:
            ctx.obs = step(env, A[5]); ctx.sel = (ctx.sel + 1) % 3 if len(ctx.idx_color) == 3 else (ctx.sel + 1) % 2
            continue
        reg = region_at(g, mk, sboxes)
        cur = reg["color"] if reg else None
        tc_gt = sel_true_color(env)
        if verbose and tc_gt is not None and tc_gt[0] != getattr(leg_outline, "_ptc", None):
            print(f"    c{color} it{it} phase={phase} TRUECOLOUR->{tc_gt[0]} @({tc_gt[1]},{tc_gt[2]}) {tc_gt[3]}x{tc_gt[4]}")
            leg_outline._ptc = tc_gt[0]
        if verbose and it % 40 == 0:
            print(f"    c{color} it{it} phase={phase} mk={mk} cur={cur} dims={reg['bbox'] if reg else None}")

        if phase == "recolour":
            if cur == tgt_color:
                phase = "to_obstacle"
                if verbose:
                    print(f"    [it{it}] c{color} recoloured -> {tgt_color} mk={mk}")
                continue
            # route the centre to the target station, other stations inflated.
            act = _l5_route(mk, scen, 6, other_boxes, walls, DIRMAP, MOVE_IDS)
            last_act = act or last_act
            ctx.obs = step(env, A[act] if act else A[last_act]); continue

        if phase == "to_obstacle":
            # stage next to the corner obstacle: tall target -> rows overlap the
            # obstacle rows with cols CLEAR-LEFT (then push right); wide target ->
            # cols overlap with rows BELOW (then push up). Route avoiding stations.
            if reg is None:
                ctx.obs = step(env, A[last_act]); continue
            r0, r1, c0, c1 = reg["bbox"]
            if tall:
                # stage TIGHT to the obstacle: right edge one push left of the
                # obstacle cols, top overlapping the obstacle rows, cols CLEAR so
                # the rise never reshapes prematurely.
                if c1 > ob[1] - 3:
                    want = (0, -1)
                elif c1 < ob[1] - 5:
                    want = (0, 1)
                elif r0 > ob[0]:
                    want = (-1, 0)
                elif r0 < ob[0] - 2:
                    want = (1, 0)
                else:
                    phase = "reshape"; continue
            else:
                # want cols overlapping obstacle, bottom just below obstacle rows
                if c1 < ob[3]:
                    want = (0, 1)
                elif c0 > ob[3]:
                    want = (0, -1)
                elif r0 > ob[2] + 1:
                    want = (-1, 0)
                else:
                    phase = "reshape"; continue
            act = next((a for a, v in DIRMAP.items() if v == want), None)
            last_act = act or last_act
            ctx.obs = step(env, A[act] if act else A[last_act]); continue

        if phase == "reshape":
            if reg is None:
                ctx.obs = step(env, A[last_act]); continue
            r0, r1, c0, c1 = reg["bbox"]
            h, w = r1 - r0 + 1, c1 - c0 + 1
            if verbose:
                print(f"      c{color} reshape it{it} {h}x{w} bbox=({r0},{r1},{c0},{c1}) cur={cur}")
            if tall:
                # STOP on WIDTH (cols are on-board-readable; the 19-tall piece's
                # TOP goes off-board so parsed h caps at ~16 and cannot be trusted).
                if w <= tw:
                    phase = "place"; print(f"    [it{it}] c{color} reshaped {h}x{w} (tall)"); continue
                last_act = 4; ctx.obs = step(env, A[4]); continue  # push RIGHT -> h+3/w-3
            else:
                if w >= tw:
                    phase = "place"; print(f"    [it{it}] c{color} reshaped {h}x{w} (wide)"); continue
                last_act = 1; ctx.obs = step(env, A[1]); continue  # push UP -> h-3/w+3

        if phase == "place":
            if reg is None:
                ctx.obs = step(env, A[last_act]); continue
            if all(t in reg["cells"] for t in tgt):
                print(f"    [it{it}] c{color} PLACED bbox={reg['bbox']}"); return True
            r0, r1, c0, c1 = reg["bbox"]
            h, w = r1 - r0 + 1, c1 - c0 + 1
            tgt_ccol = (rect[2] + rect[3]) // 2
            cen_col = (c0 + c1) // 2
            if tall:
                # COLUMN-CARRY descent: a 19-tall piece cannot thread the thin
                # scattered station band via a centre-based router (its body clips
                # stations mid-descent). Instead traverse LEFT along the top (above
                # the band; station-11 is the SAME colour = safe) to the target
                # column, then descend straight down it (cols 9-15 clear the station
                # swatches), then settle onto the corners.
                if r0 < 20 and abs(cen_col - tgt_ccol) > 1:
                    last_act = 4 if cen_col < tgt_ccol else 3
                    ctx.obs = step(env, A[last_act]); continue
                if r1 < rect[1]:
                    last_act = 2; ctx.obs = step(env, A[2]); continue  # descend
                if cen_col != tgt_ccol:
                    last_act = 4 if cen_col < tgt_ccol else 3
                    ctx.obs = step(env, A[last_act]); continue
                if r0 > rect[0]:
                    last_act = 1; ctx.obs = step(env, A[1]); continue
                last_act = 2; ctx.obs = step(env, A[2]); continue
            # WIDE piece: the router threads the wider gap fine (w//2 inflation).
            half = max(w // 2, 2)
            cen = ((r0 + r1) // 2, cen_col)
            if cen[0] <= ob[2] + half and cen[1] >= ob[1] - half:
                last_act = 2; ctx.obs = step(env, A[2]); continue  # escape the corner
            tgt_cen = ((rect[0] + rect[1]) // 2, tgt_ccol)
            act = _l5_route(mk, tgt_cen, half, other_boxes + [ob], walls, DIRMAP, MOVE_IDS)
            if act is None:
                act = 2 if r1 < 60 else 3
            last_act = act
            ctx.obs = step(env, A[act]); continue
    return False


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    s = 0
    while s < 6000 and int(getattr(obs, "levels_completed", 0) or 0) < 7 and not ad.is_done([], obs):
        obs = step(env, ad.choose_action([], obs)); s += 1
    for _ in range(3):
        obs = step(env, A[5])
    g = canonical_layer(obs)
    stations, sboxes = _station_boxes(g)
    sbox = {}
    for col, cen in stations.items():
        for b in sboxes:
            if b[0] <= cen[0] <= b[2] and b[1] <= cen[1] <= b[3]:
                sbox[col] = b; break
    ob = _l6_obstacle_box(g)
    tby = {}
    for r, c in _target_boxes(g):
        tby.setdefault(g[r][c], []).append((r, c))
    regs = l7_regions(g, sboxes)
    spawn = {m["color"]: m["cen"] for m in regs}

    def nearest_spawn(mk):
        return min(spawn, key=lambda k: abs(spawn[k][0] - mk[0]) + abs(spawn[k][1] - mk[1]))
    n = len(regs)
    idx_color = []
    for _k in range(n):
        idx_color.append(nearest_spawn(marker(canonical_layer(obs))))
        obs = step(env, A[5])
    print(f"stations={stations} obstacle={ob}")
    print(f"targets={ {k: sorted(v) for k, v in tby.items()} } movables={list(spawn)} idx_color={idx_color}")

    ctx = Ctx(env, obs, stations, sboxes, sbox, ob, tby, idx_color)
    ctx.sel = 0

    def lv():
        return int(getattr(ctx.obs, "levels_completed", 0) or 0)

    # assign: movable colours -> target colours 1:1 (both outlines identical);
    # sorted bijection is stable/frame-only.
    mov_colors = sorted(spawn)
    tgt_colors = sorted(tby)
    legs = list(zip(mov_colors, tgt_colors))
    print(f"legs (movable->target) = {legs}")
    for mc, tc in legs:
        print(f"--- leg: outline c{mc} -> {tc} (level={lv()} state={getattr(ctx.obs,'state',None)}) ---")
        ok = leg_outline(ctx, mc, tc)
        print(f"    -> {'placed' if ok else 'FAILED'} (level {lv()} state={getattr(ctx.obs,'state',None)})")
        if lv() >= 8:
            print(f"*** L8 CLEARED ***"); break
    # GROUND-TRUTH sprite colours (dev-time) — is a placed piece the wrong colour?
    from collections import Counter as _C
    for s in env._game.current_level.get_sprites_by_tag("0036ilsgwuvbxv"):
        cc = _C(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        col = cc.most_common(1)[0][0] if cc else None
        print(f"  outline sprite @({s.x},{s.y}) {s.width}x{s.height} colour={col}")
    tgt_cells = {k: sorted(v) for k, v in tby.items()}
    gg = canonical_layer(ctx.obs)
    for tc, cells in tgt_cells.items():
        got = [gg[r][c] for r, c in cells]
        print(f"  target colour-{tc} cells {cells} -> frame colours {got}")
    print(f"FINAL levels_completed={lv()} state={getattr(ctx.obs,'state',None)}")


if __name__ == "__main__":
    main()
