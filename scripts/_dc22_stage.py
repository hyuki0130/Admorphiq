"""dc22 level 6 — staged engine BFS: reach a target cell (or clear the level).

Purpose: dc22's last level is a chain of gated mechanics (bar-staircase button, tewfut
teleport button, two piyqze keys, four pressure plates gating four crane buttons, a crane
that carries a walkable 20x20 platform).  A blind search cannot cross it, but each LEG is
short.  This searches one leg at a time with the REAL engine: actions = the four moves plus
one click per LIVE sys_click sprite; state = full board digest + mover cell.

Varying parameter FIRST = stage index (0..N).  Prints ONE JSON line.
Rule 7f: any level change is reported with DIRECTION and the resulting level number.
"""
import sys, json, copy, collections, hashlib, importlib.util

SRC = "environment_files/dc22/fdcac232/dc22.py"


def load():
    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dc22mod"] = m
    spec.loader.exec_module(m)
    return m


def live_clicks(g, IM):
    out = []
    for s in g.current_level.get_sprites_by_tag("sys_click"):
        if s.interaction in (IM.REMOVED, IM.INVISIBLE) or not s.is_visible:
            continue
        px = s.render()
        done = False
        for yy in range(px.shape[0]):
            for xx in range(px.shape[1]):
                if px[yy, xx] >= 0:
                    out.append((s.name, s.x + xx, s.y + yy))
                    done = True
                    break
            if done:
                break
    return out


def key(g):
    parts = [f"{s.name}:{s.x},{s.y},{s.interaction.name}" for s in g.current_level.get_sprites()]
    parts.sort()
    parts.append(f"c:{g.sjixewahg},{g.uxtzlxsiq},{g.svxnnbpjl},{g.ozarnpwde},{g.bbobkhxob}")
    parts.append(f"m:{g.qnnpcoyzd.x},{g.qnnpcoyzd.y}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()


STAGES = [(6, 18), (34, 48), (34, 58), None]  # None = clear the level


def search(m, g, target, max_nodes, start_score):
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode as IM
    seen = {key(g)}
    q = collections.deque([(g, [])])
    exp = 0
    while q and exp < max_nodes:
        st, path = q.popleft()
        exp += 1
        if exp % 200 == 0:
            print(f"    expanded {exp} seen {len(seen)} depth {len(path)}", flush=True)
        acts = [(ActionInput(id=a, data={}), f"A{a}") for a in (1, 2, 3, 4)]
        for (nm, cx, cy) in live_clicks(st, IM):
            acts.append((ActionInput(id=6, data={"x": cx, "y": cy}), f"click:{nm}"))
        for a, lab in acts:
            nx = copy.deepcopy(st)
            try:
                nx.perform_action(a)
            except Exception:
                continue
            if nx._score > start_score:
                return nx, path + [lab], "CLEARED", exp, len(seen)
            if nx._score < start_score or nx._state.name == "GAME_OVER":
                continue
            if target is not None and (nx.qnnpcoyzd.x, nx.qnnpcoyzd.y) == target:
                return nx, path + [lab], "REACHED", exp, len(seen)
            k = key(nx)
            if k in seen:
                continue
            seen.add(k)
            q.append((nx, path + [lab]))
    return None, None, "EXHAUSTED" if not q else "CAPPED", exp, len(seen)


def main():
    upto = int(sys.argv[1]) if len(sys.argv) > 1 else len(STAGES)
    max_nodes = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    m = load()
    g = m.Dc22()
    g.set_level(5)
    start_score = g._score
    total = []
    for i, tgt in enumerate(STAGES[:upto]):
        print(f"[stage {i}] target={tgt} mover={(g.qnnpcoyzd.x, g.qnnpcoyzd.y)}", flush=True)
        g2, path, why, exp, nseen = search(m, g, tgt, max_nodes, start_score)
        print(f"[stage {i}] -> {why} exp={exp} seen={nseen} len={len(path) if path else 0}", flush=True)
        if g2 is None:
            print(json.dumps({"result": "STUCK", "stage": i, "target": tgt, "why": why,
                              "expanded": exp, "states": nseen,
                              "actions_so_far": len(total)}), flush=True)
            return
        total += path
        g = g2
        if why == "CLEARED":
            print(json.dumps({"result": "CLEARED", "direction": "UP",
                              "level_from": start_score, "level_to": g._score,
                              "state": g._state.name, "actions": len(total),
                              "plan": total}), flush=True)
            return
    print(json.dumps({"result": "STAGES_DONE", "actions": len(total),
                      "mover": [g.qnnpcoyzd.x, g.qnnpcoyzd.y], "level": g._score,
                      "plan": total}), flush=True)


if __name__ == "__main__":
    main()
