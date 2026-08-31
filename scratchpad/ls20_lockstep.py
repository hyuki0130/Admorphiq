"""Lockstep the pixel sim (ls20_sim) vs the live engine on L5, using GT maze
data (isolates PHYSICS correctness from frame-detection). Random walk; compare
avatar pixel pos + token after every action. Dump first divergence.
"""
from __future__ import annotations
import random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter
from ls20_sim import Maze, SimState, step as sim_step

TAG_KIND = {"ttfwljgohq": "shape", "soyhouuebz": "color", "rhsxkxzdjz": "rot"}
A = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3, 4: GameAction.ACTION4}


def build_maze(g) -> Maze:
    lvl = g.current_level
    hard = frozenset((s.x, s.y) for s in lvl.get_sprites_by_tag("ihdgageizm"))
    goal_sp = g.plrpelhym[0]
    goal = (goal_sp.x, goal_sp.y)
    goal_req = (g.ldxlnycps[0], g.yjdexjsoa[0], g.ehwheiwsk[0])
    # mover sprite (exclude it from static changers)
    mover_sprites = {id(m._sprite) for m in g.wsoslqeku}
    changers = []
    for tag, kind in TAG_KIND.items():
        for s in lvl.get_sprites_by_tag(tag):
            if id(s) in mover_sprites:
                continue
            changers.append(((s.x, s.y), kind))
    # refill sprites are pixel-offset; the avatar triggers a sprite at the
    # LATTICE cell whose 5x5 box contains the sprite top-left (mrznumynfe
    # containment). Snap to the avatar lattice (ox,oy from the avatar).
    ax0, ay0 = g.gudziatsk.x, g.gudziatsk.y
    ox, oy = ax0 % 5, ay0 % 5

    def snap(sx, sy):
        return (sx - (sx - ox) % 5, sy - (sy - oy) % 5)

    refills = frozenset(snap(s.x, s.y) for s in lvl.get_sprites_by_tag("npxgalaybz"))
    push = tuple((w.sprite.x, w.sprite.y, w.dx, w.dy, w.width, w.height) for w in g.hasivfwip)
    fj = frozenset(set(hard) | {goal})
    # mover track cells
    if g.wsoslqeku:
        m = g.wsoslqeku[0]
        tr = m.bfdcztirdu
        my = tr.y
        track = tuple(range(tr.x, tr.x + tr.width, 5))
        mover_track = track
    else:
        my = -1
        mover_track = ()
    return Maze(hard, goal, goal_req, tuple(changers), refills, push, fj, mover_track, my)


def gt_state(g) -> tuple:
    return (g.gudziatsk.x, g.gudziatsk.y, g.fwckfzsyc, g.hiaauhahz, g.cklxociuu)


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=6000)
    steps = 0
    while steps < 6000 and obs.levels_completed < 4:
        if adapter.is_done([], obs):
            break
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
    # settle to single-layer
    obs = env.step(GameAction.ACTION1)
    maze = build_maze(g)
    print("goal", maze.goal, "goal_req", maze.goal_req, "changers", maze.changers)
    print("mover_track", maze.mover_track, "my", maze.mover_my, "pushwalls", len(maze.pushwalls))
    print("hard walls", len(maze.hard_walls), "refills", maze.refills)
    # sync sim state from GT
    m = g.wsoslqeku[0]
    s = SimState(g.gudziatsk.x, g.gudziatsk.y, g.fwckfzsyc, g.hiaauhahz, g.cklxociuu,
                 999, frozenset(), m._sprite.x, m._dir)
    print("anchor sim", (s.ax, s.ay), "mover", (s.mx, s.mdir), "token", (s.sh, s.co, s.ro))

    import itertools
    total = 0
    diverged = False
    for seed in range(6):
        rng = random.Random(seed)
        for i in range(120):
            # suppress death so the walk explores all push-walls freely
            g._step_counter_ui.current_steps = g._step_counter_ui.osgviligwp
            s = SimState(s.ax, s.ay, s.sh, s.co, s.ro, 999, frozenset(), s.mx, s.mdir)
            act = rng.choice([1, 2, 3, 4])
            obs = env.step(A[act])
            s = sim_step(maze, s, act)
            eng = gt_state(g)
            sim = (s.ax, s.ay, s.sh, s.co, s.ro)
            total += 1
            if eng != sim:
                mstate = (m._sprite.x, m._dir)
                print(f"[seed{seed} i{i:03d}] act={act} eng={eng} sim={sim} "
                      f"eng_mover={mstate} sim_mover=({s.mx},{s.mdir}) DIVERGE")
                diverged = True
                break
            if obs.state and str(obs.state).endswith("WIN"):
                print(f"[seed{seed} i{i}] engine WIN")
                break
        if diverged:
            break
    print(f"RESULT: {'DIVERGED' if diverged else 'MATCHED'} over {total} lockstep actions")


if __name__ == "__main__":
    main()
