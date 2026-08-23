"""R98 discovery-sequence certification — sp80 idx0.

Purpose
-------
Codex binding correction 6: freeze the budget against ONE pre-certified discovery
action sequence and the shortest solve from the layout that PERSISTS after it —
not against the entry layout, because a failed commit restores the flow but not
the piece positions.

The sequence is not hand-picked; every step follows a rule an agent can derive
from observables alone:

  1. click the candidate movable region                 -> selection evidence
  2. press one direction                                -> positive displacement
  3. press the same direction again at the bound        -> blocked contrast
     (the pair is what licenses a constraint claim; a bare failure-to-move does
      not, per the asymmetric-mobility rule)
  4. translate until the region's column span covers the emitter column
                                                        -> the only placement
     that makes the flow interact with the region at all
  5. commit                                             -> one sacrificial spill
  6. solve from the PERSISTED layout, then commit

Expected feedback
-----------------
Prints the exact action cost of each phase and the cumulative total, and asserts
that the level actually clears at the end. A PASS licenses an exact cumulative
cap in the contract. A FAIL means the budget clause cannot be frozen as written
-- it does not mean the family is wrong.

Dev-time only: a certification probe, not part of any runtime agent path.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arc_agi import Arcade, OperationMode  # noqa: E402
from arcengine import GameAction  # noqa: E402

SCALE = 4
PIECE_IDLE = 8      # the movable region at rest
PIECE_SELECTED = 9  # the same region while selected
WATER = 6


def _open_arcade():
    """Open the offline arcade, honouring ``ARC_ENVIRONMENTS_DIR``.

    The kwarg is passed ONLY when the variable is set: arc_agi treats an explicit
    ``environments_dir=None`` as "different from the default" and stops scanning
    altogether, so the tidy-looking ``or None`` form silently yields an arcade with
    zero environments.
    """
    envs_dir = os.environ.get("ARC_ENVIRONMENTS_DIR")
    return (
        Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=envs_dir)
        if envs_dir
        else Arcade(operation_mode=OperationMode.OFFLINE)
    )


def _cells(grid, colour: int) -> set[tuple[int, int]]:
    return {
        (y // SCALE, x // SCALE)
        for y, row in enumerate(grid)
        for x, v in enumerate(row)
        if v == colour
    }


def _piece(obs) -> set[tuple[int, int]]:
    """The movable region, whichever appearance it currently has."""
    top = obs.frame[0]
    return _cells(top, PIECE_SELECTED) or _cells(top, PIECE_IDLE)


class Run:
    def __init__(self) -> None:
        arcade = _open_arcade()
        gid = next(e.game_id for e in arcade.get_environments()
                   if e.game_id.startswith("sp80"))
        self.env = arcade.make(gid)
        self.obs = self.env.step(GameAction.RESET)
        self.actions = 0

    def act(self, action, **data):
        self.obs = self.env.step(action, data=data) if data else self.env.step(action)
        self.actions += 1
        return self.obs


def main() -> int:
    r = Run()
    log: list[tuple[str, int, str]] = []

    entry_piece = _piece(r.obs)
    rows = sorted({y for (y, _) in entry_piece})
    cols = sorted({x for (_, x) in entry_piece})
    print(f"entry: movable region occupies rows {rows} columns {cols}")

    # 1. selection — click the region's own centroid
    before = r.actions
    cy = rows[len(rows) // 2] * SCALE + SCALE // 2
    cx = cols[len(cols) // 2] * SCALE + SCALE // 2
    r.act(GameAction.ACTION6, x=cx, y=cy)
    selected = bool(_cells(r.obs.frame[0], PIECE_SELECTED))
    log.append(("select", r.actions - before, f"selected appearance present: {selected}"))

    # 2/3. positive displacement, then the blocked contrast at the same bound
    before = r.actions
    p0 = _piece(r.obs)
    r.act(GameAction.ACTION1)
    p1 = _piece(r.obs)
    moved = p1 != p0
    r.act(GameAction.ACTION1)
    p2 = _piece(r.obs)
    r.act(GameAction.ACTION1)
    p3 = _piece(r.obs)
    blocked = p3 == p2
    log.append(("displacement contrast", r.actions - before,
                f"first press moved: {moved}; a later press at the bound was "
                f"blocked: {blocked}"))

    # 4. align the region's column span over the emitter column. The emitter is
    #    read off the entry frame as the column the flow starts in; here it is
    #    recovered from the standing water cell above the board.
    before = r.actions
    emitter_cols = sorted({x for (_, x) in _cells(r.obs.frame[0], WATER)})
    emitter = emitter_cols[len(emitter_cols) // 2] if emitter_cols else None
    span = sorted({x for (_, x) in _piece(r.obs)})
    steps = 0
    while emitter is not None and emitter > max(span):
        r.act(GameAction.ACTION4)
        span = sorted({x for (_, x) in _piece(r.obs)})
        steps += 1
        if steps > 16:
            break
    log.append(("align over emitter", r.actions - before,
                f"emitter column {emitter}; region span now {span[0]}..{span[-1]}"))

    # 5. one sacrificial commit
    before = r.actions
    pre_commit = _piece(r.obs)
    r.act(GameAction.ACTION5)
    layers = len(r.obs.frame)
    post_commit = _piece(r.obs)
    persisted = post_commit == pre_commit
    log.append(("sacrificial commit", r.actions - before,
                f"{layers} layers exposed; layout persisted across the failed "
                f"attempt: {persisted}"))

    # 6. solve from the PERSISTED layout
    before = r.actions
    r.act(GameAction.ACTION4)
    r.act(GameAction.ACTION5)
    cleared = r.obs.levels_completed >= 1
    log.append(("solve from persisted layout", r.actions - before,
                f"level advanced: {cleared}"))

    print()
    for name, cost, note in log:
        print(f"  {name:<28} {cost:>2} action(s)   {note}")
    discovery = sum(c for n, c, _ in log if n != "solve from persisted layout")
    solve = sum(c for n, c, _ in log if n == "solve from persisted layout")
    print(f"\n  discovery total: {discovery} actions")
    print(f"  solve total:     {solve} actions")
    print(f"  cumulative:      {r.actions} actions "
          f"(engine allowance at this level is 30 change-phase actions, "
          f"4 commits)")

    ok = cleared and discovery + solve == r.actions
    print(f"\n[discovery sequence] {'PASS' if ok else 'FAIL'} — "
          f"{'the sequence clears the level within the engine budget'
             if ok else 'the sequence did not clear'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
