"""R98: which outer pixel rows carry MEANING, told from observation alone.

Purpose
-------
A cell's colour comes from one pixel — its centre — so anything thinner than a cell is
invisible to every cell-based reading in this project. Measured on sp80: the entity whose
contact FAILS THE RUN is a one-pixel band on the last pixel row, and the centre sample for
that cell reads the row above it. The cell shows an unchanging colour for an entire spill
while the pixels underneath carry the verdict.

The harness already excludes outer rows on purpose — `_infer_scale` calls a status bar
"a rendering overlay rather than board structure" — and it is right about most of them.
What it cannot do is tell a decorative strip from an entity that means something, because
both look like a band the sampler does not resolve.

"It changes" does not separate them: measured over fourteen actions, sp80's TOP row changes
fourteen ways (a step counter) and ft09 has the same thing at its bottom. What separates them
is HOW MUCH:

    one state      decoration — a border or a fixed strip
    many states    a counter or clock, moving with every action
    few states     an EVENT — rare, and therefore meaningful

Expected feedback
-----------------
Per game, a verdict for each outer row. An EVENT verdict says the frame carries something the
cell grid throws away; decoration and counter say it does not. On the three games where the
question can arise at all — the rest render one pixel per cell, where nothing can hide — this
picks out exactly sp80's failure band.

NON-GATING diagnostic.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arcengine import GameAction  # noqa: E402
from oracle_gate import ACTIONS, _open_arcade  # noqa: E402

from admorphiq.hypothesis_select.grounding_flow import _as_grid, _infer_scale  # noqa: E402

GAMES = ("sp80", "vc33", "ft09")
ACTION_BUDGET = 14


def classify(states: int, actions: int) -> str:
    """One state is decoration, many is a counter, few is an event.

    The counter threshold is relative to how many actions were spent, because "changes on
    nearly every action" is what a counter does and the count of actions is what makes that
    measurable. Three is the floor so a two-action probe cannot call everything a counter."""
    if states <= 1:
        return "decoration"
    if states >= max(3, actions // 2):
        return "counter"
    return "EVENT"


def survey(prefix: str) -> dict[str, tuple[int, str]]:
    arcade = _open_arcade()
    gid = next((e.game_id for e in arcade.get_environments()
                if e.game_id.startswith(prefix)), None)
    if gid is None:
        return {}
    env = arcade.make(gid)
    obs = env.step(GameAction.RESET)
    rows: dict[str, set[tuple[int, ...]]] = {}
    spent = 0
    for step in range(ACTION_BUDGET):
        for layer in obs.frame:
            grid = _as_grid(layer)
            last = len(grid) - 1
            for name, y in (("top", 0), ("bottom", last)):
                rows.setdefault(name, set()).add(tuple(int(v) for v in grid[y]))
        # a commit every third action, so a spill actually runs and its consequences show
        obs = env.step(ACTIONS[5 if step % 3 == 2 else 1 + step % 4])
        spent += 1
        if str(obs.state) != "GameState.NOT_FINISHED":
            break
    return {name: (len(seen), classify(len(seen), spent)) for name, seen in rows.items()}


def main() -> int:
    events = 0
    for prefix in GAMES:
        arcade = _open_arcade()
        gid = next((e.game_id for e in arcade.get_environments()
                    if e.game_id.startswith(prefix)), None)
        if gid is None:
            print(f"  {prefix:5s} no environment")
            continue
        env = arcade.make(gid)
        obs = env.step(GameAction.RESET)
        scale = _infer_scale(_as_grid(obs.frame[0]))
        if not scale or scale == 1:
            print(f"  {prefix:5s} scale {scale} — a cell IS a pixel, nothing can hide")
            continue
        verdicts = survey(prefix)
        events += sum(1 for _n, kind in verdicts.values() if kind == "EVENT")
        print(f"  {prefix:5s} scale {scale}  " + "  ".join(
            f"{name}: {n} state(s) -> {kind}" for name, (n, kind) in verdicts.items()))

    print(f"\n[edge band] {events} row(s) carry an EVENT the cell grid throws away")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
