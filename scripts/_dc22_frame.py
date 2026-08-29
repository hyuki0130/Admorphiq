"""Print dc22 level 6's frame as text, plus what phase/gantry perception makes of it.

Varying parameter FIRST = unused (kept so the probe fans).  Prints the grid then ONE JSON line.
"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import score_efficiency as SE  # noqa: E402
from arcengine import GameAction  # noqa: E402


class Grab:
    def __init__(self):
        self.inner = SE._make_agent("unified", game_id="dc22")
        self.got = False

    def is_done(self, frames, obs):
        return self.got or self.inner.is_done(frames, obs)

    def choose_action(self, frames, obs):
        if obs.levels_completed >= 5 and not self.got:
            self.got = True
            self.dump(obs)
            return GameAction.ACTION1
        return self.inner.choose_action(frames, obs)

    def dump(self, obs):
        from admorphiq.tools import phase as P
        g = np.asarray(obs.frame[-1], dtype=int)
        print("    " + "".join(f"{x%10}" for x in range(64)), flush=True)
        for y in range(64):
            print(f"{y:3d} " + "".join(f"{v:x}" if v >= 0 else "." for v in g[y]), flush=True)
        from collections import Counter
        hist = Counter(int(v) for row in g for v in row)
        top, bot = P._chrome_span(g)
        split = P._split_columns(g, top, bot)
        info = {"levels_completed": int(obs.levels_completed),
                "hist": dict(sorted(hist.items(), key=lambda kv: kv[1])),
                "chrome": [int(top), int(bot)], "split": list(split) if split else None}
        for name, band in (("board", g[top:bot + 1, 0:split[0]] if split else None),
                           ("whole", g[top:bot + 1, :])):
            if band is None:
                continue
            info[name + "_pieces"] = P._pieces(band)
            info[name + "_onesq"] = {c: P._one_square(band, c) for c in (9, 11, 14)}
            info[name + "_solid"] = {c: P._solid_block(band, c) for c in (9, 11, 14)}
        print(json.dumps(info, default=str), flush=True)


def main():
    _ = sys.argv[1] if len(sys.argv) > 1 else "0"
    from arc_agi import Arcade, OperationMode
    arcade = Arcade(operation_mode=OperationMode.OFFLINE)
    envs = [e for e in arcade.get_environments() if "dc22" in f"{e.game_id} {e.title or ''}".lower()]
    ei = envs[0]
    SE.run_game(arcade, ei.game_id, ei.baseline_actions, agent_name="grab",
                max_actions=2000, adapter_factory=lambda: Grab())


if __name__ == "__main__":
    main()
