"""dc22 level 6 — randomised search over MOVES + clicks on LIVE sys_click sprites only.

Purpose: every previous dc22 sweep clicked fixed board cells while the mover stood still.
dc22's crane buttons are `buezna` sprites that are INVISIBLE unless the mover stands on the
matching `njvd-rolo` pressure plate, so a click taken from a fixed position is a no-op by
construction.  This probe re-runs blind search with the action set the game actually offers
at each instant: the four moves, plus one click per currently-live sys_click sprite.

Varying parameter FIRST = seed.  Prints ONE JSON line.
Rule 7f: a level change is reported with its DIRECTION and the resulting level number.
"""
import sys, json, random, importlib.util, hashlib

SRC = "environment_files/dc22/fdcac232/dc22.py"


def load():
    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dc22mod"] = m
    spec.loader.exec_module(m)
    return m


def live_clicks(g, InteractionMode):
    out = []
    for s in g.current_level.get_sprites_by_tag("sys_click"):
        if s.interaction in (InteractionMode.REMOVED, InteractionMode.INVISIBLE):
            continue
        if not s.is_visible:
            continue
        px = s.render()
        for yy in range(px.shape[0]):
            done = False
            for xx in range(px.shape[1]):
                if px[yy, xx] >= 0:
                    out.append((s.x + xx, s.y + yy, s.name))
                    done = True
                    break
            if done:
                break
    return out


def boardkey(g):
    parts = []
    for s in g.current_level.get_sprites():
        parts.append(f"{s.name}:{s.x},{s.y},{s.interaction.name}")
    parts.sort()
    parts.append(f"c:{g.sjixewahg},{g.uxtzlxsiq},{g.svxnnbpjl}")
    return hashlib.md5("|".join(parts).encode()).hexdigest()


def main():
    seed = int(sys.argv[1])
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 3000
    rng = random.Random(seed)
    m = load()
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode

    g = m.Dc22()
    g.set_level(5)
    start = g._score
    seen = {boardkey(g)}
    clicks_taken = 0
    button_names = set()
    for i in range(budget):
        opts = [ActionInput(id=a, data={}) for a in (1, 2, 3, 4)]
        lc = live_clicks(g, InteractionMode)
        for (x, y, nm) in lc:
            ai = ActionInput(id=6, data={"x": x, "y": y})
            opts.append(ai)
        a = rng.choice(opts)
        if a.id.value == 6:
            clicks_taken += 1
        try:
            g.perform_action(a)
        except Exception as e:
            print(json.dumps({"seed": seed, "result": "ERROR", "at": i, "err": str(e)[:120]}), flush=True)
            return
        for (_, _, nm) in lc:
            button_names.add(nm)
        seen.add(boardkey(g))
        lvl = g._score
        if lvl > start:
            print(json.dumps({"seed": seed, "result": "CLEARED", "direction": "UP",
                              "level_from": start, "level_to": lvl, "actions": i + 1,
                              "state": g._state.name}), flush=True)
            return
        if lvl < start:
            print(json.dumps({"seed": seed, "result": "FELL_BACK", "direction": "DOWN",
                              "level_from": start, "level_to": lvl, "actions": i + 1}), flush=True)
            return
        if g._state.name == "GAME_OVER":
            g.perform_action(ActionInput(id=0, data={}))
            g.set_level(5)
    print(json.dumps({"seed": seed, "result": "NO_CLEAR", "level": g._score,
                      "actions": budget, "distinct_boards": len(seen),
                      "clicks_taken": clicks_taken,
                      "buttons_seen": sorted(button_names)}), flush=True)


if __name__ == "__main__":
    main()
