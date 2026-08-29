#!/usr/bin/env python3
"""Does this game's stuck level RESTART? Answered from the RAW FRAME, on every game at once.

⛔ WHY, AND WHY THIS TEST AND NOT ANOTHER. wa30 was conquered because its last level restarts on an
action-count overrun while `levels_completed` does not move, so the harness got eight attempts and
spent SIX of them replaying one — the tool carried a stale plan across a reset it could not see
(rule 7s). If other stuck levels do the same, their tools are wasting attempts the same way, and
that is cheaper to fix than any search.

⛔ AND THE MODEL-LEVEL VERSION OF THIS TEST IS UNSOUND (rule 7u, paid for the same day). An agent
detected a restart from its own model's piece count rising and concluded lf52 was losing level 6 four
times; it was measuring DISCOVERY — the camera uncovering pieces on a scrolling board. "Pieces only
ever leave the board" is true of the BOARD and false of a model still building one.

So this hashes the RAW FRAME. A genuine restart resets board and camera together, so the level's
OPENING frame returns byte-for-byte. That is unfalsifiable by any amount of model confusion, and it
costs one dict lookup per action.

  opening_recurrences   times the level's first frame came back exactly  -> attempts - 1
  distinct              how many distinct frames the level visited       -> is it exploring at all
  state_game_over       GAME_OVER seen while ON the level                -> the other restart signal

⚠️ A game may also restart to a DIFFERENT opening (a randomised board). `distinct` and the GAME_OVER
count are carried so a zero recurrence count cannot be read as "no restarts" on its own.

Usage:  uv run python scripts/_restart_census.py <game> [budget]
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from collections import Counter


def _digest(arr) -> str:
    return hashlib.md5(arr.tobytes()).hexdigest()[:12]


def main() -> None:
    game = sys.argv[1]
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else 4000

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "src"))
    sys.path.insert(0, here)

    from arc_agi import Arcade, OperationMode  # type: ignore
    from arcengine import GameAction, GameState  # type: ignore

    from admorphiq.tools.base import frame_2d
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

    level = int(obs.levels_completed)
    start_level = level
    won = False
    opening: dict[int, str] = {level: _digest(frame_2d(obs))}
    seen: dict[int, set[str]] = {level: {opening[level]}}
    recur: Counter = Counter()
    overs: Counter = Counter()
    acts: Counter = Counter()

    for _ in range(budget):
        try:
            action = adapter.choose_action([], obs)
        except Exception:
            break
        if not isinstance(action, GameAction):
            break
        obs = env.step(action, data=action.action_data.model_dump()) if action.is_complex() \
            else env.step(action)
        if obs is None:
            break

        now = int(obs.levels_completed)
        d = _digest(frame_2d(obs))
        acts[now] += 1
        if now not in opening:
            opening[now] = d          # first frame of a level we have just entered
            seen[now] = set()
        elif d == opening[now]:
            recur[now] += 1           # the level's opening came back — an attempt ended
        seen[now].add(d)
        # ⛔ MIRROR THE SCORER OR MEASURE A DIFFERENT RUN (rule 7x). score_efficiency.py BREAKS on
        # WIN. The first version of this probe did not, so it kept playing and resetting after the
        # game was already won and counted deaths the scored run never sees — sc25 came back with
        # 143 GAME_OVERs on a game that scores 1.0000. Caught by the numbers being absurd, which is
        # luckier than it should be: on a game that does NOT win, the same defect is invisible.
        if obs.state == GameState.WIN:
            won = True
            break
        if obs.state == GameState.GAME_OVER:
            overs[now] += 1
            obs = env.step(GameAction.RESET)
            if obs is None:
                break
        level = now

    wall = max(acts, key=lambda k: acts[k]) if acts else start_level
    print(json.dumps({
        "game": game,
        "won": won,
        "start_level": start_level,
        "highest_level": max(acts) if acts else start_level,
        "wall_level": wall,
        "wall_actions": acts.get(wall, 0),
        "wall_opening_recurrences": recur.get(wall, 0),
        "wall_distinct_frames": len(seen.get(wall, ())),
        "wall_game_over": overs.get(wall, 0),
        "per_level": {
            str(k): {"actions": acts[k], "recur": recur.get(k, 0),
                     "distinct": len(seen.get(k, ())), "over": overs.get(k, 0)}
            for k in sorted(acts)
        },
    }))


if __name__ == "__main__":
    main()
