#!/usr/bin/env python3
"""Is `_EMPTY_TOLERANCE` load-bearing on the FULL 25 — value AND shape? (rule 7bd's third half)

⛔ THE QUESTION. `_EMPTY_TOLERANCE = 8` is the only number that ends a tenure by exhaustion. It was
picked against two boards (s5i5's 448 centre-clicks, dc22's 499) and swept on exactly ONE game
(rule 7ax: ls20's level 7 is INVARIANT at 231 for handovers from action 9 to 17). Nobody has asked
what it is worth across all twenty-five, and it is a harness constant, so it prices every one of the
110 private games.

⛔ AND THE SHAPE IS SEPARATELY SUSPECT. `_empty_runs` is AGENT-scoped, not tenure-scoped: nothing in
`_reset_level` or `_redecide` clears it (loop.py — the only writes are the reset-on-legal-fill and
the reset-on-fire). A successor therefore INHERITS its predecessor's partial empty count and can be
retired having personally proposed nothing fewer than eight times. The `perT` arm is that one
change and nothing else.

ARMS (seed = arm * 25 + game_index, so one fan covers the grid):
    tol8=CONTROL (seeds 1..25)  tol1  tol2  tol4  tol16  tol32  perT8
The CONTROL arm must reproduce `scripts/rounds/R101LP85GATE/games/<game>.json` per-level counts
exactly, or nothing read off the other arms is admissible (rule 7ai).

⛔ MIRRORS `score_efficiency.py:run_game` (rule 7x): the scorer's own `_make_agent("unified")`, an
EMPTY frames list, `restart_on_game_over` honoured, BREAK on WIN, same per-level accounting.

Usage:  uv run python scripts/_tenure_tolsweep.py <seed 1..175> [budget]
"""

from __future__ import annotations

import json
import os
import sys

ARMS = ["tol8", "tol1", "tol2", "tol4", "tol16", "tol32", "perT8"]  # CONTROL FIRST: seeds 1..25
TOL = {"tol1": 1, "tol2": 2, "tol4": 4, "tol8": 8, "tol16": 16, "tol32": 32, "perT8": 8}


def main() -> None:
    seed = int(sys.argv[1]) - 1
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "src"))
    sys.path.insert(0, here)

    from arc_agi import Arcade, OperationMode  # type: ignore
    from arcengine import GameAction, GameState  # type: ignore
    from score_efficiency import _make_agent, game_score, level_score

    from admorphiq.harness import loop as loopmod

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    # ⛔ DEDUPE BY game_id. ceph-build's environment_files/sk48 holds TWO version dirs
    # (41055498 and d8078629) with the SAME game_id, the SAME baseline and DIFFERENT bytes, while
    # the repository has only the first — so `get_environments()` returns 26 there and 25 here, and
    # an index-addressed fan silently runs one game twice and drops the last. This is rule
    # 7 (env_metadata_duplicate_game_id) on a machine nobody re-checked.
    seen: set[str] = set()
    envs = [e for e in sorted(arcade.get_environments(), key=lambda e: e.game_id)
            if not (e.game_id in seen or seen.add(e.game_id))]
    arm = ARMS[seed // len(envs)]
    entry = envs[seed % len(envs)]
    game_id = entry.game_id
    game = game_id.split("-")[0]

    # The lever. `loop.py` reads the module global at the comparison, so rebinding it here is the
    # whole arm — no edit to the shipped file, and the CONTROL arm rebinds it to its own value.
    loopmod._EMPTY_TOLERANCE = TOL[arm]

    env = arcade.make(game_id)
    obs = env.observation_space
    adapter = _make_agent("unified", game_id=game_id)

    if arm == "perT8":
        # The SHAPE arm: the empty counter belongs to the TENURE, not to the agent.
        orig_fill = type(adapter)._fill_from_current

        def fill(self, frames, o):
            if getattr(self, "_census_last_cur", "\0") != self._current:
                self._census_last_cur = self._current
                self._empty_runs = 0
            orig_fill(self, frames, o)

        type(adapter)._fill_from_current = fill

    win_levels = int(obs.win_levels)
    prev_levels = int(obs.levels_completed)
    total = 0
    this_level = 0
    per_level: list[int] = []
    restart_on_game_over = bool(getattr(adapter, "restart_on_game_over", False))

    while total < budget:
        if adapter.is_done([], obs):
            break
        try:
            action = adapter.choose_action([], obs)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"seed": seed + 1, "arm": arm, "game": game,
                              "error": str(exc)[:160]}))
            return
        if not isinstance(action, GameAction):
            break
        obs = env.step(action, data=action.action_data.model_dump()) if action.is_complex() \
            else env.step(action)
        if obs is None:
            break
        total += 1
        this_level += 1
        cur = int(obs.levels_completed)
        if cur > prev_levels:
            for _ in range(cur - prev_levels):
                per_level.append(this_level)
                this_level = 0
            prev_levels = cur
        if obs.state == GameState.WIN:
            break
        if obs.state == GameState.GAME_OVER:
            if not restart_on_game_over:
                break
            obs = env.step(GameAction.RESET)
            total += 1
            this_level += 1
            if obs is None:
                break

    # Score exactly as the scorer does: per-level squared efficiency, level-index weighted,
    # denominator = ALL levels' weights (so an unfinished game is capped by completion).
    baseline = entry.baseline_actions
    scores: list[float] = []
    for i, acts in enumerate(per_level):
        h = baseline[i] if baseline is not None and i < len(baseline) else None
        scores.append(level_score(h, acts) if h is not None else 0.0)
    print(json.dumps({
        "seed": seed + 1, "arm": arm, "game": game, "tol": TOL[arm],
        "levels": prev_levels, "win_levels": win_levels,
        "actions": total, "per_level": per_level,
        "game_score": round(game_score(scores, win_levels), 6),
    }))


if __name__ == "__main__":
    main()
