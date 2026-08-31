"""Isolate the batch driver: identify, then drive straight to plate B (4,6),
printing each batch's plan + reconcile so we see where it diverges from the
working confirmed-hop driver (which reached (4,6) in 11 steps)."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from g50t_l1_solve5 import Solver, reach_l1
from g50t_l1_slam8 import MOVE


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("g50t")
    obs = reach_l1(env, env.observation_space)
    if int(getattr(obs, "levels_completed", 0) or 0) != 1:
        print("no L1"); return
    s = Solver(env)
    s.identify()
    print(f"identify player={s.player_cell} goal={s.goal_cell} steps={s.steps}")
    target = (4, 6)
    for it in range(10):
        if s.player_cell == target:
            print(f"REACHED {target} in {s.steps} steps"); break
        plan = s.plan(s.player_cell, target, enter=target)
        print(f"  iter{it} player={s.player_cell} plan={plan}")
        if not plan:
            print("  no plan"); break
        conf, wall = s.batch_execute(plan)
        print(f"    -> conf={conf} wall={wall} player={s.player_cell} steps={s.steps} blocked={sorted(s.blocked)}")
    print(f"final player={s.player_cell} floor_added_on_plate={sorted(s.floor(s._grid))!=[]}")


if __name__ == "__main__":
    main()
