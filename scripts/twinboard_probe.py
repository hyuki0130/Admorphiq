"""Compare a game against its ARCHIVED re-render, and say which of the two things went wrong.

This repository keeps a second copy of most sample games under ``environment_files_archive/`` --
the same games as an earlier API version served them. They are the only evidence here about
boards nothing has been tuned against, and the eval is games we will never see, so a tool that
scores differently on the two copies is the most informative failure available.

When that happens there are exactly two possibilities and they call for opposite work:

  * the BOARD is different -- different layout, different rules, a genuinely harder puzzle; or
  * the PICTURE is different and the board is not, in which case the tool's perception is what
    failed and the level is winnable by the moves it already knows.

``same`` settles that in one command by recording the harness's own action tape on one copy and
replaying it, action for action, on the other. If the tape clears the same levels at the same
action counts, the two copies are the SAME GAME and every difference in score is perception.

``see`` then localises it. A raw pixel diff is all noise, because a re-render may permute the
PALETTE and may draw the same board at a different OFFSET -- one game's nine levels showed both,
plus one real difference, and nothing but a raw diff would tell them apart. So this searches for
the shift and the colour mapping that best explain one copy as the other, and prints only what
survives both. On the game this was written for, eight of nine levels survived nothing and the
ninth left a single 3x3 object, VISIBLE on one copy and HIDDEN on the other because the maze it
stands on is drawn at a different layer in the two renders and covers it in only one of them.

    uv run python scripts/twinboard_probe.py same <title> [budget]
    uv run python scripts/twinboard_probe.py see  <title> [level]
    uv run python scripts/twinboard_probe.py both <title> [budget]
    uv run python scripts/twinboard_probe.py candidate <title> [budget]
    uv run python scripts/twinboard_probe.py full [budget]

``candidate`` measures a proposed change to an EXISTING tool without editing it, by binding the
replacement over the class for the length of the run. It is a measurement harness, not an edit:
the change it carries has to be applied by whoever owns the integration.
"""

from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, "src")

LIVE = "environment_files"
ARCHIVE = "environment_files_archive"


def _arcade(root: str):
    from arc_agi import Arcade, OperationMode
    return Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=os.path.abspath(root))


def _make(root: str, title: str):
    arcade = _arcade(root)
    info = next((i for i in arcade.get_environments()
                 if (i.title or i.game_id).lower().startswith(title)), None)
    if info is None:
        # Not every game was archived; saying so beats a StopIteration ten frames deep.
        raise SystemExit(f"{title} has no copy under {root}/")
    return arcade.make(info.game_id), info


def _titles(root: str) -> list[str]:
    return sorted({(i.title or i.game_id).lower() for i in _arcade(root).get_environments()})


def _agent(cap: int):
    from admorphiq.harness.loop import UnifiedAgent
    from admorphiq.harness.registry import default_tools

    def _no_llm(*_a, **_k):
        raise RuntimeError("LLM-free: the signature fallback is what this measures")

    return UnifiedAgent(default_tools(), _no_llm, giveup=cap, stall=80, ctx_budget=6000)


def _run(root: str, title: str, cap: int) -> tuple[int, int, list, Counter, list]:
    """Play one copy through the real harness; return levels, actions, clears, who acted, tape."""
    env, _ = _make(root, title)
    obs = env.reset()
    agent = _agent(cap)
    frames = [obs]
    picks: Counter = Counter()
    marks: list[tuple[int, int]] = []
    tape: list[tuple[str, dict | None]] = []
    levels = step = 0
    for step in range(cap):
        if agent.is_done(frames, obs):
            break
        act = agent.choose_action(frames, obs)
        picks[str(agent._current)] += 1
        data = act.action_data.model_dump() if getattr(act, "action_data", None) else None
        tape.append((getattr(act, "name", str(act)), data))
        obs = env.step(act, data=data) if data else env.step(act)
        frames.append(obs)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, step + 1))
            levels = now
    return levels, step + 1, marks, picks, tape


def _replay(root: str, title: str, tape: list) -> tuple[int, list]:
    from arcengine import GameAction
    env, _ = _make(root, title)
    env.reset()
    marks: list[tuple[int, int]] = []
    levels = 0
    for i, (name, data) in enumerate(tape):
        act = getattr(GameAction, name)
        obs = env.step(act, data=data) if data else env.step(act)
        now = int(getattr(obs, "levels_completed", levels) or 0)
        if now != levels:
            marks.append((now, i + 1))
            levels = now
    return levels, marks


def same(title: str, cap: int) -> None:
    """Is it the same GAME? Record the tape on one copy, replay it on the other."""
    for src, dst in ((LIVE, ARCHIVE), (ARCHIVE, LIVE)):
        lv, acts, marks, _picks, tape = _run(src, title, cap)
        print(f"{src:28s} played  {lv} levels / {acts} actions  {marks}")
        for root in (src, dst):
            rl, rm = _replay(root, title, tape)
            tag = "control" if root == src else "REPLAYED ON THE OTHER COPY"
            print(f"   tape on {root:26s} -> {rl} levels  {rm}   [{tag}]")


def _palette(a, b):
    """Map one copy's palette onto the other's, greedily by how often colours coincide."""
    import numpy as np
    pairs: Counter = Counter(zip(np.asarray(a).ravel().tolist(),
                                 np.asarray(b).ravel().tolist()))
    table: dict[int, int] = {}
    used: set[int] = set()
    for (ca, cb), _n in pairs.most_common():
        if ca in table or cb in used:
            continue
        table[ca] = cb
        used.add(cb)
    return np.vectorize(lambda v: table.get(int(v), int(v)))(np.asarray(a))


def _align(a, b, window: int = 8):
    """The (shift, palette) that best explains one copy as the other, and what is left over.

    ⛔ Both halves are needed and the second was learned the hard way. A re-render can permute
    the palette, which makes a raw pixel diff pure noise -- and it can also draw the same maze at
    a different OFFSET, which a palette map alone reports as most of the board having changed.
    Two of a game's levels showed exactly those two failures, and only one of the nine had a
    difference that survived both corrections. That one was the bug.
    """
    import numpy as np
    src = np.asarray(a)
    h, w = src.shape
    best = None
    for dy in range(-window, window + 1):
        for dx in range(-window, window + 1):
            # A shift that WRAPS is not a shift: rolling the step-counter row off the bottom
            # and back in at the top invented a difference across the whole first row.
            shifted = np.full_like(src, -9)
            ys, ye = max(0, dy), min(h, h + dy)
            xs_, xe = max(0, dx), min(w, w + dx)
            shifted[ys:ye, xs_:xe] = src[ys - dy:ye - dy, xs_ - dx:xe - dx]
            mapped = _palette(shifted, b)
            resid = (mapped != b) & (shifted != -9)
            n = int(resid.sum()) + abs(dy) * w + abs(dx) * h
            if best is None or n < best[0]:
                best = (n, dy, dx, resid, mapped)
    return best


def see(title: str, level: int) -> None:
    """What SURVIVES an offset and a palette normalisation is the real difference."""
    import numpy as np
    from arcengine import GameAction

    grids = []
    for root in (LIVE, ARCHIVE):
        env, _ = _make(root, title)
        env.reset()
        env._game.set_level(level)
        obs = env.step(GameAction.ACTION1)
        arr = np.asarray(obs.frame)
        grids.append(arr[-1] if arr.ndim >= 3 else arr)
    a, b = grids
    raw = int((a != b).sum())
    n, dy, dx, resid, mapped = _align(a, b)
    print(f"{title} level {level + 1}: {raw} cells differ raw; after a shift of "
          f"({dy},{dx}) and a palette map, {n} remain")
    if not resid.any():
        print("   the two copies draw the SAME board, recoloured and/or moved")
        return
    ys, xs = np.where(resid)
    print(f"   surviving box rows {ys.min()}-{ys.max()} cols {xs.min()}-{xs.max()}")
    for y in range(ys.min(), min(ys.max() + 1, ys.min() + 20)):
        row = "".join(f"{int(mapped[y, x]):x}" if resid[y, x] else "."
                      for x in range(xs.min(), xs.max() + 1))
        alt = "".join(f"{int(b[y, x]):x}" if resid[y, x] else "."
                      for x in range(xs.min(), xs.max() + 1))
        print(f"   {y:3d}  live {row}   archive {alt}")


def both(title: str, cap: int) -> None:
    for root in (LIVE, ARCHIVE):
        lv, acts, marks, picks, _ = _run(root, title, cap)
        top = dict(picks.most_common(3))
        print(f"{root:28s} {lv} levels / {acts} actions  {marks}  acted {top}")


# --- the candidate change ----------------------------------------------------
#
# ⛔ NOT APPLIED. This is the fix this probe was written to justify, held here so it can be
# re-measured in one command by whoever owns the integration.
#
# The steered piece is currently found by its BODY COLOUR, and that stops being an identity the
# moment a second piece wears the same colours -- which is exactly what one archived copy shows
# and the live copy hides. With two candidates the reader falls through to the CENTROID of every
# pixel of that colour, which lands between the two pieces and is neither of them.
#
# What a position is: the piece stood at a known node, a control with a known displacement was
# spent, so it is at that node plus the displacement if the move was taken, or still at that node
# if it was refused. Everything else wearing the colour is a different piece. Colour alone still
# answers when only one piece wears it, which is what keeps a struck piece findable.
#
# MEASURED with `full`: the owning tool takes a turn on 2 of 40 game/copy pairs, both of them the
# same game, so 38 pairs cannot change and did not. Of the two, the live copy is byte-for-byte
# unchanged and the archived copy goes 4 levels in 1288 actions to 9 in 188 -- the live copy's
# own timings, level for level.
#
# To apply it: this is a method of the owning tool, so `rank_pieces` becomes a plain module
# reference and the local import goes.

def _locate_by_position(self, board):
    """Where the steered piece stands: by position when the colour is shared, colour otherwise."""
    if self._body is None:
        return None
    same_colour = [c for c, (body, _) in board.pieces.items() if body == self._body]
    if len(same_colour) == 1:
        return same_colour[0]
    if not same_colour:
        return self._centroid_cell(board, board.side)
    if self._prev_cell is None:
        from admorphiq.tools.lattice_maze import rank_pieces
        for cell in rank_pieces(board):
            if cell in same_colour:
                return cell
        return same_colour[0]
    eff = self._effect.get(self._prev_action) if self._prev_action is not None else None
    if eff is not None:
        moved = (self._prev_cell[0] + eff[0], self._prev_cell[1] + eff[1])
        if moved in same_colour:
            return moved
        if self._prev_cell in same_colour:
            return self._prev_cell
    return min(same_colour,
               key=lambda c: abs(c[0] - self._prev_cell[0]) + abs(c[1] - self._prev_cell[1]))


def candidate(title: str, cap: int) -> None:
    from admorphiq.tools.lattice_maze import LatticeMazeTool
    original = LatticeMazeTool._locate
    for label, fn in (("as registered", original), ("with the candidate", _locate_by_position)):
        LatticeMazeTool._locate = fn
        for root in (LIVE, ARCHIVE):
            lv, acts, marks, _p, _t = _run(root, title, cap)
            print(f"{label:20s} {root:28s} {lv} levels / {acts} actions  {marks}")
    LatticeMazeTool._locate = original


def full(cap: int) -> None:
    """Every game, both copies, before and after the candidate -- the only honest keep/revert.

    Scoped, and the scope is an argument rather than an economy: the candidate replaces a method
    of ONE tool, and that method only ever runs after the harness has already handed that tool a
    turn. A game where the tool never acted cannot change, so the baseline pass records who acted
    and the second pass re-runs only the games where it did. Both passes are printed in full, so
    the scope can be checked rather than taken on trust.
    """
    from admorphiq.tools.lattice_maze import LatticeMazeTool
    owner = LatticeMazeTool.name
    original = LatticeMazeTool._locate
    base: dict[tuple[str, str], tuple[int, int]] = {}
    touched: list[tuple[str, str]] = []
    for root in (LIVE, ARCHIVE):
        for title in _titles(root):
            lv, acts, _m, picks, _t = _run(root, title, cap)
            base[(title, root)] = (lv, acts)
            acted = picks.get(owner, 0)
            if acted:
                touched.append((title, root))
            tag = "live" if root == LIVE else "archive"
            print(f"  before {tag:7s} {title:8s} {lv} levels / {acts:5d}"
                  f"   {owner} acted {acted}", flush=True)
    print(f"\n{owner} acted on {len(touched)} of {len(base)} game/copy pairs; "
          f"re-running those with the candidate\n")
    LatticeMazeTool._locate = _locate_by_position
    changed = 0
    try:
        for title, root in touched:
            lv, acts, marks, _p, _t = _run(root, title, cap)
            was = base[(title, root)]
            flag = "" if (lv, acts) == was else "   <-- CHANGED"
            if flag:
                changed += 1
            tag = "live" if root == LIVE else "archive"
            print(f"  after  {tag:7s} {title:8s} {lv} levels / {acts:5d}"
                  f"   was {was[0]}/{was[1]}{flag}  {marks if flag else ''}", flush=True)
    finally:
        LatticeMazeTool._locate = original
    print(f"\n{changed} of {len(touched)} pairs changed; "
          f"{len(base) - len(touched)} could not")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    if mode == "full":
        full(int(sys.argv[2]) if len(sys.argv) > 2 else 1500)
    elif mode == "see":
        see(sys.argv[2], int(sys.argv[3]) - 1 if len(sys.argv) > 3 else 0)
    else:
        fn = {"same": same, "both": both, "candidate": candidate}[mode]
        fn(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1500)
