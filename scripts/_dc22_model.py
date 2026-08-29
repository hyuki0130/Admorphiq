"""dc22 level 6 — full analytic state model + search, mirrored from the engine and VERIFIED.

The level chains five gated mechanics:
  * 'f' button  -> shifts a 3-row staircase of walkable bars (period 6)
  * 'c' button  -> swaps every group-c form (period 2) AND teleports the mover between the
                   two tewfut tiles that share a prefix
  * piyqze key 'd' at (6,18) -> unlocks the colour-cycle button, which re-prefixes the tile
                   at (18,48) and therefore RE-AIMS the teleport
  * piyqze key 'g' at (34,48) -> unlocks the crane's grab button
  * four njvd-rolo pressure plates -> each makes ONE crane direction button visible while the
                   mover stands on it; the crane carries a 20x20 INTANGIBLE platform
The model reproduces the engine's own support (`sxnzvaqltp`) and collision (`collides_with`)
predicates; `--verify` checks them cell by cell against the live engine before searching.

Varying parameter FIRST = search node cap (or 0 = verify only).  Prints ONE JSON line.
"""
import sys, json, collections, importlib.util

SRC = "environment_files/dc22/fdcac232/dc22.py"
FBTN = (53, 5)
CBTN = (48, 23)
DBTN = None  # filled from the level (renrjo-buezna)
GOAL = (46, 6)
PLATES = {}  # letter -> (x, y)
DIRS = {1: (0, -2), 2: (0, 2), 3: (-2, 0), 4: (2, 0)}
ORDER = ["tewfutpibpar", "tewfutrefgps", "tewfutyefmyf", "tewfutblrmbx"]


def load():
    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dc22mod"] = m
    spec.loader.exec_module(m)
    return m


def sprite_mask(s):
    px = s.render()
    return {(x, y) for y in range(px.shape[0]) for x in range(px.shape[1]) if px[y, x] >= 0}


def build(m):
    """Return everything the search needs, plus the engine objects for verification."""
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode as IM
    g = m.Dc22()
    g.set_level(5)
    return g, ActionInput, IM


def support_and_block(g, IM, exclude_names=()):
    """Mirror of sxnzvaqltp (support) and collides_with (blocking) over the even grid."""
    mover = g.qnnpcoyzd
    sup = set()
    blk = set()
    solid = []   # (x, y, mask, is_support, is_block)
    for s in g.current_level.get_sprites():
        if s is mover or "ignore" in s.tags:
            continue
        if s.name in exclude_names:
            continue
        is_sup = (s._interaction == IM.INTANGIBLE and "crzsjq" not in s.tags and "vcha" not in s.tags)
        is_blk = s._interaction in (IM.TANGIBLE, IM.INVISIBLE)
        if not (is_sup or is_blk):
            continue
        solid.append((s.x, s.y, sprite_mask(s), is_sup, is_blk))
    for (sx, sy, mask, is_sup, is_blk) in solid:
        for (dx, dy) in mask:
            x, y = sx + dx, sy + dy
            if x % 2 == 0 and y % 2 == 0 and is_sup:
                sup.add((x, y))
            if is_blk:
                # mover occupies (x..x+1, y..y+1); it is blocked from any even cell overlapping
                for ox in (0, -1):
                    for oy in (0, -1):
                        cx, cy = x + ox, y + oy
                        if cx % 2 == 0 and cy % 2 == 0:
                            blk.add((cx, cy))
    return sup, blk


def verify(g, IM):
    """Prove the mirrored predicates equal the engine's, cell by cell."""
    sup, blk = support_and_block(g, IM)
    mover = g.qnnpcoyzd
    ox, oy = mover.x, mover.y
    bad = 0
    for y in range(0, 64, 2):
        for x in range(0, 64, 2):
            e_sup = g.sxnzvaqltp(x, y, mover) is not None
            mover.set_position(x, y)
            e_blk = any(g.collides_with(mover, o) for o in g.current_level.get_sprites())
            mover.set_position(ox, oy)
            if e_sup != ((x, y) in sup) or e_blk != ((x, y) in blk):
                bad += 1
                if bad <= 5:
                    print(f"   MISMATCH ({x},{y}) engine sup={e_sup} blk={e_blk} "
                          f"model sup={(x,y) in sup} blk={(x,y) in blk}", flush=True)
    return bad



def collect(g, IM, m):
    """Static level facts the search needs."""
    from arcengine.base_game import ActionInput
    facts = {}
    facts["crane_origin"] = g.cuvqxkfop
    facts["crane_off"] = g.yfxrlzdyvi()
    # vcha rail mask
    rail = set()
    for s in g.current_level.get_sprites_by_tag("vcha"):
        if s._interaction == IM.REMOVED:
            continue
        for (dx, dy) in sprite_mask(s):
            rail.add((s.x + dx, s.y + dy))
    facts["rail"] = rail
    # plates: letter -> cell
    plates = {}
    for s in g.current_level.get_sprites_by_tag("njvd-rolo"):
        L = next((t for t in s.tags if len(t) == 1), None)
        if L:
            plates[L] = (s.x, s.y)
    facts["plates"] = plates
    # buttons: letter -> (kind, click xy)
    btns = {}
    for s in g.current_level.get_sprites_by_tag("sys_click"):
        L = next((t for t in s.tags if len(t) == 1), None)
        kind = None
        for k in ("up", "dowlja", "lersnf", "riidpd", "grawwq"):
            if k in s.tags:
                kind = k
        mk = sprite_mask(s)
        if not mk:
            continue
        dx, dy = sorted(mk, key=lambda t: (t[1], t[0]))[0]
        btns[L or s.name] = (kind, (s.x + dx, s.y + dy), s.name)
    facts["buttons"] = btns
    # tewfut tiles: cell -> prefix (the (18,48) one is the cycler)
    tew = {}
    for s in g.current_level.get_sprites_by_tag("tewfut"):
        if s._interaction == IM.REMOVED:
            continue
        tew[(s.x, s.y)] = s.name[:-1]
    facts["tewfut"] = tew
    facts["cycler"] = next(((s.x, s.y) for s in g.current_level.get_sprites_by_tag("tewfut")
                            if "tewfut-color-cycle" in s.tags), None)
    # piyqze keys: cell -> letter
    facts["keys"] = {}
    for s in g.current_level.get_sprites_by_tag("piyqze"):
        L = next((t for t in s.tags if len(t) == 1), None)
        facts["keys"][(s.x, s.y)] = L
    # brixto masks per form + its size/start
    br = {}
    for name in ("brixto-orckhi1", "brixto-orckhi2"):
        for s in g.current_level.get_sprites():
            if s.name == name:
                br[name] = (sprite_mask(s), s.width, s.height, (s.x, s.y))
                break
    facts["brixto"] = br
    return facts


def base_maps(m, IM):
    """support/block per bar phase, with the carried platform EXCLUDED."""
    from arcengine.base_game import ActionInput
    g = m.Dc22(); g.set_level(5)
    sups, blks = [], []
    for p in range(6):
        s, b = support_and_block(g, IM, exclude_names=("brixto-orckhi1", "brixto-orckhi2"))
        sups.append(s); blks.append(b)
        g.perform_action(ActionInput(id=6, data={"x": FBTN[0], "y": FBTN[1]}))
    return sups, blks


def search(facts, sups, blks, cap):
    rail = facts["rail"]
    ox, oy = facts["crane_origin"]
    offx, offy = facts["crane_off"]
    plates = facts["plates"]
    btns = facts["buttons"]
    tew = dict(facts["tewfut"])
    cyc = facts["cycler"]
    keys = facts["keys"]
    br = facts["brixto"]
    m1, bw, bh, bstart = br["brixto-orckhi1"]
    m2 = br["brixto-orckhi2"][0]
    bmask = {0: {(x, y) for (x, y) in m1 if True}, 1: {(x, y) for (x, y) in m2}}
    # direction buttons: kind -> (letter, click xy)
    dirbtn = {}
    for L, (kind, xy, nm) in btns.items():
        if kind:
            dirbtn[kind] = (L, xy, nm)

    def anchor(i, j):
        return (ox + 4 * i + offx, oy - 4 * j + offy)

    def rail_ok(i, j):
        return anchor(i, j) in rail

    def sup_at(p, q, bpos, cell):
        if cell in sups[p]:
            return True
        bx, by = bpos
        return (cell[0] - bx, cell[1] - by) in bmask[q]

    # teleport: (q, r, cell) -> cell
    fixed = {c: pre for c, pre in tew.items() if c != cyc}

    def teleport(q, r, cell):
        if cell == cyc:
            want = ORDER[r]
            for c, pre in fixed.items():
                if pre == want:
                    return c
            return None
        pre = fixed.get(cell)
        if pre is None:
            return None
        return cyc if ORDER[r] == pre else None

    start = (0, 0, 0, 0, 0, 0, bstart[0], bstart[1], 0, 0, 28, 52)
    prev = {start: None}
    dq = collections.deque([start])
    exp = 0
    while dq and exp < cap:
        cur = dq.popleft(); exp += 1
        p, q, r, i, j, att, bx, by, dk, gk, mx, my = cur
        succ = []
        for aid, (dx, dy) in DIRS.items():
            n = (mx + dx, my + dy)
            if n in blks[p] or not sup_at(p, q, (bx, by), n):
                continue
            ndk, ngk = dk, gk
            L = keys.get(n)
            if L == "d":
                ndk = 1
            if L == "g":
                ngk = 1
            succ.append(((p, q, r, i, j, att, bx, by, ndk, ngk, n[0], n[1]), f"A{aid}"))
        np_ = (p + 1) % 6
        if sup_at(np_, q, (bx, by), (mx, my)) and (mx, my) not in blks[np_]:
            succ.append(((np_, q, r, i, j, att, bx, by, dk, gk, mx, my), "click_f"))
        nq = q ^ 1
        tp = teleport(q, r, (mx, my)) or (mx, my)
        if sup_at(p, nq, (bx, by), tp) and tp not in blks[p]:
            ndk, ngk = dk, gk
            L = keys.get(tp)
            if L == "d":
                ndk = 1
            if L == "g":
                ngk = 1
            succ.append(((p, nq, r, i, j, att, bx, by, ndk, ngk, tp[0], tp[1]), "click_c"))
        if dk:
            nr = (r + 1) % 4
            succ.append(((p, q, nr, i, j, att, bx, by, dk, gk, mx, my), "click_d"))
        # crane direction buttons, gated by standing on the matching plate
        for kind, (L, xy, nm) in dirbtn.items():
            if kind == "grawwq":
                continue
            if plates.get(L) != (mx, my):
                continue
            di, dj = {"up": (0, 1), "dowlja": (0, -1), "lersnf": (-1, 0), "riidpd": (1, 0)}[kind]
            ni, nj = i + di, j + dj
            if not rail_ok(ni, nj):
                continue
            if att:
                ax, ay = anchor(ni, nj)
                nbx, nby = ax - bw // 2, ay - bh // 2
            else:
                nbx, nby = bx, by
            if not sup_at(p, q, (nbx, nby), (mx, my)):
                continue
            succ.append(((p, q, r, ni, nj, att, nbx, nby, dk, gk, mx, my), f"crane_{kind}"))
        # grab
        if gk and not att:
            gL, gxy, gnm = dirbtn.get("grawwq", (None, None, None))
            if gL is not None:
                ax, ay = anchor(i, j)
                if (bx + bw // 2, by + bh // 2) == (ax, ay):
                    succ.append(((p, q, r, i, j, 1, bx, by, dk, gk, mx, my), "crane_grab"))
        for n, lab in succ:
            if n in prev:
                continue
            prev[n] = (cur, lab)
            if (n[10], n[11]) == GOAL:
                path = []
                node = n
                while prev[node] is not None:
                    pr, l2 = prev[node]
                    path.append(l2)
                    node = pr
                return path[::-1], exp, len(prev)
            dq.append(n)
    return None, exp, len(prev)


def main():
    cap = int(sys.argv[1]) if len(sys.argv) > 1 else 200000
    m = load()
    g, ActionInput, IM = build(m)
    bad = verify(g, IM)
    if bad:
        print(json.dumps({"result": "MODEL_MISMATCH", "mismatches": bad}), flush=True)
        return
    facts = collect(g, IM, m)
    sups, blks = base_maps(m, IM)
    print(f"model ready: rail={len(facts['rail'])} plates={facts['plates']} "
          f"buttons={ {k: v[0] for k, v in facts['buttons'].items()} } cycler={facts['cycler']}", flush=True)
    path, exp, nstates = search(facts, sups, blks, cap)
    if path is None:
        print(json.dumps({"result": "NO_PLAN", "expanded": exp, "states": nstates}), flush=True)
    else:
        print(json.dumps({"result": "PLAN", "actions": len(path), "expanded": exp,
                          "states": nstates, "plan": path}), flush=True)


if __name__ == "__main__":
    main()
