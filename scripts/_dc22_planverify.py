"""Execute the dc22 level-6 model plan on the REAL engine and report whether it CLEARS.

Purpose: the plan comes from an analytic mirror of the engine's predicates; only a run
says what happens (rule 7g).  Rule 7f: the level change is reported with its DIRECTION and
the resulting level number.  Varying parameter FIRST = plan file path.
"""
import sys, json, importlib.util

SRC = "environment_files/dc22/fdcac232/dc22.py"


def load():
    spec = importlib.util.spec_from_file_location("dc22mod", SRC)
    m = importlib.util.module_from_spec(spec)
    sys.modules["dc22mod"] = m
    spec.loader.exec_module(m)
    return m


def first_pixel(s):
    px = s.render()
    for y in range(px.shape[0]):
        for x in range(px.shape[1]):
            if px[y, x] >= 0:
                return (s.x + x, s.y + y)
    return None


def main():
    planfile = sys.argv[1]
    plan = json.load(open(planfile))["plan"]
    m = load()
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode as IM
    g = m.Dc22()
    g.set_level(5)
    start = g._score

    coords = {}
    for s in g.current_level.get_sprites_by_tag("sys_click"):
        kind = next((k for k in ("up", "dowlja", "lersnf", "riidpd", "grawwq") if k in s.tags), None)
        if kind:
            coords["crane_" + ("grab" if kind == "grawwq" else kind)] = first_pixel(s)
        elif "tewfut-color-buezna" in s.tags:
            coords["click_d"] = first_pixel(s)
    coords["click_f"] = (53, 5)
    coords["click_c"] = (48, 23)
    print("click coords:", coords, flush=True)

    for i, lab in enumerate(plan):
        if lab.startswith("A"):
            a = ActionInput(id=int(lab[1]), data={})
        else:
            xy = coords[lab]
            a = ActionInput(id=6, data={"x": xy[0], "y": xy[1]})
        g.perform_action(a)
        if i % 10 == 0 or i == len(plan) - 1:
            print(f"  step {i+1}/{len(plan)} {lab:14s} mover={(g.qnnpcoyzd.x, g.qnnpcoyzd.y)} "
                  f"crane=({g.sjixewahg},{g.uxtzlxsiq}) att={g.svxnnbpjl} level={g._score}", flush=True)
        if g._score > start:
            print(json.dumps({"result": "CLEARED", "direction": "UP", "level_from": start,
                              "level_to": g._score, "state": g._state.name,
                              "actions": i + 1, "plan_len": len(plan)}), flush=True)
            return
        if g._score < start:
            print(json.dumps({"result": "FELL_BACK", "direction": "DOWN", "level_to": g._score,
                              "actions": i + 1}), flush=True)
            return
        if g._state.name == "GAME_OVER":
            print(json.dumps({"result": "GAME_OVER", "actions": i + 1, "at": lab}), flush=True)
            return
    print(json.dumps({"result": "PLAN_DONE_NO_CLEAR", "level": g._score,
                      "mover": [g.qnnpcoyzd.x, g.qnnpcoyzd.y], "actions": len(plan)}), flush=True)


if __name__ == "__main__":
    main()
