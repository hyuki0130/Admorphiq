"""Drive the shaft tool through the REAL harness loop and report how deep it gets.

⛔ Not a bespoke driver. Measured three ways a tool's own loop disagrees with the harness — it
resets the tool on a level-up, feeds `observe` only its own transitions, and re-enters `propose`
after every single action — so a probe that runs the tool by hand reports a number the scored
run will not reproduce. This drives `UnifiedAgent`, with the tool set restricted to the one
under test so the reading is about this tool and not about the routing around it.

`--level N` starts at a later board, which is dev-time only: it reaches into the environment to
skip ahead so a deep board can be read without paying for the ones before it. The tool itself
never sees anything but the frame. `--with-default` measures the tool inside the whole registry
instead, which is the number the card is built from.
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "src")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("title", nargs="?", default="bp35")
    ap.add_argument("--cap", type=int, default=1500)
    ap.add_argument("--level", type=int, default=0)
    ap.add_argument("--with-default", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.shaft import ShaftTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(args.title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    if args.level:
        env._game.set_level(args.level)
        obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})

    tools = default_tools() + [ShaftTool()] if args.with_default else [ShaftTool()]
    agent = UnifiedAgent(tools, _no_llm, giveup=args.cap, stall=80, ctx_budget=6000)
    frames = [obs]
    levels = base = int(getattr(obs, "levels_completed", 0) or 0)
    marks: list[tuple[int, int]] = []
    picks: dict[str, int] = {}
    restarts = 0
    was_over = False
    step = 0
    for step in range(args.cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        picks[str(agent._current)] = picks.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        over = "GAME_OVER" in str(getattr(obs, "state", ""))
        if over and not was_over:
            restarts += 1
        was_over = over
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
        if args.verbose:
            print(f"  {step:4d} {act} lvl={now} state={getattr(obs, 'state', '')}")
    print(f"{args.title} from level {args.level}: {levels - base} levels in {step + 1} actions")
    print(f"   clears at {marks}   restarts={restarts}")
    print(f"   who acted: {dict(sorted(picks.items(), key=lambda kv: -kv[1])[:4])}")


if __name__ == "__main__":
    main()
