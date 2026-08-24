"""R98 shortlist probe — WHICH source names the oversized target on idx2?

Purpose
-------
idx2's entire replay residual is one region the grounding admits as a target: nineteen
cells over seven rows, where the level's real targets are five-cell cups. Two notch
discriminators were measured against it and neither removed it, which means it does not
enter through the notch filter. `sink_candidates()` draws from four independent sources
and the filter runs after all of them, so the question is which source names it.

This walks to idx2 with the real driver, then asks each source directly, without
changing what any of them does.

Expected feedback
-----------------
One line per source with the region sizes it proposes. A source that proposes the
oversized region is where the fix belongs; a source that does not is exonerated. If
several propose it, the region is over-determined and removing it needs all of them.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from depth_walk import Walker, play_level  # noqa: E402

from admorphiq.hypothesis_select.grounding_flow import UNKNOWN, FlowGrounding  # noqa: E402


def _sizes(groups) -> list[int]:
    return sorted(len(g) for g in groups)


def report(g: FlowGrounding) -> None:
    changed: list = []
    for anim in g._animations:
        for region in anim.changed_regions:
            if region not in changed:
                changed.append(region)
    print(f"  changed-appearance regions : {_sizes(changed)}", flush=True)
    print(f"  obstruction regions        : {_sizes(g._obstruction_regions())}", flush=True)
    print(f"  matching-shape regions     : {_sizes(g._matching_shape_regions(changed))}",
          flush=True)
    print(f"  wearing-the-appearance     : {_sizes(g._appearance_regions(changed))}",
          flush=True)
    shortlist = g.sink_candidates()
    # Each entry is a (name, cells) PAIR. Taking len() of the pair reports "2" for every
    # region regardless of its size — measured, and it made a nineteen-cell region look
    # like a two-cell one.
    sizes = ("UNKNOWN" if shortlist is UNKNOWN
             else sorted(len(cells) for _, cells in shortlist.value))
    print(f"  SHORTLIST after filtering  : {sizes}", flush=True)


def main() -> int:
    w = Walker()
    for i in range(2):
        ok, note = play_level(w)
        print(f"  idx{i}: {'CLEARED' if ok else 'stopped'} — {note}", flush=True)
        if not ok:
            print("  could not reach idx2")
            return 0
    # Ground idx2 in the driver's own order, reporting at each stage. The oversized
    # region is absent at first grounding, so WHEN it appears is as much the question as
    # which source names it.
    g = FlowGrounding()
    g.observe(0, None, w.obs.frame)
    for a in (1, 1, 2, 3, 4):
        w.act(a, g)
    print("\nidx2 after the direction probes:")
    report(g)

    w.act(5, g)
    print("\nidx2 after the sacrificial commit:")
    report(g)

    candidates = g.selection_candidates()
    if candidates is not UNKNOWN:
        for cell in candidates.value[:6]:
            w.click(cell, g)
    print("\nidx2 after the selection probes:")
    report(g)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
