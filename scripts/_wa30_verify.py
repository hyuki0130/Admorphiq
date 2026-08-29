"""Replay the recorded wa30 level-9 witness and print `levels_completed` as a NUMBER.

⛔ This exists because `level_index` and `levels_completed` DISAGREE on this board and only one of
them answers "did we win". Level 9 is the LAST level, so the engine's `next_level()` takes the
`is_last_level()` branch and calls `win()` — the level index NEVER increments. A probe that tested
the index would read a real clear as "nothing happened", the mirror of reading a collapse as a
clear: the direction has to be named and the number printed.

Takes a throwaway first argument so it can be fanned; prints one JSON line.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def main() -> None:
    from arc_agi import Arcade, OperationMode

    from admorphiq.adapter import AdmorphiqAdapter
    from admorphiq.types import ActionType, GameAction

    _ = sys.argv[1] if len(sys.argv) > 1 else "1"
    text = Path("scripts/rounds/R101WA30/WITNESS.txt").read_text()
    body = text.split("Replay:")[0]
    nums = re.findall(r"^[\s\d]+$", body, re.M)
    witness = [int(t) for t in " ".join(nums).split()]
    conv = AdmorphiqAdapter._convert_action

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("wa30"))
    env = arcade.make(info.game_id)
    obs = env.reset()
    game = env._game
    game.set_level(8)

    start_done = int(getattr(obs, "levels_completed", 0) or 0)
    start_index = game.level_index
    print(f"START levels_completed={start_done} level_index={start_index} "
          f"witness_len={len(witness)}", file=sys.stderr, flush=True)

    rose_at = None
    for i, a in enumerate(witness, 1):
        obs = env.step(conv(GameAction.simple(ActionType(a))))
        done = int(getattr(obs, "levels_completed", 0) or 0)
        if done > start_done and rose_at is None:
            rose_at = i
            print(f"action {i}: levels_completed {start_done} -> {done} (> start: True) "
                  f"level_index={game.level_index} state={obs.state}",
                  file=sys.stderr, flush=True)
            break
        if i % 20 == 0:
            print(f"action {i}: levels_completed={done} state={obs.state}",
                  file=sys.stderr, flush=True)

    end_done = int(getattr(obs, "levels_completed", 0) or 0)
    pieces = game.current_level.get_sprites_by_tag("geezpjgiyd")
    resting = sum(1 for s in pieces
                  if (s.x, s.y) in game.wyzquhjerd and s not in game.zmqreragji)
    print(json.dumps({
        "witness_actions": len(witness),
        "levels_completed_start": start_done,
        "levels_completed_end": end_done,
        "greater_than_start": end_done > start_done,
        "rose_at_action": rose_at,
        "level_index_start": start_index,
        "level_index_end": game.level_index,
        "engine_state": str(game._state),
        "obs_state": str(getattr(obs, "state", "")),
        "pieces_resting": resting, "pieces_total": len(pieces),
        "step_counter_left": game.kuncbnslnm.current_steps,
    }))


if __name__ == "__main__":
    main()
