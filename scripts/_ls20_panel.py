"""ls20: WHY does `fogscout` read no token panel on the unfogged levels 1-6?

Purpose. `scripts/_ls20_passive.py` measured that a passive `fogscout` learns `dirs` (4/4 on level
1) and the refill signature (level 2) from levels it does not drive, but learns ZERO changers --
because `self.tok` is never read there, and with no token every changer press looks like nothing
happening, so the marks are filed INERT and carrying that LOSES the level. The panel is the whole
blocker. This probe reads the level-1 and level-7 frames side by side and prints exactly what
`_read_panel` sees, so the fix is chosen from the failure rather than guessed.

⛔ The verdict is known in one direction already -- level 7 finds the panel at (55,3)-(60,8) -- so
the same code is run on both frames and the level-7 column is the positive control.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def main() -> None:
    import numpy as np
    from arc_agi import Arcade, OperationMode
    from arcengine import GameAction

    from admorphiq.tools.base import frame_2d
    from admorphiq.tools.fogscout import _dominant, _rect_components, fog_view, icon_key

    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    info = next(i for i in arcade.get_environments()
                if (i.title or i.game_id).lower().startswith("ls20"))
    env = arcade.make(info.game_id)
    obs = env.observation_space

    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    agent = UnifiedAgent(default_tools(), _no_llm, giveup=4000, stall=80, ctx_budget=6000)
    # The board as it stands two actions into each level, which is what a passive observer sees.
    frames: dict[int, np.ndarray] = {}
    seen_at: dict[int, int] = {}
    lvl = int(obs.levels_completed)
    total = 0
    while total < 4000:
        if agent.is_done([], obs):
            break
        act = agent.choose_action([], obs)
        if not isinstance(act, GameAction):
            break
        obs = env.step(act, data=act.action_data.model_dump()) if act.is_complex() else env.step(act)
        if obs is None:
            break
        total += 1
        cur = int(obs.levels_completed)
        if cur != lvl:
            lvl, seen_at[cur] = cur, total
        if lvl not in frames and total - seen_at.get(lvl, 0) >= 2:
            frames[lvl] = frame_2d(obs).astype(np.int16)
        if lvl >= 6 and len(frames) >= 7:
            break

    out = []
    for lvl in sorted(frames):
        f = frames[lvl]
        flat = _dominant(f)
        view = fog_view(f)
        rec = {"level": lvl + 1, "dominant": flat,
               "fogged": view is not None, "fog_flat": None if view is None else view[0],
               "panel_patch_colors": Counter(int(v) for v in f[55:61, 3:9].ravel()).most_common(),
               "icon_key_global": icon_key(f[55:61, 3:9], flat) is not None,
               "components_near_panel": []}
        for y0, x0, hh, ww, size in _rect_components(f != flat):
            if not (48 <= y0 <= 64 and 0 <= x0 <= 16):
                continue
            side = max(hh, ww)
            patch = f[y0:y0 + side, x0:x0 + side]
            cols = Counter(int(v) for v in patch.ravel())
            local = cols.most_common(1)[0][0]
            rec["components_near_panel"].append({
                "box": [y0, x0, hh, ww, size],
                "colors": cols.most_common(),
                "vs_dominant": icon_key(patch, flat) is not None,
                "vs_local": icon_key(patch, local) is not None,
            })
        out.append(rec)
    # ⛔ a DICT, not a list: the fan keeps only lines starting with "{" and a JSON array is
    # dropped silently, which reads exactly like a probe that produced nothing.
    print(json.dumps({"levels": out}, default=str), flush=True)


if __name__ == "__main__":
    main()
