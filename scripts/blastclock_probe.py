"""Probe for `tools/blastclock.py` — validate the model, play the game, sweep the bids.

Three questions, three subcommands, and the first one is the one that matters:

* `validate <file> <level>` — does the tool's simulator predict the BOARD? It reads the frame, takes
  random presses, and after each one compares the pieces it predicted against the pieces it can see.
  A model of a board that fires on its own clock cannot be checked by "did the level clear"; either
  it reproduces the engine cell-for-cell or the plan it hands over is fiction.
* `play <title> [budget]` — run the tool alone against the real environment and report levels and
  actions per level.
* `sweep [dir]` — every sample game's first frame through `detect`, because a tool that bids on a
  board it cannot solve takes the turn from the tool that can.

The environments directory is chosen with ENVIRONMENTS_DIR (⛔ that exact name — the runner does not
read ARC_ENVIRONMENTS_DIR and setting that one scores zero games while looking healthy).
"""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, "src")

import numpy as np  # noqa: E402


def _frame(obs: Any) -> np.ndarray:
    from admorphiq.tools.slotlaunch import current_frame
    return current_frame(obs)


def _pieces(board: Any) -> set[tuple[Any, tuple[int, int]]]:
    return {(p.mask, p.pos) for p in board.pieces}


def _bind(game: Any, board: Any) -> tuple[list[Any], tuple[int, int]]:
    """Tie each parsed piece to the sprite standing exactly where it is.

    Dev-time only, and the point of the whole probe — the tool never sees a sprite. A re-read of the
    frame can be confused by two pieces jammed corner to corner, and without the engine's own answer
    there is no way to tell a mis-parse from a mis-model. Bound by geometry, so no tag is named.
    """
    sprites = list(game.current_level.get_sprites())
    # A board smaller than the display is letterboxed, so frame coordinates carry an offset. Recover
    # it rather than assuming it: every offset that could bind the first piece is tried, and the one
    # that binds them all is the camera's.
    first = board.pieces[0]
    cands = {(first.pos[0] - s.y, first.pos[1] - s.x)
             for s in sprites if (s.height, s.width) == (first.h, first.w)}
    for off in sorted(cands):
        bound = []
        for p in board.pieces:
            hit = [s for s in sprites
                   if (s.y + off[0], s.x + off[1], s.height, s.width) == (p.pos[0], p.pos[1], p.h, p.w)]
            if len(hit) != 1:
                break
            bound.append(hit[0])
        else:
            return bound, off
    raise SystemExit(f"no camera offset binds {[(p.pos, p.h, p.w) for p in board.pieces]}")


# --- validate ---------------------------------------------------------------

def _load_game(path: str) -> Any:
    from arcengine.base_game import ARCBaseGame
    spec = importlib.util.spec_from_file_location("probe_game", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for obj in vars(mod).values():
        if isinstance(obj, type) and issubclass(obj, ARCBaseGame) and obj is not ARCBaseGame:
            return obj()
    raise SystemExit(f"no game class in {path}")


def validate(path: str, level: int, trials: int, presses: int, seed: int) -> int:
    """Random presses, prediction versus observation, reported as the first divergence."""
    from arcengine.enums import ActionInput, GameAction

    from admorphiq.tools.blastclock import Sim, charges_of, fuse_pieces, read_growth
    from admorphiq.tools.slotlaunch import read_board, reread

    rng = random.Random(seed)
    bad = 0
    for trial in range(trials):
        game = _load_game(path)
        game.set_level(level)
        prev = np.asarray(game.camera.render(game.current_level.get_sprites()))

        def press(aid: int) -> np.ndarray:
            fd = game.perform_action(ActionInput(id=getattr(GameAction, f"ACTION{aid}"), data={}))
            return np.asarray(fd.frame)[-1].astype(np.int64)

        # One press to make the fuses legible, exactly as the tool does.
        now = press(1)
        static = read_board(prev.astype(np.int64))
        if static is None:
            print(f"  level {level}: board does not parse")
            return 1
        board = fuse_pieces(reread(static, now), now)
        charges = read_growth(prev.astype(np.int64), now, board, charges_of(board, now))
        unread = [c for c in charges.values() if not c.ready]
        if unread:
            now2 = press(1)
            board2 = fuse_pieces(reread(static, now2), now2)
            charges = read_growth(now, now2, board2, charges_of(board2, now2))
            board, now = board2, now2
        sim = Sim(board, charges)
        bound, off = _bind(game, board)
        pos = tuple(sim.base)
        held = board.held if board.held is not None else (sim.click[0] if sim.click else 0)
        vel = tuple(0 for _ in range(sim.n))
        tick = 0
        for k in range(presses):
            aid = rng.choice([1, 2, 3, 4])
            pos, held, vel, tick = sim.press(pos, held, vel, tick, (aid, None))
            now = press(aid)
            if game.current_level is None or str(game._state) not in (
                    "GameState.NOT_FINISHED", "NOT_FINISHED"):
                break
            seen = reread(static, now)
            seen = fuse_pieces(seen, now) if seen is not None else None
            if seen is None:
                print(f"  trial {trial} press {k}: board stopped parsing")
                bad += 1
                break
            want = list(pos)
            truth = [(s.y + off[0], s.x + off[1]) for s in bound]
            if want != truth:
                print(f"  trial {trial} press {k} (action {aid}): MODEL MISMATCH")
                print(f"    predicted: {want}")
                print(f"    engine   : {truth}")
                bad += 1
                break
            if sorted(p for _, p in _pieces(seen)) != sorted(want):
                print(f"  trial {trial} press {k}: model exact, the RE-READ disagrees "
                      f"{sorted(p for _, p in _pieces(seen))}")
        else:
            continue
    print(f"validate level {level}: {trials - bad}/{trials} trials exact")
    return 0 if bad == 0 else 1


# --- play -------------------------------------------------------------------

def play(title: str, budget: int) -> int:
    """Drive the tool alone against the real environment."""
    from arc_agi import Arcade, OperationMode

    from admorphiq.tools.blastclock import BlastClockTool

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = BlastClockTool()
    print(f"detect on the first frame: {tool.detect([obs], obs):.3f}")
    queue: list[tuple[int, tuple[int, int] | None]] = []
    levels, marks, step = 0, [], 0
    while step < budget:
        if not queue:
            queue = list(tool.propose([obs], obs))
            if not queue:
                print(f"  no proposal at action {step} (level {levels})")
                break
        aid, xy = queue.pop(0)
        act, data = _to_action(aid, xy)
        obs = env.step(act, data=data) if data else env.step(act)
        step += 1
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step))
            levels = now
            queue = []
        if str(getattr(obs, "state", "")) .endswith("GAME_OVER"):
            print(f"  GAME OVER at action {step}")
            break
    print(f"{title} ALONE: {levels} levels in {step} actions   clears at {marks}")
    return 0


def _to_action(aid: int, xy: tuple[int, int] | None) -> tuple[Any, dict[str, int] | None]:
    """A tool Step in the same form the harness hands the environment."""
    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction
    if xy is not None:
        act = AdmorphiqAdapter._convert_action(GameAction.coordinate(int(xy[0]), int(xy[1])))
        return act, act.action_data.model_dump() if getattr(act, "action_data", None) else None
    return AdmorphiqAdapter._convert_action(GameAction.simple(ActionType(aid))), None


# --- sweep ------------------------------------------------------------------

def sweep(root: str, frames: int = 60, seed: int = 3) -> int:
    """Every sample game through detect, over a walk rather than one frame.

    ⛔ A first-frame sweep is not the selectivity measurement. `detect` reads whatever board is in
    front of it, and a board that does not parse at the start can parse three moves in — which is how
    a tool takes a turn on a game it was measured never to bid on. This walks each game and reports
    the HIGHEST bid seen anywhere along the walk.
    """
    import os
    import random

    from arc_agi import Arcade, OperationMode

    from admorphiq.tools.blastclock import BlastClockTool
    os.environ["ENVIRONMENTS_DIR"] = str(Path(root).resolve())
    rng = random.Random(seed)
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    hits = 0
    for info in sorted(arcade.get_environments(), key=lambda i: (i.title or i.game_id)):
        name = (info.title or info.game_id).lower()
        env = arcade.make(info.game_id)
        obs = env.reset()
        tool = BlastClockTool()
        best, when = 0.0, 0
        for k in range(frames):
            bid = tool.detect([obs], obs)
            if bid > best:
                best, when = bid, k
            simple, click = _availability(obs)
            choices = [(a, None) for a in simple]
            if click:
                choices += [(6, (rng.randrange(64), rng.randrange(64))) for _ in range(2)]
            if not choices:
                break
            act, data = _to_action(*rng.choice(choices))
            obs = env.step(act, data=data) if data else env.step(act)
        if best > 0:
            hits += 1
        print(f"  {name:<14} max {best:.3f} (frame {when})")
    print(f"sweep over {root}, {frames} frames each: {hits} games bid above zero")
    return 0


def _availability(obs: Any) -> tuple[list[int], bool]:
    from admorphiq.tools.base import availability
    return availability(obs)


def harness(title: str, cap: int, drop: list[str]) -> int:
    """The real harness loop, optionally with named tools left out of the registry.

    ⛔ The harness is what is scored, and a tool's own probe disagrees with it in three ways. Dropping
    a tool here is a MEASUREMENT, never a change: the registry file is untouched, the drop lives only
    in this process, and which tool should rank where is not the author's call.
    """
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.blastclock import BlastClockTool

    def _no_llm(*_a: Any, **_k: Any) -> Any:
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    tools = [t for t in default_tools() if t.name not in drop]
    tools.insert(0, BlastClockTool())
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
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
    top = sorted(picks.items(), key=lambda kv: -kv[1])[:4]
    print(f"{title} HARNESS(drop={drop or 'none'}): {levels} levels in {step + 1} actions"
          f"   clears at {marks}")
    print(f"   who acted: {dict(top)}")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "validate":
        path = sys.argv[2]
        level = int(sys.argv[3])
        trials = int(sys.argv[4]) if len(sys.argv) > 4 else 5
        presses = int(sys.argv[5]) if len(sys.argv) > 5 else 25
        seed = int(sys.argv[6]) if len(sys.argv) > 6 else 0
        return validate(path, level, trials, presses, seed)
    if cmd == "play":
        return play(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1500)
    if cmd == "harness":
        return harness(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1500,
                       sys.argv[4].split(",") if len(sys.argv) > 4 else [])
    if cmd == "sweep":
        return sweep(sys.argv[2] if len(sys.argv) > 2 else "environment_files",
                     int(sys.argv[3]) if len(sys.argv) > 3 else 60)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
