#!/usr/bin/env python3
"""Which tools actually HOLD a board, across the whole 25 — and which never do.

⛔ WHY. A 47-tool x 5-game sweep showed 36 tools clearing NOTHING on any stuck game, but that is
evidence about five boards only. The registry is interrogated on EVERY re-decide (`loop.py:338`,
`:418`, `:440` all loop over `self.tools`), and 19 of 47 have a `detect` that reaches a mutating line
(rule 7ah) — so a tool that never holds a board is not free: it is asked, it may mutate, and on the
110 PRIVATE games it may hold a board nobody has seen it hold here.

This records, per game, every tool that was `_current` for at least one action, with how many. A tool
absent from all 25 rows earns its place ONLY on the private set — which is a real argument, but it
should be made knowingly rather than by default.

⛔ MIRRORS `score_efficiency.py:run_game` (rule 7x): the scorer's own `_make_agent`, an EMPTY frames
list to `is_done`/`choose_action`, `restart_on_game_over` honoured, BREAK on WIN. ⚠️ Verify it
reproduces the banked per-level counts before trusting a row.

Usage:  uv run python scripts/_tool_tenure.py <game> [budget]
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
    from arcengine import GameAction, GameState  # type: ignore

    from score_efficiency import _make_agent

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    want = game.strip().lower()
    game_id = next(
        e.game_id for e in arcade.get_environments()
        if want in f"{e.game_id} {e.title or ''}".lower()
    )
    env = arcade.make(game_id)
    obs = env.observation_space
    adapter = _make_agent("unified", game_id=game_id)

    tenure: Counter = Counter()
    per_level: dict[int, Counter] = {}
    prev_levels = int(obs.levels_completed)
    actions = 0

    for _ in range(budget):
        if adapter.is_done([], obs):
            break
        try:
            action = adapter.choose_action([], obs)
        except Exception:
            break
        if not isinstance(action, GameAction):
            break

        # `_current` is the harness's own name for the tool holding the board (loop.py:534);
        # None means no tool is chosen and `_probe` fills the turn.
        who = getattr(adapter, "_current", None) or "HARNESS"
        tenure[who] += 1
        per_level.setdefault(prev_levels, Counter())[who] += 1

        obs = env.step(action, data=action.action_data.model_dump()) if action.is_complex() \
            else env.step(action)
        if obs is None:
            break
        actions += 1
        prev_levels = max(prev_levels, int(obs.levels_completed))

        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            obs = env.step(GameAction.RESET)
            if obs is None:
                break

    print(json.dumps({
        "game": game,
        "levels": prev_levels,
        "actions": actions,
        "tenure": dict(tenure),
        "per_level": {str(k): dict(v) for k, v in sorted(per_level.items())},
    }))


if __name__ == "__main__":
    main()
