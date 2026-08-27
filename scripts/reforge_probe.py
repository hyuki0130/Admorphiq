"""Drive the reforge tool against the live games — alone, per level, inside the harness, or swept.

Four modes:

* ``reforge_probe.py <game> [cap]`` — the tool ALONE from level one.
* ``reforge_probe.py --level <game> <index> [cap]`` — start ON one level, so a deep level can be
  measured without paying for the levels before it. This is what a DEPTH tool needs: the levels
  that matter here are the last ones, and reaching them honestly costs hundreds of actions every
  time the model changes. It jumps by asking the loaded game to set its own level, which is a
  DEV-time reach into the engine and is why it lives in the probe and not in the tool.
* ``reforge_probe.py --harness <game> [cap]`` — the REAL ``UnifiedAgent`` with the full tool set
  and no LLM. ⛔ This is the number that counts; the tool alone answers an empty proposal
  differently from the loop.
* ``reforge_probe.py --sweep [cap]`` — the bid on every sample game. A tool that bids on a board
  it cannot solve takes that game away from whatever could.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.reforge import ReforgeTool, parse_board  # noqa: E402


def _env(title: str):
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    return arcade.make(info.game_id)


def _titles() -> list[str]:
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    return sorted({(i.title or i.game_id).lower() for i in arcade.get_environments()})


def _drive(env, obs, tool, cap: int, base: int) -> tuple[int, int]:
    """Run the tool until it stops proposing or the cap is spent. -> (levels, actions)."""
    from arcengine import GameAction
    simple = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
              4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    done, acted, idle = base, 0, 0
    while acted < cap and idle < 3:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            continue
        idle = 0
        for aid, _xy in steps:
            if aid not in simple:
                continue
            obs = env.step(simple[aid])
            acted += 1
            new = int(getattr(obs, "levels_completed", done) or 0)
            if new != done:
                print(f"  level {new}: cleared at {acted} actions "
                      f"(state={getattr(obs, 'state', '?')})")
                done = new
                tool.reset()
            if acted >= cap:
                break
    return done, acted


def run_alone(title: str, cap: int) -> None:
    env = _env(title)
    obs = env.reset()
    tool = ReforgeTool()
    print(f"  detect={tool.detect([], obs):.2f}")
    done, acted = _drive(env, obs, tool, cap, 0)
    print(f"{title} ALONE: {done} levels in {acted} actions")


def run_level(title: str, index: int, cap: int) -> None:
    env = _env(title)
    obs = env.reset()
    env._game.set_level(index)
    # RESET here would be read as a fresh game and send us back to level one, so the level is
    # entered with the one action that touches nothing: the hand-over to the next piece.
    obs = env.step(__import__("arcengine").GameAction.ACTION5)
    grid = obs.frame[-1]
    board = parse_board(__import__("numpy").array(grid, dtype="int16"))
    if board is None:
        print(f"  level {index}: board UNREADABLE")
        return
    print(f"  level {index}: {len(board.pieces)} pieces "
          f"{[(p['kind'], p['h'], p['w'], p['colour']) for p in board.pieces]}, "
          f"{len(board.pins)} pins {sorted({c for _, c in board.pins if c is not None})}, "
          f"{len(board.gates)} presses, {len(board.pads)} pads, selected={board.selected}")
    tool = ReforgeTool()
    print(f"  detect={tool.detect([], obs):.2f}")
    # The engine's own clear-count does not know about the jump, so the baseline is read off the
    # jumped-to observation rather than assumed to equal the level index.
    base = int(getattr(obs, "levels_completed", 0) or 0)
    done, acted = _drive(env, obs, tool, cap, base)
    print(f"{title} LEVEL {index}: {'CLEARED' if done > base else 'not cleared'} "
          f"after {acted} actions")


def run_harness(title: str, cap: int) -> None:
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    env = _env(title)
    obs = env.reset()
    # The registry is the integrator's file, not a tool author's, so the tool is appended here
    # instead — this is the same tool set the deployed loop builds, plus the one under test.
    tools = [*default_tools(), ReforgeTool()]
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    picks: dict[str, int] = {}
    marks: list[tuple[int, int]] = []
    levels = step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        picks[str(agent._current)] = picks.get(str(agent._current), 0) + 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
    print(f"{title} HARNESS: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   who acted: {picks}")


def run_sweep(cap: int) -> None:
    """The bid on every sample game, over a WALK and not just the opening frame.

    ⛔ A first-frame sweep is not a selectivity measurement. Every board here starts tidy and
    starts to look like something else only once it has been played — the very reason this tool
    could not be handed its own game was that nothing asked until 180 actions had rearranged it.
    So each game is walked with the simple actions and the HIGHEST bid over the whole walk is what
    gets reported.
    """
    import random
    for title in _titles():
        try:
            from arcengine import GameAction
            simple = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
                      4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
            env = _env(title)
            obs = env.reset()
            tool = ReforgeTool()
            rng = random.Random(7)
            top, when = tool.detect([], obs), 0
            for step in range(cap):
                ids = [a for a in getattr(obs, "available_actions", []) if int(a) in simple]
                if ids:
                    obs = env.step(simple[int(rng.choice(ids))])
                else:
                    obs = env.step(GameAction.ACTION6, data={"x": rng.randrange(64),
                                                             "y": rng.randrange(64)})
                bid = tool.detect([], obs)
                if bid > top:
                    top, when = bid, step + 1
        except Exception as exc:  # noqa: BLE001
            print(f"  {title:6s} ERROR {exc}")
            continue
        flag = "  <-- CLAIMS" if top >= 0.6 else ""
        print(f"  {title:6s} peak bid={top:.2f} over {cap} actions (at {when}){flag}")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--sweep":
        run_sweep(int(args[1]) if len(args) > 1 else 400)
    elif args and args[0] == "--harness":
        run_harness(args[1], int(args[2]) if len(args) > 2 else 1500)
    elif args and args[0] == "--level":
        run_level(args[1], int(args[2]), int(args[3]) if len(args) > 3 else 400)
    else:
        run_alone(args[0], int(args[1]) if len(args) > 1 else 1500)


if __name__ == "__main__":
    main()
