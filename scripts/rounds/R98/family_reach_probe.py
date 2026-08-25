"""R98 family reach — does the harness READ any game besides the one it was built on?

Purpose
-------
The near-OOD screen, widened to all twenty-five games, found the family's structural
tell — a scripted multi-tick consequence from one action — on TEN of them, two bursting
harder than sp80. That is the observable precondition for reaching for a
place-then-propagate model, not membership. The question it leaves is the one that
decides whether "family" is a real word here: given the same discovery the oracle gate
spends, does the grounding ASSEMBLE A BOARD on any of them?

The OOD certification already answers it for two games chosen as controls, and both
decline at perception. It has never been asked of the candidates that outrank them.

Expected feedback
-----------------
Per candidate: the board it assembled, or the slots it could not read. A candidate that
assembles a board is a family member the round never measured; one that declines is a
game whose tell is structural only, and the harness is that much more sp80's than the
family's.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ood_certification import _play  # noqa: E402

from admorphiq.hypothesis_select.grounding_flow import UNKNOWN  # noqa: E402

# Every game whose burst matched or beat the oracle's, plus the two that follow it. The
# controls are excluded: they already have their answer.
CANDIDATES = ("sb26", "lf52", "sc25", "cd82", "g50t")


def main() -> int:
    reads = []
    for prefix in CANDIDATES:
        g, gid = _play(prefix)
        if g is None:
            print(f"  {prefix}: {gid}")
            continue
        board = g.board()
        if board is UNKNOWN:
            slots = {name: getattr(g, name)() for name in
                     ("pieces", "sink_candidates", "barriers", "initial_direction",
                      "emitters", "trajectory")}
            missing = [n for n, v in slots.items() if v is UNKNOWN]
            print(f"  {gid}: DECLINES — no board; unread: "
                  f"{', '.join(missing) if missing else 'nothing (board() itself)'}")
            continue
        b = board.value
        reads.append(gid)
        print(f"  {gid}: READS — {len(b.sinks)} target(s), {len(b.pieces)} piece(s), "
              f"direction {b.direction}, size {b.size}")
    print(f"\n[family reach] {len(reads)} of {len(CANDIDATES)} candidate(s) assemble a board"
          + (f": {', '.join(reads)}" if reads else
             " — the harness reads its own game and no other"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
