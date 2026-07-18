"""Final movable-9 reshape hypothesis: an ARM TIP poking the obstacle grows the
perpendicular arms. Position the plus so its centre COL overlaps the obstacle
cols (28-35) and it sits ABOVE the obstacle, then push DOWN so the down-arm tip
pokes the obstacle top — dump bbox/arm spans each push to see if any arm GROWS.
Also try the RIGHT-arm-tip variant (centre ROW on obstacle, piece LEFT of it,
push right) for completeness."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _l5_movables, _station_boxes
from admorphiq.adapters25.base import canonical_layer

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}


def marker(g):
    for r, row in enumerate(g):
        for c, v in enumerate(row):
            if v == 0:
                return (r, c)
    return None


def get(g, sb, color):
    for m in _l5_movables(g, set(), sb, subtract_boxes=False):
        if m["color"] == color:
            return m
    return None


def info(m):
    cells = set(m["cells"])
    rs = [r for r, _ in cells]; cs = [c for _, c in cells]
    r0, r1, c0, c1 = min(rs), max(rs), min(cs), max(cs)
    return f"{r1-r0+1}x{c1-c0+1} rows {r0}-{r1} cols {c0}-{c1} px={len(cells)}"


def sel(env, sb, color, obs):
    for _ in range(10):
        g = canonical_layer(obs); mk = marker(g); m = get(g, sb, color)
        if m and mk and abs(m["cen"][0] - mk[0]) <= 15 and abs(m["cen"][1] - mk[1]) <= 15:
            return obs
        obs = env.step(A[5])
    return obs


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    ad = Adapter(giveup=8000)
    obs = env.observation_space
    steps = 0
    while steps < 2500 and int(getattr(obs, "levels_completed", 0) or 0) < 5 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a); steps += 1
    for _ in range(3):
        obs = env.step(A[5])
    g = canonical_layer(obs); _st, sb = _station_boxes(g)
    dm = dict(ad._dir_global)
    up = next(a for a, s in dm.items() if s == (-1, 0))
    down = next(a for a, s in dm.items() if s == (1, 0))
    left = next(a for a, s in dm.items() if s == (0, -1))
    right = next(a for a, s in dm.items() if s == (0, 1))

    obs = sel(env, sb, 9, obs)
    # centre col -> 31 (over the obstacle cols), keep the piece ABOVE the obstacle.
    for _ in range(20):
        g = canonical_layer(obs); m = get(g, sb, 9)
        cs = [c for _, c in m["cells"]]; ccol = (min(cs) + max(cs)) // 2
        if abs(ccol - 31) <= 2:
            break
        obs = env.step(A[left if ccol > 31 else right])
    for _ in range(20):
        g = canonical_layer(obs); m = get(g, sb, 9)
        rs = [r for r, _ in m["cells"]]
        if max(rs) <= 26:  # bottom tip just above the obstacle top (row 28)
            break
        obs = env.step(A[up])
    g = canonical_layer(obs); m = get(g, sb, 9)
    print(f"positioned above obstacle, centre col ~31: {info(m)}")
    print("-- push DOWN (down-arm tip pokes obstacle top) --")
    prev = None
    for k in range(12):
        obs = env.step(A[down])
        g = canonical_layer(obs); m = get(g, sb, 9)
        s = info(m) if m else "GONE"
        if s != prev:
            print(f"  D{k+1}: {s}")
            prev = s


if __name__ == "__main__":
    main()
