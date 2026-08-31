"""Dump dc22 level 6 walkable components + landmarks, before and after each teleport."""
import sys, importlib.util, collections
sys.path.insert(0, "scratchpad")
from dc22_l6_macro import load, reachable, live_buttons, landmarks


def show(g, IM, tag):
    prev = reachable(g)
    xs = sorted(prev)
    print(f"--- {tag}: mover={(g.qnnpcoyzd.x,g.qnnpcoyzd.y)} reachable={len(prev)} cells")
    rows = collections.defaultdict(list)
    for (x, y) in xs:
        rows[y].append(x)
    for y in sorted(rows):
        r = sorted(rows[y])
        print(f"    y={y:2d}  x={r[0]}..{r[-1]} ({len(r)})")
    lm = [(nm, x, y, (x, y) in prev) for (x, y, nm) in landmarks(g, IM)]
    print("    landmarks:", [(nm, x, y, "REACH" if ok else "-") for nm, x, y, ok in lm])
    print("    live buttons:", live_buttons(g, IM))


def main():
    m = load()
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode as IM
    g = m.Dc22()
    g.set_level(5)
    show(g, IM, "start")
    # walk to the cycle tile and teleport
    from dc22_l6_macro import reachable as R, path_from
    prev = R(g)
    for aid in path_from(prev, (18, 48)):
        g.perform_action(ActionInput(id=aid, data={}))
    show(g, IM, "on tewfutpibpar1 (18,48)")
    g.perform_action(ActionInput(id=6, data={"x": 48, "y": 23}))
    show(g, IM, "after c-teleport #1")
    g.perform_action(ActionInput(id=6, data={"x": 48, "y": 23}))
    show(g, IM, "after c-teleport #2")


if __name__ == "__main__":
    main()
