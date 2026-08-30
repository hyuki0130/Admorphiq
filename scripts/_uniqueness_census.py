"""Census, part two: identity taken from being the SOLE WEARER of a colour.

⛔ WHY THIS IS THE SAME CLASS AND NOT A SECOND ONE. Rule 7cd's site loses an object when the render
HIDES it. `lattice_maze._locate` records the mirror image, measured by a peer on 2026-08-27 and
already repaired: on the archived re-render of that game the maze sprite is drawn at a different
z-order and COVERS a second piece, so *"the only thing of my colour"* is true on one copy and false
on the other. The tool fell through to a centroid of every pixel of that colour, which averages two
pieces to a point between them, and the board went from **9 levels in 188 actions to 4 in 1288**.

So occlusion does not only REMOVE the evidence a tool identifies by (7cd); it also FORGES it. Both
halves are "identity read out of paint order", and a census of the class has to count both.

The sites, each read in full before being wrapped:

    lattice_maze._locate    `same` = pieces wearing my body colour; unique -> me   (REPAIRED — the
                            repair is what this probe checks is load-bearing)
    tube._candidates        a colour group holding ONE tube is the live pair, `out or every tube`
    cover_targets._track    `sole` = no other part wears this colour; decides whether motion is
                            taken as extra evidence about the piece's shape

⚠️ `ledge._avatar` belongs here too and is already counted by `scripts/_visibility_census.py`;
it is not re-counted, to keep the two probes' numbers addable.

⛔ Rule 7g: a site that never reaches its ambiguous branch costs nothing, so what is recorded is
how often the branch is REACHED and how often the uniqueness test actually decides something.

⛔ RUN IT ON BOTH BOARDS, for the reason this probe exists to record: the LIVE tu93 never once
reaches `lattice_maze._locate`'s ambiguous branch, and the ARCHIVED copy of that same game is where
the whole incident happened. A live-only census understates the class by construction.

  bash scripts/pfan.sh uniqcensus  scripts/_uniqueness_census.py 25 ""   10
  bash scripts/pfan.sh uniqcensusA scripts/_uniqueness_census.py 25 arch 10
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

BUDGET = 4000


def _install(tally: Counter) -> None:
    from admorphiq.tools import cover_targets as ct
    from admorphiq.tools import lattice_maze as lm
    from admorphiq.tools import tube as tb

    def note(site: str, outcome: str) -> None:
        tally[f"{site}.{outcome}"] += 1

    # --- lattice_maze: the repaired site ------------------------------------
    lm_loc = lm.LatticeMazeTool._locate

    def lm_wrap(self, board):  # noqa: ANN001, ANN202
        got = lm_loc(self, board)
        note("lattice_maze._locate", "fires")
        if self._body is not None:
            same = [c for c, (body, _) in board.pieces.items() if body == self._body]
            # ⭐ THE FIELD THAT SAYS WHETHER THE REPAIR IS LOAD-BEARING. `== 1` is the branch the
            # OLD code was right about; anything else is where it went to a centroid and lost the
            # piece, and where the repair's position-carrying does the work instead.
            note("lattice_maze._locate",
                 "unique" if len(same) == 1 else ("none_drawn" if not same else "shared"))
        if got is None:
            note("lattice_maze._locate", "returned_none")
        return got

    lm.LatticeMazeTool._locate = lm_wrap

    # --- tube: a colour group holding one tube, else EVERY tube -------------
    tb_cand = tb._candidates

    def tb_wrap(board):  # noqa: ANN001, ANN202
        out = tb_cand(board)
        note("tube._candidates", "fires")
        n = len(board.tubes)
        if not out:
            note("tube._candidates", "fallback")
        elif len(out) < n:
            note("tube._candidates", "narrows")
        else:
            note("tube._candidates", "no_effect")
        return out

    tb._candidates = tb_wrap

    # --- cover_targets: the `sole` guard inside _attribute -------------------
    ct_attr = ct.CoverTargetsTool._attribute

    def ct_wrap(self, cells, vec):  # noqa: ANN001, ANN202
        out = ct_attr(self, cells, vec)
        note("cover_targets._attribute", "fires")
        # ⚠️ Count over EVERY part, not over whichever one `_attribute` happened to choose:
        # picking a part index out of the tool's state after the call would be attribution by
        # proximity, which rule 7b bans. What the uniqueness test can decide is a property of the
        # whole part list, and that is what is measured.
        for part in self._parts:
            sole = part["colour"] is not None and sum(
                1 for q in self._parts if q["colour"] == part["colour"]) == 1
            note("cover_targets._attribute", "part_sole" if sole else "part_shared")
        return out

    ct.CoverTargetsTool._attribute = ct_wrap


def main() -> None:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    arm = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else "live"

    from arc_agi import Arcade, OperationMode

    tally: Counter = Counter()
    _install(tally)

    # One implementation of the substitution, imported rather than copied: two probes that build
    # the archived tree differently would be two boards wearing one name (rule 7bu's shape).
    from _visibility_census import env_dir
    from score_efficiency import run_game

    where = env_dir(arm)
    arcade = (Arcade(operation_mode=OperationMode.OFFLINE, environments_dir=where)
              if where else Arcade(operation_mode=OperationMode.OFFLINE))
    seen: set[str] = set()
    uniq = []
    for e in arcade.get_environments():
        if e.game_id not in seen:
            seen.add(e.game_id)
            uniq.append(e)
    if seed > len(uniq):
        print(json.dumps({"seed": seed, "arm": arm, "skipped": True, "n_games": len(uniq)}))
        return
    info = uniq[seed - 1]
    res = run_game(arcade, info.game_id, info.baseline_actions,
                   agent_name="unified", max_actions=BUDGET)
    print(json.dumps({
        "seed": seed,
        "arm": arm,
        "game": info.game_id,
        "game_score": res.get("game_score"),
        "levels": res.get("levels_completed"),
        "tally": dict(sorted(tally.items())),
    }))


if __name__ == "__main__":
    main()
