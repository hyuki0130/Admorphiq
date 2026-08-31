"""dc22 level 6 — the island structure: every walkable component at bar phase 0..5."""
import sys, collections
sys.path.insert(0, "scratchpad")
from dc22_l6_macro import load
from dc22_l6_phase import maps

DIRS = [(0, -2), (0, 2), (-2, 0), (2, 0)]


def main():
    m = load()
    from arcengine.base_game import ActionInput
    from arcengine.sprites import InteractionMode as IM
    g = m.Dc22()
    g.set_level(5)
    lm = {}
    for s in g.current_level.get_sprites():
        if s.interaction == IM.REMOVED:
            continue
        if set(s.tags) & {"tewfut", "piyqze", "njvd-rolo", "goknoi"}:
            lm.setdefault((s.x, s.y), []).append(s.name)
    for p in range(6):
        S, B = maps(g)
        ok = {c for c in S if c not in B}
        seen = set()
        comps = []
        for c in sorted(ok):
            if c in seen:
                continue
            comp = {c}
            st = [c]
            seen.add(c)
            while st:
                cur = st.pop()
                for d in DIRS:
                    n = (cur[0] + d[0], cur[1] + d[1])
                    if n in ok and n not in seen:
                        seen.add(n)
                        comp.add(n)
                        st.append(n)
            comps.append(comp)
        print(f"=== phase {p}: {len(comps)} components")
        for comp in sorted(comps, key=len, reverse=True):
            xs = [c[0] for c in comp]; ys = [c[1] for c in comp]
            marks = sorted({n for c in comp for n in lm.get(c, [])})
            print(f"   size {len(comp):3d}  x{min(xs)}-{max(xs)} y{min(ys)}-{max(ys)}  landmarks={marks}")
        g.perform_action(ActionInput(id=6, data={"x": 53, "y": 5}))


if __name__ == "__main__":
    main()
