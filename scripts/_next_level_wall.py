#!/usr/bin/env python3
"""What does the harness DO on the level it cannot pass? One question, every stuck game at once.

⛔ WHY THIS AND NOT ANOTHER PER-GAME PROBE. Four of the seven incomplete games lose nothing but
depth — every level they reach scores 1.0 and the game simply ends short — so the only question that
matters for them is what happens AT THE WALL. That question has been asked one game at a time, by a
different agent each time, in a different instrument each time. Rule 7h: working serially is caused
by generating one hypothesis at a time. There are exactly four candidate walls and they are
distinguishable in a single run:

  EMPTY      the agent stops proposing (``is_done``) or returns a non-action
  COLLAPSE   the level ENDS — GAME_OVER — rather than merely failing to advance
  INERT      the engine accepts the action and the board does not change
  MOVED      the board changes and the level still does not advance

Those four want four different fixes and three of them are NOT "search harder".

⛔ IT MIRRORS ``scripts/score_efficiency.py:run_game`` LINE FOR LINE — same ``Arcade`` construction,
same ``_make_agent``, same ``choose_action([], obs)``, same complex-action ``data=`` branch, same
GAME_OVER handling. A probe that drives the engine its own way measures its own way of driving:
three separate disagreements between a per-tool probe and the harness were paid for on 2026-08-27,
which is why ``scripts/harness_probe.py`` exists. Reuse beats re-derivation here.

⚠️ Reports levels as NUMBERS and compares ``> start``. A collapse to level 0 is otherwise
indistinguishable from a clear, which survived three commits and two probes on 2026-08-29 (rule 7f).

⚠️ INSTRUMENT VALIDITY (rule 7c/7d — three instruments lied toward "nothing here" today): the board
comparison ignores the outer band via ``tools.segment.board_changed``. A plain ``(prev != cur).any()``
is true on every action for any game that draws a step counter at the edge, so INERT would score zero
everywhere and read exactly like a finding.

Usage:  uv run python scripts/_next_level_wall.py <game> [budget]
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter


def main() -> None:
    game = sys.argv[1]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "src"))
    sys.path.insert(0, here)

    from arc_agi import Arcade, OperationMode  # type: ignore

    from admorphiq.tools.base import frame_2d
    from admorphiq.tools.segment import board_changed
    # ⛔ arcengine, NOT admorphiq.types. They are different classes with the same names, so an
    # isinstance() against the wrong one is False for every action the agent returns — and this probe
    # then reports EMPTY, which is a finding-shaped null. Caught by running it on ar25, which scores
    # 1.0000 and came back "EMPTY at step 0". Rule 7b: validate the instrument on a verdict you know.
    from arcengine import GameAction, GameState  # type: ignore
    from score_efficiency import _make_agent  # the SAME factory the scored runs use

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    # ⛔ get_environments() yields EnvironmentInfo objects, not id strings, and the runner selects on
    # "<game_id> <title>" lowercased — mirror that rather than inventing a match, or a title-only
    # game silently resolves to the wrong environment.
    want = game.strip().lower()
    game_id = next(
        e.game_id
        for e in arcade.get_environments()
        if want in f"{e.game_id} {e.title or ''}".lower()
    )
    env = arcade.make(game_id)
    obs = env.observation_space

    adapter = _make_agent("unified", game_id=game_id)
    start = int(obs.levels_completed)
    high = start
    prev_levels = start
    tally: dict[int, Counter] = {}
    prev = frame_2d(obs)

    for _ in range(budget):
        lvl = int(obs.levels_completed)
        t = tally.setdefault(lvl, Counter())

        if adapter.is_done([], obs):
            t["EMPTY_is_done"] += 1
            break
        try:
            action = adapter.choose_action([], obs)
        except Exception as exc:  # a raising propose reads exactly like EMPTY; count it apart
            t["THREW_" + type(exc).__name__] += 1
            break
        if not isinstance(action, GameAction):
            t["EMPTY_no_action"] += 1
            break

        if action.is_complex():
            obs = env.step(action, data=action.action_data.model_dump())
        else:
            obs = env.step(action)
        if obs is None:
            t["ENV_none"] += 1
            break

        t["actions"] += 1
        now = int(obs.levels_completed)
        if now > prev_levels:
            t["ADVANCED"] += 1
            prev_levels = now
            high = max(high, now)
        elif obs.state == GameState.GAME_OVER:
            t["COLLAPSE"] += 1
        else:
            cur = frame_2d(obs)
            t["MOVED" if board_changed(prev, cur) else "INERT"] += 1
            prev = cur

        if obs.state == GameState.WIN:
            t["WIN"] += 1
            break
        if obs.state == GameState.GAME_OVER:
            obs = env.step(GameAction.RESET)
            if obs is None:
                break
            prev = frame_2d(obs)

    wall = high
    print(
        json.dumps(
            {
                "game": game,
                "start_level": start,
                "highest_level": high,
                "cleared": high > start,
                "wall_level": wall,
                "wall": dict(tally.get(wall, Counter())),
                "all_levels": {str(k): dict(v) for k, v in sorted(tally.items())},
            }
        )
    )


if __name__ == "__main__":
    main()
