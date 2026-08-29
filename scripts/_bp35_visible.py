"""Was the thing that killed crag VISIBLE in the frame before it committed?

The census (`scripts/_bp35_census.py`) settled the first half: on all five bp35 boards that carry
spikes, colour **11** is painted by EVERY lethal kind and by NO safe kind. It is the invariant —
colour 0 is also exclusive but renders zero pixels on board 3, and colour 15 is shared with the
breakable kinds there. So lethality IS distinguishable by colour.

⛔ That is not yet the answer, because bp35 is a SCROLLING SHAFT. A spike below the camera window
cannot be read before contact however distinctive it is, and the census already shows board 3
drawing only 2 pixels of colour 11 for 16 lethal cells — those two being the player's own facing
accent, which uses the same colour. So the question that decides whether the +0.0043 is reachable
is this one: at the frame BEFORE each fatal action, was any lethal pixel on screen at all?

Reports, per death: the colour-11 pixel count in the previous frame, the count EXCLUDING the
player's own tile (the one confound — the player's accent is colour 11 too), and where the body
was. `levels_completed` is a NUMBER. Scorer's own agent factory, scorer's own loop.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

LETHAL_COLOUR = 11


def main() -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction, GameState

    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
    spec = importlib.util.spec_from_file_location(
        "score_eff", Path(__file__).resolve().parent / "score_efficiency.py")
    se = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(se)

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("bp35"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    game = getattr(env, "_game", None) or getattr(env, "game", None)

    def grid(o):
        f = getattr(o, "frame", None)
        if f is None:
            return None
        a = np.asarray(f)
        return a[-1] if a.ndim == 3 else a

    def body():
        try:
            p = game.oztjzzyqoek.twdpowducb.qumspquyus
            return (int(p[0]), int(p[1]))
        except Exception:
            return None

    agent = se._make_agent("unified", info.game_id)
    restart_on_game_over = bool(getattr(agent, "restart_on_game_over", False))
    levels = int(getattr(obs, "levels_completed", 0) or 0)
    start = levels
    prev_count = int(getattr(game, "hbqwwgceeqp", -1))
    deaths: list[dict] = []
    prev_grid = grid(obs)
    prev_body = body()
    step = 0

    for step in range(cap):
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        if obs is None:
            break
        now = int(getattr(obs, "levels_completed", levels) or 0)
        count = int(getattr(game, "hbqwwgceeqp", -1))
        if count < prev_count and now == levels:
            kind = "CLOCK" if prev_count in (64, 128, 192) else "SPIKE"
            seen = total = -1
            if prev_grid is not None:
                mask = prev_grid == LETHAL_COLOUR
                total = int(mask.sum())
                # The player's own facing accent is colour 11 too; blank its tile out. The body
                # is in GAME cells of 6 px; blanking a generous 8x8 around it cannot hide a
                # spike tile that is not adjacent, and adjacency is exactly the case that matters.
                seen = total
                if prev_body is not None:
                    m2 = mask.copy()
                    ys, xs = np.nonzero(m2)
                    if ys.size:
                        py = prev_body[1] * 6 - int(game.oztjzzyqoek.camera.rczgvgfsfb[1])
                        px = prev_body[0] * 6
                        near = (abs(ys - py) <= 8) & (abs(xs - px) <= 8)
                        seen = int(total - near.sum())
            deaths.append({"at_action": step + 1, "levels_completed": levels, "kind": kind,
                           "counter_at_death": prev_count,
                           "lethal_pixels_in_prev_frame": total,
                           "lethal_pixels_excluding_body_tile": seen,
                           "body": list(prev_body) if prev_body else None})
        prev_count = count
        prev_grid = grid(obs)
        prev_body = body()
        levels = now
        if getattr(obs, "state", None) == GameState.WIN:
            break
        if getattr(obs, "state", None) == GameState.GAME_OVER:
            if not restart_on_game_over:
                break
            obs = env.step(GameAction.RESET)
            if obs is None:
                break
            prev_grid = grid(obs)
            prev_body = body()

    spikes = [d for d in deaths if d["kind"] == "SPIKE"]
    blind = [d for d in spikes if d["lethal_pixels_excluding_body_tile"] == 0]
    print(json.dumps({
        "levels_completed_start": start, "levels_completed_end": levels,
        "greater_than_start": levels > start, "actions": step + 1,
        "n_deaths": len(deaths), "n_spike_deaths": len(spikes),
        "spike_deaths_with_NO_lethal_pixel_visible": len(blind),
        "deaths": deaths,
    }))


if __name__ == "__main__":
    main()
