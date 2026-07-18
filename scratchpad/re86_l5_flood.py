"""re86 L5 flood-mechanics probe (task #84): what happens during a recolour flood?

Drive colour-11 toward the bottom-left corner station-9, and once a flood starts
(marker hidden), log the sprite's colour + centre each frame while issuing a fixed
wait action. Answers: (a) is the piece move-FROZEN during the flood, or does a wait
action move it? (b) does the flood COMPLETE (colour -> 9) or wedge forever? (c) how
many frames? Run three times with WAIT in {up, down, cycle}.
"""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.re86 import Adapter, _station_boxes
from admorphiq.adapters25.base import canonical_layer
from re86_l5_ctrl import reach_l5, marker_of

A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4, 5: GameAction.ACTION5}
MOV_TAG = "0031cppcuvqlbi"


def sprites(g):
    out = {}
    for s in g.current_level.get_sprites_by_tag(MOV_TAG):
        cols = Counter(int(v) for row in s.pixels for v in row if v not in (-1, 0))
        if not cols:
            continue
        out[cols.most_common(1)[0][0]] = (s.y + s.height // 2, s.x + s.width // 2)
    return out


def run(wait_name):
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("re86")
    g = env._game
    ad = Adapter(giveup=6000)
    obs, steps = reach_l5(env, ad)
    if int(getattr(obs, "levels_completed", 0) or 0) != 4:
        print("no L5"); return
    dirmap = dict(ad._dir_global)
    for _ in range(2):
        obs = env.step(A[5])
    stations, _ = _station_boxes(canonical_layer(obs))
    down = next((a for a, s in dirmap.items() if s == (1, 0)), 2)
    up = next((a for a, s in dirmap.items() if s == (-1, 0)), 1)
    left = next((a for a, s in dirmap.items() if s == (0, -1)), 3)
    wait = {"up": up, "down": down, "cycle": 5}[wait_name]
    print(f"\n===== WAIT={wait_name} (action {wait}) dirmap={dirmap} station9={stations.get(9)} =====")
    # select colour-11
    for _ in range(6):
        cur = sprites(g); mk = marker_of(canonical_layer(obs))
        if mk and 11 in cur and abs(cur[11][0] - mk[0]) <= 15 and abs(cur[11][1] - mk[1]) <= 15:
            break
        obs = env.step(A[5])
    print(f"  colour-11 @ {sprites(g).get(11)} station9={stations.get(9)}")
    # drive it down then left toward station-9, then hit the flood and watch
    flooding = 0
    for k in range(60):
        cur = sprites(g); mk = marker_of(canonical_layer(obs))
        c11 = cur.get(11)
        cols = sorted(cur.keys())
        if mk is None:  # flood
            flooding += 1
            print(f"  k{k} FLOOD#{flooding} colours={cols} c11={c11} c14?={cur.get(14)} -> WAIT")
            obs = env.step(A[wait])
            if flooding > 20:
                break
            continue
        # navigate toward station-9: down until row>=51, then left until col<=18
        s9 = stations.get(9, (54, 5))
        if c11 is None:
            print(f"  k{k} colours={cols} (c11 gone, colour changed)")
            obs = env.step(A[wait]); continue
        if c11[0] < s9[0] - 3:
            obs = env.step(A[down])
        elif c11[1] > 18:
            obs = env.step(A[left])
        else:
            print(f"  k{k} at c11={c11}, pushing into station-9 (left)")
            obs = env.step(A[left])


if __name__ == "__main__":
    for w in ("up", "down", "cycle"):
        run(w)
