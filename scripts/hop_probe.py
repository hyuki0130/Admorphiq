"""Drive the hop tool against a live game and report how deep it gets."""

from __future__ import annotations

import sys
import time

sys.path.insert(0, "src")

import numpy as np  # noqa: E402

from admorphiq.tools.hop import HopTool, reachable_track, read_board, solve  # noqa: E402


def _describe(obs) -> None:
    board = read_board(np.array(obs.frame[-1]))
    if board is None:
        print("  board: unreadable")
        return
    print(f"  board: pitch={board.pitch} side={board.side} hole={board.hole} "
          f"holes={len(board.holes)} pieces={len(board.pieces)} lead={board.lead} "
          f"track={len(board.track)} carriage={board.carriage} "
          f"reach={len(reachable_track(board))}")
    started = time.time()
    plan = solve(board)
    took = time.time() - started
    if plan is None:
        print(f"  plan: none ({took:.1f}s)")
    else:
        cost = sum(2 if m[0] == "leap" else 1 for m in plan)
        print(f"  plan: {len(plan)} moves, {cost} actions ({took:.1f}s)")


def falsepos() -> None:
    """Ask every public game's FIRST frame whether the hop tool claims it.

    Purpose: a tool that bids on a board it cannot solve steals that game's whole turn. The bid
    must be high on its own board and exactly zero everywhere else.

    Expected feedback: one line per game. Anything but a single non-zero row blocks the tool.
    Each game is asked immediately after boot — an observation does not survive a later make().
    """
    from arc_agi import Arcade, OperationMode

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    seen: set[str] = set()
    rows: list[tuple[str, float]] = []
    for env_info in arcade.get_environments():
        key = (env_info.title or env_info.game_id).lower().split("-")[0][:4]
        if key in seen:
            continue
        env = arcade.make(env_info.game_id)
        if env is None or env.observation_space is None:
            continue
        seen.add(key)
        rows.append((key, HopTool().detect([], env.observation_space)))
    for key, bid in sorted(rows, key=lambda r: -r[1]):
        print(f"  {key}: {bid:.2f}")
    others = [b for k, b in rows if b > 0.0]
    print(f"games={len(rows)}  nonzero={len(others)}  max_elsewhere="
          f"{max([b for k, b in rows if k != 'lf52'] or [0.0]):.2f}")


def main() -> None:
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    if "--falsepos" in sys.argv:
        falsepos()
        return
    title = sys.argv[1] if len(sys.argv) > 1 else "lf52"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    verbose = "-v" in sys.argv
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments() if (i.title or i.game_id).lower().startswith(title))
    env = arcade.make(info.game_id)
    obs = env.reset()
    tool = HopTool()
    acts = {1: GameAction.ACTION1, 2: GameAction.ACTION2, 3: GameAction.ACTION3,
            4: GameAction.ACTION4, 5: GameAction.ACTION5, 7: GameAction.ACTION7}
    print(f"  detect={tool.detect([], obs):.2f}  human={list(getattr(info, 'baseline_actions', None) or [])}")
    _describe(obs)

    done = 0
    acted = 0
    idle = 0
    marks: list[int] = []
    while acted < cap and idle < 4:
        steps = tool.propose([], obs)
        if not steps:
            idle += 1
            continue
        idle = 0
        for aid, xy in steps:
            prev = np.array(obs.frame[-1])
            if aid == 6:
                obs = env.step(GameAction.ACTION6, data={"x": xy[0], "y": xy[1]})
            else:
                obs = env.step(acts[aid])
            acted += 1
            tool.observe(prev, (aid, xy), True)
            if verbose:
                print(f"   {acted:4d} act={aid} {xy or ''} lvl={obs.levels_completed} {obs.state}")
        new = int(getattr(obs, "levels_completed", done) or 0)
        if new != done:
            marks.append(acted)
            print(f"  level {new}: cleared at {acted} actions")
            done = new
            tool.reset()
            _describe(obs)
        if "GAME_OVER" in str(getattr(obs, "state", "")):
            print(f"     GAME_OVER at {acted}")
            break

    base = list(getattr(info, "baseline_actions", None) or [])
    spent = [b - a for a, b in zip([0] + marks, marks)]
    scores = [min(base[i] / max(1, spent[i]), 1.0) ** 2 for i in range(len(spent)) if i < len(base)]
    weights = list(range(1, len(base) + 1))
    game = sum((i + 1) * s for i, s in enumerate(scores)) / sum(weights) if base else 0.0
    print(f"  per level: spent={spent} human={base[:len(spent)]} scores={[round(s, 3) for s in scores]}")
    print(f"{title} hop: {done} levels in {acted} actions, game_score={game:.4f}")


if __name__ == "__main__":
    main()
