"""R98 window probe — is idx3's board bigger than the frame that shows it?

Purpose
-------
idx3 stops with the compiler finding no satisfying layout across every enumerated
placement, and the leading explanation is that its level is TALLER than the frame:
twenty cells rendered through a sixteen-cell window, so four rows of the board are
outside anything the harness can read. That explanation was reached from the game
source (dev-time) and has never been tested through the official interface.

This probe asks the observable form of the question: when a piece moves, does
content that is NOT the piece TRANSLATE? A fixed window keeps every static pixel
where it was; a scrolling window shifts the whole render, walls and targets
included. It reports the same measurement on idx0, whose board is known to fit,
so the answer has its own control.

Expected feedback
-----------------
Per level, the best whole-frame translation between consecutive frames and how
much of the frame it explains. Offset (0,0) everywhere means the window is FIXED,
and on idx3 that means four board rows are unreachable by construction — a real
ceiling rather than a planner failure. Any other offset on idx3 with idx0 at
(0,0) means the window scrolls and the board can be assembled by scrolling it.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from depth_walk import Walker, play_level  # noqa: E402

from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402


def _pixels(frame) -> list[list[int]]:
    """The last layer of an observation — the settled render."""
    layer = frame[-1]
    return [list(row) for row in layer]


def _best_shift(a: list[list[int]], b: list[list[int]]) -> tuple[tuple[int, int], float]:
    """The whole-frame translation that best maps a onto b, and its agreement.

    Agreement is counted over the overlap only, so a shift is not rewarded for the
    rows it pushes off the edge."""
    h, w = len(a), len(a[0])
    best = ((0, 0), -1.0)
    for dr in range(-8, 9):
        for dc in range(-8, 9):
            same = total = 0
            for r in range(max(0, -dr), min(h, h - dr)):
                for c in range(max(0, -dc), min(w, w - dc)):
                    total += 1
                    same += a[r][c] == b[r + dr][c + dc]
            if total and same / total > best[1]:
                best = ((dr, dc), same / total)
    return best


def probe(w: Walker, level: int) -> None:
    g = FlowGrounding()
    g.observe(0, None, w.obs.frame)
    before = _pixels(w.obs.frame)
    for action in (3, 4, 1, 2):
        w.act(action, g)
        after = _pixels(w.obs.frame)
        (dr, dc), agree = _best_shift(before, after)
        identical = sum(
            before[r][c] == after[r][c] for r in range(len(before)) for c in range(len(before[0]))
        ) / (len(before) * len(before[0]))
        print(f"    idx{level} press {action}: best shift ({dr},{dc}) explains {agree:.3f}; "
              f"unshifted agreement {identical:.3f}", flush=True)
        before = after
    scale = g.scale()
    print(f"    idx{level} scale={scale.value if scale is not UNKNOWN else 'UNKNOWN'} "
          f"frame={len(before)}x{len(before[0])}", flush=True)


def main() -> int:
    w = Walker()
    print("[window probe] does non-piece content translate when a piece moves?\n")
    print("  idx0 (control — board known to fit the frame)")
    probe(w, 0)
    for i in range(3):
        if not w.alive:
            print(f"  game over before idx{i + 1}")
            return 0
        ok, note = play_level(w)
        print(f"  idx{i}: {'CLEARED' if ok else 'stopped'} — {note}", flush=True)
        if not ok:
            print("  could not reach idx3")
            return 0
    print("\n  idx3 (the level whose board is suspected to exceed the frame)")
    probe(w, 3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
