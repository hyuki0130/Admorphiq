"""Execute a joint-BFS action path on the REAL dc22 engine and report the result.

Rule 7f: level changes reported with DIRECTION and the resulting number.
"""
import sys, json
sys.path.insert(0, "scratchpad")
from dc22_l6_macro import load

F = (53, 5)
C = (48, 23)
PATH = json.loads(sys.argv[1])["path"] if len(sys.argv) > 1 else []


def run(g, path, AI, IM, label=""):
    for i, lab in enumerate(path):
        if lab.startswith("A"):
            a = AI(id=int(lab[1]), data={})
        elif lab == "click_f":
            a = AI(id=6, data={"x": F[0], "y": F[1]})
        elif lab == "click_c":
            a = AI(id=6, data={"x": C[0], "y": C[1]})
        else:
            raise ValueError(lab)
        g.perform_action(a)
        if g._score != 0 or g._state.name == "GAME_OVER":
            print(f"  !! at step {i} ({lab}) level={g._score} state={g._state.name}", flush=True)
            return False
    print(f"  [{label}] done {len(path)} actions, mover={(g.qnnpcoyzd.x, g.qnnpcoyzd.y)}", flush=True)
    return True


def main():
    m = load()
    from arcengine.base_game import ActionInput as AI
    from arcengine.sprites import InteractionMode as IM
    g = m.Dc22()
    g.set_level(5)
    ok = run(g, PATH, AI, IM, "to d-key")
    live = [s.name for s in g.current_level.get_sprites_by_tag("sys_click")
            if s.interaction not in (IM.REMOVED, IM.INVISIBLE)]
    piy = [(s.name, s.x, s.y, s.interaction.name) for s in g.current_level.get_sprites_by_tag("piyqze")]
    print(json.dumps({"ok": ok, "mover": [g.qnnpcoyzd.x, g.qnnpcoyzd.y],
                      "live_buttons": live, "piyqze": piy, "level": g._score,
                      "state": g._state.name}), flush=True)


if __name__ == "__main__":
    main()
