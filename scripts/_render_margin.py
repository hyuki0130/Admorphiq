"""Per game: the largest rigid translation whose validity condition can hold.

The translation arm of `rendergate.sh` needs a UNIFORM MARGIN of at least the shift on
both the leaving and the entering side, of the same colour (see
`admorphiq.render_mutation.Translate`). This probe measures that margin so the arm is
not run blind — and it measures it over a random-walk sample of the game, not only the
opening frame, because validity has to hold for EVERY frame the agent sees.

⛔ IT IS A TRIAGE, NOT A PROOF. A game reported as having margin k here can still be
refused mid-run on a frame this walk never reached; the instrument checks every frame
regardless. What this probe rules out is the opposite: a game reported 0 cannot possibly
support the arm, and running it would only produce refusals.

    bash scripts/pfan.sh rmargin scripts/_render_margin.py 25 "" 8
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

MAX_K = 6
STEPS = 120


def margin(layer: np.ndarray) -> int:
    """Largest k <= MAX_K such that all four k-wide edge bands hold ONE colour."""
    arr = np.asarray(layer)
    h, w = arr.shape
    best = 0
    for k in range(1, MAX_K + 1):
        vals = {int(v) for band in (arr[:k, :], arr[h - k:, :], arr[:, :k], arr[:, w - k:])
                for v in np.unique(band)}
        if len(vals) != 1:
            break
        best = k
    return best


def main() -> int:
    idx = int(sys.argv[1]) - 1
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = []
    seen: set[str] = set()
    for e in arcade.get_environments():
        if e.game_id not in seen:
            seen.add(e.game_id)
            envs.append(e)
    envs.sort(key=lambda e: e.game_id)
    if idx >= len(envs):
        return 0
    info = envs[idx]

    env = arcade.make(info.game_id)
    obs = env.observation_space
    rng = np.random.default_rng(0)
    worst = min(margin(x) for x in obs.frame)
    opening = worst
    simple = [a for a in GameAction if a.is_simple() and a is not GameAction.RESET]
    for _ in range(STEPS):
        avail = set(obs.available_actions or [])
        pool = [a for a in simple if a.value in avail]
        if 6 in avail:
            act = GameAction.ACTION6
            act.set_data({"game_id": "", "x": int(rng.integers(64)),
                          "y": int(rng.integers(64))})
            obs = env.step(act, data=act.action_data.model_dump())
        elif pool:
            obs = env.step(pool[int(rng.integers(len(pool)))])
        else:
            break
        if obs is None or not obs.frame:
            break
        worst = min(worst, min(margin(x) for x in obs.frame))
        if worst == 0:
            break

    # ⛔ THE PROBE CARRIES ITS OWN POSITIVE CONTROL. Rule 7q: an all-zero column is
    # indistinguishable from a margin() that returns 0 for everything. This board has a
    # 4-wide uniform border by construction, so control_margin MUST read 4; any other
    # value means the measurement above says nothing.
    control = np.full((64, 64), 3, dtype=np.int8)
    control[4:60, 4:60] = 7
    print(json.dumps({"game": info.game_id.split("-")[0], "opening_margin": opening,
                      "walk_margin": worst, "layers": len(obs.frame) if obs else 0,
                      "control_margin": margin(control)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
