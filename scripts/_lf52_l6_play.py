"""Play the solved line for lf52 level 6 against the live engine.

⛔ Rule 7g: the source says what is POSSIBLE. An exhaustive search over a model built from
`equnaohchtj.qikmikecdf` / `cfilhtifcb` / `tmhxwcojkh` says level 6 has 935 winning states and a
55-move line that never clicks a cell the camera is not showing. That is a claim about a MODEL.
This replays the line action by action and reports what the ENGINE does with it.

The model is anchored to four independent live measurements before it is trusted: the two
selection markers it predicts (`fozwvlovdui` at grid (2,3) may jump UP over the red pad, the red
pad may jump DOWN over it, and neither of the two isolated greens may move at all) matched the
frame exactly, and ACTION3 was inert while ACTION4 changed the board three times and then stopped
as the carts left the screen.

Coordinates: cell (gx, gy) draws at pixel (gx*6 + ox + 2, gy*6 + 5 + 2) — measured, the pad at
grid (2,3) has its blob centred on (25.5, 19.5) with ox = 5. Only the horizontal offset moves, and
only when a green rides a cart sideways or a pad lands on the cart at (7, 6).

Expected feedback: `cleared` true with `level` 6 is lf52's sixth level solved and names the exact
action sequence. A desync reports the FIRST step whose live board disagreed with the model, which
is the one fact a tool author needs.
"""
from __future__ import annotations

import json
import sys

import numpy as np

GREEN, RED = 14, 8
START_LEVEL = 5
DRIVE_ACTION = {(0, -1): 1, (0, 1): 2, (-1, 0): 3, (1, 0): 4}
LINE = json.load(open(__file__.rsplit("/", 1)[0] + "/_lf52_l6_line.json"))["steps"]


def reach(seed: int):
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("lf52"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    frames = [obs]
    for i in range(2500):
        if int(getattr(obs, "levels_completed", 0) or 0) >= START_LEVEL:
            break
        if i % 300 == 0:
            print(f"# seed {seed} reach action {i}", file=sys.stderr, flush=True)
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
    if int(getattr(obs, "levels_completed", 0) or 0) < START_LEVEL:
        return None
    return env, agent, obs


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    # seed 1 plays the line as solved; other seeds shift the click point inside the cell, because
    # a cell is six pixels wide and which pixel the engine treats as "inside" is not measured.
    dot = [(2, 2), (3, 3), (2, 3), (3, 2), (1, 2), (4, 3), (2, 4), (3, 1)][(seed - 1) % 8]
    got = reach(seed)
    if got is None:
        print(json.dumps({"seed": seed, "error": "did not reach level 6"}), flush=True)
        return
    env, agent, obs = got
    from admorphiq.types import ActionType as AT
    from admorphiq.types import GameAction

    state = {"obs": obs, "last": np.array(obs.frame[-1], dtype=np.int16), "n": 0}

    def step(action, data=None):
        state["n"] += 1
        o = env.step(action, data=data) if data else env.step(action)
        state["obs"] = o
        if getattr(o, "frame", None):
            state["last"] = np.array(o.frame[-1], dtype=np.int16)
        return state["last"]

    def click(x, y):
        return step(agent._convert(GameAction.coordinate(int(x), int(y))),
                    data={"x": int(x), "y": int(y)})

    def simple(k):
        return step(agent._convert(GameAction.simple(AT(k))))

    def lvl():
        return int(getattr(state["obs"], "levels_completed", 0) or 0)

    def green():
        return int((state["last"] == GREEN).sum())

    for _ in range(6):
        click(62, 2)
    start_lvl = lvl()
    base = green()
    print(f"# seed {seed} at level {start_lvl} green={base} dot={dot}", file=sys.stderr, flush=True)

    log = []
    desync = None
    for i, st in enumerate(LINE):
        mv, ox = st["mv"], st["ox"]
        g0, p0 = green(), state["last"].tobytes()
        if mv[0] == "drive":
            d = tuple(mv[1])
            simple(DRIVE_ACTION[d])
        else:
            (gx, gy), d = tuple(mv[1]), tuple(mv[2])
            sx, sy = gx * 6 + ox + dot[0], gy * 6 + 5 + dot[1]
            lx, ly = (gx + 2 * d[0]) * 6 + ox + dot[0], (gy + 2 * d[1]) * 6 + 5 + dot[1]
            if not (0 <= sx < 64 and 0 <= sy < 64 and 0 <= lx < 64 and 0 <= ly < 64):
                desync = {"step": i, "why": "offscreen", "move": mv, "ox": ox,
                          "sel": [sx, sy], "land": [lx, ly]}
                break
            click(sx, sy)
            click(lx, ly)
        changed = state["last"].tobytes() != p0
        log.append({"i": i, "mv": mv, "ox": ox, "pads_model": st["pads"], "green": [g0, green()],
                    "changed": changed, "lvl": lvl(), "act": state["n"]})
        if lvl() > start_lvl:
            print(json.dumps({"seed": seed, "cleared": True, "level": lvl(),
                              "actions_on_level": state["n"], "dot": dot,
                              "log": log}), flush=True)
            return
        if not changed:
            desync = {"step": i, "why": "engine refused the move", "move": mv, "ox": ox}
            break
    print(json.dumps({"seed": seed, "cleared": False, "level": lvl(), "dot": dot,
                      "actions_on_level": state["n"], "green": green(),
                      "desync": desync, "log": log[-6:], "played": len(log)}), flush=True)


if __name__ == "__main__":
    main()
