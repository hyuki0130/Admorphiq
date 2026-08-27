"""Probe the cycle-press tool: per level from a cold start, and through the real harness loop.

Two things are measured, because they answer different questions.

`--levels` drives the tool ALONE against each level of a game, started directly at that level, and
reports whether the level clears and in how many presses. That is the only way to see a level the
harness never reaches, and the only way to see a level's cost separately from the ones before it.

`--harness` runs the tool inside `UnifiedAgent` alongside the registered tool set — the
configuration that is actually scored. It exists because a tool's own probe disagrees with the
harness in ways no author can see from the tool: the tool may never win a turn, or lose the board
on a level-up, or behave differently because the harness re-enters `propose` after every action.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, "src")


def _load_game(directory: str):
    """Import a sample game's own module so a level can be entered directly."""
    source = next(Path(directory).rglob("*.py"))
    spec = importlib.util.spec_from_file_location("probed_game", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for value in vars(module).values():
        if isinstance(value, type) and value.__module__ == "probed_game" and hasattr(value, "step"):
            try:
                return value()
            except Exception:  # noqa: BLE001, S112
                continue
    raise SystemExit(f"no playable game class in {source}")


class _Obs:
    """The observation fields a tool is allowed to read."""

    def __init__(self, frame_data) -> None:
        self.frame = frame_data.frame
        self.state = frame_data.state
        self.levels_completed = frame_data.levels_completed
        self.available_actions = frame_data.available_actions


def levels_probe(directory: str, first: int, last: int, cap: int) -> None:
    from arcengine.enums import ActionInput, GameAction, GameState

    from admorphiq.tools.cyclepress import CyclePressTool

    for index in range(first, last + 1):
        game = _load_game(directory)
        if index - 1 >= len(game._levels):
            break
        game.set_level(index - 1)
        # One click off the board: it costs no press and yields the first frame.
        data = game.perform_action(ActionInput(id=GameAction.ACTION6, data={"x": 0, "y": 0}))
        obs = _Obs(data)
        tool = CyclePressTool()
        frames = [obs]
        verdict, used = "no plan", 0
        for used in range(1, cap + 1):
            steps = tool.propose(frames, obs)
            if not steps:
                verdict = "withdrew"
                used -= 1
                break
            _action, xy = steps[0]
            data = game.perform_action(ActionInput(id=GameAction.ACTION6, data={"x": xy[0], "y": xy[1]}))
            obs = _Obs(data)
            frames.append(obs)
            if data.state == GameState.GAME_OVER:
                verdict = "OVER (budget spent)"
                break
            if game.level_index != index - 1 or data.state == GameState.WIN:
                verdict = "CLEARED"
                break
        else:
            verdict = "cap reached"
        controls = len(tool._perm) + len(tool._inert)
        print(f"  level {index}: {verdict:20s} actions={used:4d}  controls modelled={len(tool._perm)}/{controls}")


def harness_probe(title: str, cap: int, extra: bool) -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.cyclepress import CyclePressTool

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tools = default_tools()
    if extra:
        tools = [CyclePressTool(), *tools]
    agent = UnifiedAgent(tools, _no_llm, giveup=cap, stall=80, ctx_budget=6000)
    frames = [obs]
    picks: dict[str, int] = {}
    marks: list[tuple[int, int]] = []
    levels = 0
    step = 0
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
    top = sorted(picks.items(), key=lambda kv: -kv[1])[:4]
    print(f"{title} HARNESS: {levels} levels in {step + 1} actions   clears at {marks}")
    print(f"   who acted: {dict(top)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title", help="game title prefix, e.g. the first four letters")
    parser.add_argument("--dir", default="")
    parser.add_argument("--cap", type=int, default=1500)
    parser.add_argument("--levels", type=int, nargs=2, metavar=("FIRST", "LAST"))
    parser.add_argument("--harness", action="store_true")
    parser.add_argument("--without", action="store_true", help="harness run with the registered set only")
    args = parser.parse_args()

    if args.levels:
        directory = args.dir or f"environment_files/{args.title}"
        print(f"{args.title} PER-LEVEL (tool alone, cap {args.cap}):")
        levels_probe(directory, args.levels[0], args.levels[1], args.cap)
    if args.harness or not args.levels:
        harness_probe(args.title, args.cap, not args.without)


if __name__ == "__main__":
    main()
