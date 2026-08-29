"""s5i5 level 7 — does the engine's restart really hand back the board the level started with?

The whole remaining repair rests on it. The step allowance drains and refills (frame row 63, read
directly: `64 @a192 -> 5 @a376 -> 61 @a401`), so the level IS restarted, and `levels_completed`
never moves. But every attempt to DETECT that from inside the tool has failed: comparing
`solid_cells` against the first reading reported a constant difference of 682 cells and never once
matched, across 2202 actions and several restarts.

⛔ That is an instrument question before it is a mechanism question, and there is an obvious
suspect: `solid_cells` returns the whole frame's solid cells INCLUDING the allowance bar the game
paints along row 63. A bar that is full at the first reading and three pixels short one action
after the restart can never compare equal — and `_chrome` (which covers that row) is subtracted in
`_agrees` but not in a raw comparison.

So this measures the board itself:

  * a fingerprint of every frame with the outer band excluded (`tools.segment.board_changed`'s own
    notion of the board), recorded every action on level 7;
  * the first action whose fingerprint equals action 193's, if any;
  * the allowance bar and the game state around each refill, so the restart is located exactly;
  * how many DISTINCT boards recur, which is what a retry detector would actually key on.

Run:  bash scripts/pfan.sh s5i5restart scripts/_s5i5_restart.py 1 "" 2
"""
from __future__ import annotations

import hashlib
import json
import sys

sys.path.insert(0, "src")

TITLE = "s5i5"
STUCK = 6


def main() -> None:
    _job = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    import numpy as np
    from arc_agi import Arcade, OperationMode

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools
    from admorphiq.tools.telescope import _layers

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free")

    def board_key(obs, band: int) -> str:
        layers = _layers(obs)
        if not layers:
            return "none"
        g = np.asarray(layers[-1])
        inner = g[band:g.shape[0] - band, band:g.shape[1] - band] if band else g
        return hashlib.md5(inner.tobytes()).hexdigest()[:12]

    def bar(obs) -> int:
        layers = _layers(obs)
        if not layers:
            return -1
        return int((np.asarray(layers[-1])[63] == 3).sum())

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith(TITLE))
    env = arcade.make(info.game_id)
    obs = env.reset()
    agent = UnifiedAgent(default_tools(), _no_llm, giveup=8000, stall=80,
                         no_progress=2000, ctx_budget=6000)
    frames = [obs]
    lvl = 0
    first_keys: dict[int, str] = {}
    repeats: dict[int, list[int]] = {1: [], 2: []}
    seen: dict[int, dict[str, int]] = {1: {}, 2: {}}
    bars: list[list[int]] = []
    states: list[list] = []
    prev_bar = None
    step = 0
    for step in range(1600):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", lvl) or 0)
        lvl = now
        if lvl < STUCK:
            continue
        b = bar(obs)
        if prev_bar is not None and b > prev_bar + 5:
            states.append([step + 1, "BAR_REFILL", prev_bar, b, str(getattr(obs, "state", ""))])
        prev_bar = b
        if len(bars) < 40 or (step % 25 == 0):
            bars.append([step + 1, b])
        for band in (1, 2):
            k = board_key(obs, band)
            if band not in first_keys:
                first_keys[band] = k
            if k == first_keys[band] and len(repeats[band]) < 20:
                repeats[band].append(step + 1)
            seen[band][k] = seen[band].get(k, 0) + 1
        if str(getattr(obs, "state", "")).endswith("GAME_OVER") and len(states) < 20:
            states.append([step + 1, "GAME_OVER", b, lvl])
    print(json.dumps({
        "job": 1, "levels": lvl, "actions": step + 1,
        "first_board_key": first_keys,
        "actions_matching_first_board": {str(k): v for k, v in repeats.items()},
        "distinct_boards": {str(k): len(v) for k, v in seen.items()},
        "most_repeated": {str(k): sorted(v.values(), reverse=True)[:5] for k, v in seen.items()},
        "events": states[:20],
        "bar_samples": bars[:40],
    }))


if __name__ == "__main__":
    main()
