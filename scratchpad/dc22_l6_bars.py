"""What the 'f' button does to dc22 level 6's moxubw bars, and to the walkable component."""
import sys, collections
sys.path.insert(0, "scratchpad")
from dc22_l6_macro import load, reachable, landmarks, live_buttons


def bars(g, IM):
    out = []
    for s in g.current_level.get_sprites():
        if s.name.startswith("moxubw") and s.interaction != IM.REMOVED:
            out.append((s.name, s.x, s.y, s.width, s.height, s.interaction.name))
    return sorted(out)


def support_row(g, y):
    mv = g.qnnpcoyzd
    return "".join("#" if g.sxnzvaqltp(x, y, mv) is not None else "." for x in range(0, 64))


def main():
    m = load()
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode as IM
    g = m.Dc22()
    g.set_level(5)
    for i in range(9):
        prev = reachable(g)
        print(f"== after {i} 'f' clicks: reachable={len(prev)}  bars={bars(g, IM)}")
        for y in (46, 48, 52, 54, 56, 58, 60):
            print(f"   sup y={y:2d} {support_row(g, y)}")
        g.perform_action(ActionInput(id=6, data={"x": 53, "y": 5}))


if __name__ == "__main__":
    main()
