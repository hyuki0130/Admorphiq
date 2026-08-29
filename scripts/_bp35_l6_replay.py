"""Replay a simulator-found plan for bp35 level 6 on the REAL engine (rule 7g).

The simulator agrees with the engine on 40/40 random trials for this level, and it says level 6 is
winnable inside the engine's own 64-action allowance. A simulator agreeing is not the game clearing:
this plays the real game to level 6 with the shipped harness, then executes the plan action by action
and prints the resulting level number.

⛔ The test is `levels_completed > 5`, never `!= 5` — a collapse back to level 0 and a clear look
identical to a boolean (rule 7f).

Expected feedback: `levels_completed` printing 6 proves the plan clears the level and that the
toggle-click vocabulary is what the tool is missing. Anything else means the simulator's agreement
was shallower than the differential test suggested, and the plan is worthless.

Usage: _bp35_l6_replay.py <seed_for_the_solver> [cap]
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 3_000_000

    import contextlib
    import io

    import _bp35_l6_solve as solver
    from _bp35_sim import load_module, make_level  # noqa: E402

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        solver.solve(seed, cap)
    res = json.loads(buf.getvalue().strip().splitlines()[-1])
    if not res.get("plan"):
        print(json.dumps({"seed": seed, "plan": None, "note": "solver found nothing"}))
        return
    plan = res["plan"]
    print(f"# plan of {len(plan)} actions from seed {seed}", flush=True)

    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.types import ActionType, GameAction

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    steps = 0
    while steps < 4000 and int(getattr(obs, "levels_completed", 0) or 0) < 5:
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        steps += 1
        if steps % 100 == 0:
            print(f"# reaching level 6: {steps} actions, "
                  f"levels_completed={getattr(obs, 'levels_completed', 0)}", flush=True)
    start_lvl = int(getattr(obs, "levels_completed", 0) or 0)
    print(f"# handover at {steps} actions, levels_completed={start_lvl}", flush=True)
    if start_lvl != 5:
        print(json.dumps({"seed": seed, "reached": start_lvl, "cleared": False,
                          "note": "never reached level 6"}))
        return

    m = load_module()
    _, sim = make_level(m, 6)
    scene = env._game.oztjzzyqoek
    print(f"# engine player={scene.twdpowducb.qumspquyus} cam={scene.camera.rczgvgfsfb[1]} "
          f"budget={env._game.hbqwwgceeqp}; sim player=({sim.px},{sim.py}) cam={sim.cam_y}",
          flush=True)

    drift = None
    for i, a in enumerate(plan):
        if a == "L":
            act = agent._convert(GameAction.simple(ActionType(3)))
            sim.move(False)
            obs = env.step(act)
        elif a == "R":
            act = agent._convert(GameAction.simple(ActionType(4)))
            sim.move(True)
            obs = env.step(act)
        else:
            gx, gy = (int(v) for v in a[1:].split(","))
            sx, sy = sim.screen_xy(gx, gy)
            act = agent._convert(GameAction.coordinate(int(sx), int(sy)))
            sim.click_cell(gx, gy)
            obs = env.step(act, data=act.action_data.model_dump())
        sc = env._game.oztjzzyqoek
        ep = sc.twdpowducb.qumspquyus
        if drift is None and (ep[0], ep[1]) != (sim.px, sim.py):
            drift = (i, a, (ep[0], ep[1]), (sim.px, sim.py))
        lvl = int(getattr(obs, "levels_completed", 0) or 0)
        if i % 10 == 0 or lvl > start_lvl:
            print(f"# {i:3d} {a:8s} engine={ep} sim=({sim.px},{sim.py}) "
                  f"lvl={lvl} used={env._game.hbqwwgceeqp} state={obs.state}", flush=True)
        if lvl > start_lvl:
            break

    lvl = int(getattr(obs, "levels_completed", 0) or 0)
    print(json.dumps({"seed": seed, "plan_len": len(plan), "start_level": start_lvl,
                      "end_level": lvl, "cleared": lvl > start_lvl,
                      "actions_on_level": env._game.hbqwwgceeqp,
                      "first_drift": drift, "state": str(obs.state)}))


if __name__ == "__main__":
    main()
