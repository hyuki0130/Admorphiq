"""re86 L5 selection/flood probe (task #84 closing): how does selection behave,
and does the marker reliably return after a recolour flood?

Reach L5, then repeatedly: issue ACTION5 (cycle) and a tiny probe move, recording
which GT sprite moved (= selected) + marker presence. Then drive one piece into
its station to trigger a flood and watch the marker over the next 12 frames while
issuing a NO-OP move (ACTION1 on the frozen selected piece) vs ACTION5. Decides
the closing controller's selection + flood-wait design.
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter
from admorphiq.adapters25.base import canonical_layer

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
MOV_TAG = "0031cppcuvqlbi"


def reach_l5(env, ad):
    obs = env.observation_space
    s = 0
    while s < 6000 and int(getattr(obs, "levels_completed", 0) or 0) < 4 and not ad.is_done([], obs):
        a = ad.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        s += 1
    return obs


def gt(g):
    out = {}
    for s in g.current_level.get_sprites_by_tag(MOV_TAG):
        cols = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        if not cols:
            continue
        out[cols.most_common(1)[0][0]] = (s.y + s.height // 2, s.x + s.width // 2)
    return out


def marker_of(grid):
    for r, row in enumerate(grid):
        for c, v in enumerate(row):
            if v == 0:
                return (r, c)
    return None


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    g = env._game
    ad = Adapter(giveup=6000)
    obs = reach_l5(env, ad)
    if int(getattr(obs, "levels_completed", 0) or 0) != 4:
        print("no L5"); return
    for _ in range(2):
        obs = env.step(A[5])

    print("=== SELECTION CYCLE (ACTION5 then probe UP; which colour moved) ===")
    for k in range(8):
        before = gt(g)
        obs = env.step(A[1])  # probe up
        after = gt(g)
        moved = [c for c in before if c in after and before[c] != after[c]]
        mk = marker_of(canonical_layer(obs))
        mk_col = None
        if mk:
            for c, cen in after.items():
                if abs(cen[0]-mk[0]) <= 15 and abs(cen[1]-mk[1]) <= 15:
                    mk_col = c
        print(f"  k{k}: moved={moved} marker={mk} marker_on=c{mk_col}")
        obs = env.step(A[5])  # cycle

    print("\n=== FLOOD WATCH: drive selected piece DOWN into a station, watch marker ===")
    # cycle so colour-12 (largest) selected, then drive down toward station-8/9
    for _ in range(6):
        mk = marker_of(canonical_layer(obs))
        cur = gt(g)
        if mk and 12 in cur and abs(cur[12][0]-mk[0]) <= 15 and abs(cur[12][1]-mk[1]) <= 15:
            break
        obs = env.step(A[5])
    print(f"  colour-12 selected at {gt(g).get(12)}")
    # drive down + right toward station-8 to force a recolour, then watch 14 frames
    for k in range(30):
        cur = gt(g)
        mk = marker_of(canonical_layer(obs))
        cols = set(cur.keys())
        print(f"  k{k}: colours={sorted(cols)} c12={cur.get(12)} marker={mk}")
        # once 12 disappears (recoloured), issue NO-OP (up) and watch marker return
        if 12 not in cols:
            obs = env.step(A[1])  # no-op wait (frozen piece), NOT cycle
        else:
            obs = env.step(A[2])  # down


if __name__ == "__main__":
    main()
