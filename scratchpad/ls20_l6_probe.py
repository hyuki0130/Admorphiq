"""Characterize L6 (multi-goal) ground truth: goal count + per-goal required
tokens, push-walls, movers, refills, start token, life. Drives L1-L5 with the
(now L5-clearing) adapter to reach L6."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from arc_agi import Arcade, OperationMode
from arcengine import GameAction
from admorphiq.adapters25.ls20 import Adapter


def dump(g, tag):
    out = {"tag": tag}
    out["avatar"] = (g.gudziatsk.x, g.gudziatsk.y)
    out["token(sh,co,ro)"] = (g.fwckfzsyc, g.hiaauhahz, g.cklxociuu)
    goals = []
    for i, gg in enumerate(g.plrpelhym):
        goals.append({
            "cell": (gg.x, gg.y),
            "req(sh,co,ro)": (g.ldxlnycps[i], g.yjdexjsoa[i], g.ehwheiwsk[i]),
            "satisfied": g.lvrnuajbl[i],
        })
    out["goals"] = goals
    out["n_pushwalls"] = len(g.hasivfwip)
    out["n_movers"] = len(g.wsoslqeku)
    out["refills"] = [(s.x, s.y) for s in g.current_level.get_sprites_by_tag("npxgalaybz")]
    changers = {}
    for tag_c, kind in (("ttfwljgohq", "shape"), ("soyhouuebz", "color"), ("rhsxkxzdjz", "rot")):
        for s in g.current_level.get_sprites_by_tag(tag_c):
            changers[f"{s.x},{s.y}"] = kind
    out["changers"] = changers
    out["life_current/full/decr"] = (g._step_counter_ui.current_steps,
                                     g._step_counter_ui.osgviligwp, g._step_counter_ui.efipnixsvl)
    return out


def main():
    ar = Arcade(operation_mode=OperationMode.OFFLINE)
    env = ar.make("ls20")
    obs = env.observation_space
    g = env._game
    adapter = Adapter(giveup=8000)
    steps = 0
    dumped = False
    while steps < 8000:
        if obs.levels_completed >= 5 and not dumped:
            # entered L6; settle a couple moves then dump
            for _ in range(3):
                obs = env.step(GameAction.ACTION1)
                steps += 1
            info = dump(g, f"L6 levels_completed={obs.levels_completed}")
            print(json.dumps(info, indent=2))
            Path("scratchpad/ls20_l6_gt.json").write_text(json.dumps(info, indent=2))
            dumped = True
            break
        if adapter.is_done([], obs):
            break
        a = adapter.choose_action([], obs)
        obs = env.step(a, data=a.action_data.model_dump()) if a.is_complex() else env.step(a)
        steps += 1
        if obs is None:
            print("obs None @", steps); break
    print("reached levels_completed:", obs.levels_completed if obs else "?", "@", steps)


if __name__ == "__main__":
    main()
