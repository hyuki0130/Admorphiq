"""Offline BFS over dc22 level 6 (index 5), driving the REAL game module.

Purpose: enumerate the reachable state space of the last dc22 level using the
actual engine, restricted to the four movement actions plus clicks on the
sys_click sprites that are live at that moment.  Prints ONE JSON line.
Varying parameter FIRST: max nodes to expand.
"""
import sys, json, copy, hashlib, importlib.util, collections

SRC = "environment_files/dc22/fdcac232/dc22.py"


def load():
    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dc22mod"] = m
    spec.loader.exec_module(m)
    return m


def live_clicks(g):
    """Screen coords of every sys_click sprite that xodizggcom would find."""
    out = []
    from arcengine.sprites import InteractionMode
    for s in g.current_level.get_sprites_by_tag("sys_click"):
        if s.interaction in (InteractionMode.REMOVED, InteractionMode.INVISIBLE):
            continue
        if not s.is_visible:
            continue
        px = s.render()
        hit = None
        for yy in range(px.shape[0]):
            for xx in range(px.shape[1]):
                if px[yy, xx] >= 0:
                    hit = (s.x + xx, s.y + yy)
                    break
            if hit:
                break
        if hit:
            out.append((hit, s.name))
    return out


def key(g):
    parts = []
    for s in sorted(g.current_level.get_sprites(), key=lambda s: (s.name, s.x, s.y)):
        parts.append(f"{s.name}:{s.x},{s.y},{s.interaction.name}")
    parts.append(f"crane:{g.sjixewahg},{g.uxtzlxsiq},{g.svxnnbpjl},{g.fvwekbbhj},{g.ozarnpwde},{g.bbobkhxob}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def main():
    max_nodes = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
    m = load()
    from arcengine.base_game import ActionInput
    from arcengine.enums import GameAction

    g = m.Dc22()
    g.set_level(5)
    start_lvl = g._score

    root = copy.deepcopy(g)
    seen = {key(g): 0}
    q = collections.deque([(root, [])])
    expanded = 0
    best = None
    max_depth = 0
    lost = 0
    while q and expanded < max_nodes:
        st, path = q.popleft()
        expanded += 1
        if len(path) > max_depth:
            max_depth = len(path)
            print(f"depth {max_depth} expanded {expanded} seen {len(seen)}", flush=True)
        acts = [ActionInput(id=i, data={}) for i in (1, 2, 3, 4)]
        for (cx, cy), nm in live_clicks(st):
            a = ActionInput(id=6, data={"x": cx, "y": cy})
            a._label = nm
            acts.append(a)
        for a in acts:
            nxt = copy.deepcopy(st)
            try:
                nxt.perform_action(a)
            except Exception as e:
                continue
            lbl = f"A{a.id}" if a.id != 6 else f"click({a.data['x']},{a.data['y']}:{getattr(a,'_label','')})"
            npath = path + [lbl]
            if nxt._score > start_lvl:
                best = npath
                print(json.dumps({"result": "CLEARED", "from_level": start_lvl,
                                  "to_level": nxt._score, "actions": len(npath),
                                  "path": npath}), flush=True)
                return
            if getattr(nxt._state, "name", "") == "GAME_OVER":
                lost += 1
                continue
            k = key(nxt)
            if k in seen:
                continue
            seen[k] = len(npath)
            q.append((nxt, npath))
    print(json.dumps({"result": "NO_CLEAR", "expanded": expanded, "distinct_states": len(seen),
                      "max_depth": max_depth, "frontier": len(q)}), flush=True)


if __name__ == "__main__":
    main()
