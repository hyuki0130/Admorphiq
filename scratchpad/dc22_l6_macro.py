"""dc22 level 6 — MACRO search: walk-to-landmark + click-live-button.

Purpose: the level's primitive action space hides its structure (one click of a crane
button is meaningless without first standing on the matching pressure plate, and the
walkable component changes when a platform is carried).  This searches over macro moves:
walk to any reachable landmark (tewfut tile / piyqze key / pressure plate / goal), or
click any currently-live sys_click sprite.  Prints ONE JSON line; rule 7f direction-named.
"""
import sys, json, importlib.util, collections, hashlib, copy

SRC = "environment_files/dc22/fdcac232/dc22.py"
STEP = 2
DIRS = {1: (0, -STEP), 2: (0, STEP), 3: (-STEP, 0), 4: (STEP, 0)}


def load():
    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dc22mod"] = m
    spec.loader.exec_module(m)
    return m


def blocked(g, x, y):
    mv = g.qnnpcoyzd
    ox, oy = mv.x, mv.y
    mv.set_position(x, y)
    hit = False
    for o in g.current_level.get_sprites():
        if g.collides_with(mv, o):
            hit = True
            break
    mv.set_position(ox, oy)
    return hit


def reachable(g):
    """All mover positions reachable by walking, with the action path to each."""
    start = (g.qnnpcoyzd.x, g.qnnpcoyzd.y)
    prev = {start: None}
    q = collections.deque([start])
    while q:
        cur = q.popleft()
        for aid, (dx, dy) in DIRS.items():
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in prev or not (0 <= nxt[0] < 64 and 0 <= nxt[1] < 64):
                continue
            mv = g.qnnpcoyzd
            ox, oy = mv.x, mv.y
            mv.set_position(*cur)
            bad = blocked(g, *nxt)
            sup = g.sxnzvaqltp(nxt[0], nxt[1], mv) is not None
            mv.set_position(ox, oy)
            if bad or not sup:
                continue
            prev[nxt] = (cur, aid)
            q.append(nxt)
    return prev


def path_from(prev, node):
    out = []
    while prev[node] is not None:
        p, a = prev[node]
        out.append(a)
        node = p
    return out[::-1]


def live_buttons(g, IM):
    out = []
    for s in g.current_level.get_sprites_by_tag("sys_click"):
        if s.interaction in (IM.REMOVED, IM.INVISIBLE) or not s.is_visible:
            continue
        px = s.render()
        for yy in range(px.shape[0]):
            for xx in range(px.shape[1]):
                if px[yy, xx] >= 0:
                    out.append((s.name, s.x + xx, s.y + yy))
                    break
            else:
                continue
            break
    return out


def landmarks(g, IM):
    pts = []
    for s in g.current_level.get_sprites():
        if s.interaction == IM.REMOVED:
            continue
        t = set(s.tags)
        if t & {"tewfut", "piyqze", "njvd-rolo", "goknoi"}:
            pts.append((s.x, s.y, s.name))
    return pts


def key(g):
    parts = [f"{s.name}:{s.x},{s.y},{s.interaction.name}" for s in g.current_level.get_sprites()]
    parts.sort()
    parts.append(f"c:{g.sjixewahg},{g.uxtzlxsiq},{g.svxnnbpjl},{g.fvwekbbhj},{g.ozarnpwde},{g.bbobkhxob}")
    parts.append(f"m:{g.qnnpcoyzd.x},{g.qnnpcoyzd.y}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def main():
    max_nodes = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    m = load()
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode as IM

    g0 = m.Dc22()
    g0.set_level(5)
    start = g0._score
    seen = {key(g0): 1}
    q = collections.deque([(g0, [], 0)])
    expanded = 0
    best_depth = 0
    while q and expanded < max_nodes:
        g, hist, cost = q.popleft()
        expanded += 1
        if len(hist) > best_depth:
            best_depth = len(hist)
            print(f"macro-depth {best_depth} expanded {expanded} seen {len(seen)}", flush=True)
        prev = reachable(g)
        succ = []
        for (nm, cx, cy) in live_buttons(g, IM):
            succ.append(([ActionInput(id=6, data={"x": cx, "y": cy})], f"click:{nm}", 1))
        for (lx, ly, nm) in landmarks(g, IM):
            if (lx, ly) in prev and (lx, ly) != (g.qnnpcoyzd.x, g.qnnpcoyzd.y):
                p = path_from(prev, (lx, ly))
                succ.append(([ActionInput(id=a, data={}) for a in p], f"walk:{nm}@{lx},{ly}", len(p)))
        for acts, label, c in succ:
            nx = copy.deepcopy(g)
            ok = True
            for a in acts:
                try:
                    nx.perform_action(a)
                except Exception:
                    ok = False
                    break
                if nx._score != start or nx._state.name == "GAME_OVER":
                    break
            if not ok:
                continue
            if nx._score > start:
                print(json.dumps({"result": "CLEARED", "direction": "UP", "level_from": start,
                                  "level_to": nx._score, "state": nx._state.name,
                                  "macro_steps": len(hist) + 1, "actions": cost + c,
                                  "plan": hist + [label]}), flush=True)
                return
            if nx._score < start or nx._state.name == "GAME_OVER":
                continue
            k = key(nx)
            if k in seen:
                continue
            seen[k] = 1
            q.append((nx, hist + [label], cost + c))
    print(json.dumps({"result": "NO_CLEAR", "expanded": expanded, "states": len(seen),
                      "macro_depth": best_depth, "frontier": len(q)}), flush=True)


if __name__ == "__main__":
    main()
