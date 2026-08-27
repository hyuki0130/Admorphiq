"""Drive the assemble tool against the live games — alone, inside the real harness, or swept.

Three modes, and the middle one is the load-bearing one:

* ``assemble_probe.py <game> [cap]`` — the tool ALONE. Cheap, but it answers an empty proposal
  with an inert corner click, which the real loop does not.
* ``assemble_probe.py --harness <game> [cap]`` — the REAL ``UnifiedAgent`` with the full tool set
  and no LLM, printing which tool owns each step. ⛔ This is the number that counts. MEASURED
  2026-08-27: the tool alone cleared 6 levels while the harness cleared ONE, and the whole gap was
  the loop substituting a probe action for the tool's empty proposal — a fault invisible to the
  alone-mode driver, which substitutes a harmless one.
* ``assemble_probe.py --sweep [cap]`` — the bid on every sample game. Selectivity outranks depth:
  a tool that bids on a board it cannot solve takes that game away from whatever could.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from admorphiq.tools.assemble import JigsawAssembleTool  # noqa: E402


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


def run_alone(title: str, cap: int) -> None:
    from arcengine import GameAction

    env = _env(title)
    obs = env.reset()
    tool = JigsawAssembleTool()
    simple = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
              4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    done = 0
    acted = 0
    marks = []
    print(f"  detect={tool.detect([], obs):.2f}")
    idle = 0
    while acted < cap and idle < 4:
        steps = tool.propose([], obs)
        if not steps:
            # A cleared board only turns into the next level when something acts; a corner click
            # is the cheapest thing that cannot select a piece.
            idle += 1
            obs = env.step(GameAction.ACTION6, data={"x": 0, "y": 0})
            acted += 1
            new = int(getattr(obs, "levels_completed", done) or 0)
            if new != done:
                marks.append((new, acted))
                print(f"  level {new}: cleared at {acted} actions")
                done = new
            continue
        idle = 0
        for aid, xy in steps:
            if aid == 6 and xy is not None:
                obs = env.step(GameAction.ACTION6, data={"x": int(xy[0]), "y": int(xy[1])})
            else:
                obs = env.step(simple[aid])
            acted += 1
            new = int(getattr(obs, "levels_completed", done) or 0)
            if new != done:
                marks.append((new, acted))
                print(f"  level {new}: cleared at {acted} actions")
                done = new
                break
        state = str(getattr(obs, "state", ""))
        if "GAME_OVER" in state or "WIN" in state:
            print(f"  {state} at {acted}")
            break
    print(f"{title} assemble: {done} levels in {acted} actions  marks={marks}")


def run_harness(title: str, cap: int) -> None:
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(_messages: object) -> str:
        raise RuntimeError("LLM-free deployment")

    env = _env(title)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    levels = 0
    marks: list[tuple[int, int, str | None]] = []
    runs: list[list] = []
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        # Which tool owns this turn — a tool that clears a level and then loses every remaining
        # step to the general searcher looks exactly like a tool that cannot go deeper.
        cur = agent._current
        if runs and runs[-1][0] == cur:
            runs[-1][1] += 1
        else:
            runs.append([cur, 1])
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        new = int(getattr(obs, "levels_completed", levels) or 0)
        if new != levels:
            marks.append((new, step + 1, cur))
            print(f"  level {new} cleared at step {step + 1} by {cur}")
            levels = new
        if "WIN" in str(getattr(obs, "state", "")):
            print(f"  WIN at {step + 1}")
            break
    print(f"{title} harness: {levels} levels  marks={marks}")
    print("  owners: " + " ".join(f"{n}x{c}" for c, n in runs))


def run_sweep(cap: int) -> None:
    """The tool's own bid on every sample game, plus how fast it withdraws from a foreign one."""
    from arcengine import GameAction

    simple = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
              4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    for title in _titles():
        env = _env(title)
        obs = env.reset()
        tool = JigsawAssembleTool()
        best = tool.detect([], obs)
        acted = 0
        while acted < cap:
            conf = tool.detect([], obs)
            best = max(best, conf)
            if conf <= 0.0:
                break
            steps = tool.propose([], obs)
            if not steps:
                break
            for aid, xy in steps:
                if aid == 6 and xy is not None:
                    obs = env.step(GameAction.ACTION6, data={"x": int(xy[0]), "y": int(xy[1])})
                else:
                    obs = env.step(simple[aid])
                acted += 1
            if "GAME_OVER" in str(getattr(obs, "state", "")):
                break
        print(f"  {title:6s} detect={best:.2f} withdrew_after={acted}", flush=True)


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--sweep":
        run_sweep(int(args[1]) if len(args) > 1 else 40)
        return
    if args and args[0] == "--harness":
        run_harness(args[1] if len(args) > 1 else "cn04",
                    int(args[2]) if len(args) > 2 else 600)
        return
    run_alone(args[0] if args else "cn04", int(args[1]) if len(args) > 1 else 400)


if __name__ == "__main__":
    main()
