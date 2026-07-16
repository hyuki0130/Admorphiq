"""Decode s5i5 a48e4b1d L0 (the variant the VM loads, which the adapter scores 0/8
on): identify which colour-13 markers are GOALS (move on a track click) vs TARGETS
(static), since on this variant goal and target share colour AND size (both 4) so
the adapter's size-split detects zero goals. Loads a48e4b1d unambiguously by moving
the 18d95033 dir aside (restored in finally). Verification-only.

Usage: uv run python scripts/_s5i5_decode_a48.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from admorphiq.adapters25 import s5i5  # noqa: E402
from admorphiq.adapters25.base import (  # noqa: E402
    canonical_layer,
    click_action,
    most_common_color,
    reset_action,
)
from admorphiq.kernels import find_regions  # noqa: E402

_18D = REPO / "environment_files" / "s5i5" / "18d95033"
_ASIDE = Path("/tmp/s5i5_18d95033_decode_aside")


def _markers(grid):
    bg = most_common_color(grid)
    regs = find_regions(grid, background=bg, connectivity=8)
    return sorted(
        ([int(x) for x in s5i5._centroid(r)], int(r["size"])) for r in regs if r["color"] == s5i5._MARKER_COLOR
    )


def _all_regions(grid):
    """Every non-background region as (color, size, centroid) — to find the movable
    GOAL regardless of colour (the v2 variant may remap the goal's colour)."""
    bg = most_common_color(grid)
    regs = find_regions(grid, background=bg, connectivity=8)
    return sorted(
        (int(r["color"]), int(r["size"]), tuple(int(x) for x in s5i5._centroid(r))) for r in regs
    )


def _moved_any(before, after):
    """Regions (color,size,centroid) that shifted, matched by (color,size) nearest."""
    out = []
    for col, sz, bc in before:
        same = [a for a in after if a[0] == col and a[1] == sz]
        if not same:
            out.append((col, sz, bc, "GONE"))
            continue
        nn = min(same, key=lambda a: abs(a[2][0] - bc[0]) + abs(a[2][1] - bc[1]))
        d = (nn[2][0] - bc[0], nn[2][1] - bc[1])
        if d != (0, 0):
            out.append((col, sz, bc, f"->{nn[2]} d={d}"))
    return out


def _tracks(grid):
    bg = most_common_color(grid)
    regs = find_regions(grid, background=bg, connectivity=8)
    pts = []
    for r in regs:
        if r["color"] != s5i5._TRACK_COLOR:
            continue
        r0, c0, r1, c1 = r["bbox"]
        mr, mc = (r0 + r1) // 2, (c0 + c1) // 2
        pts.extend([(mr, c1), (mr, c0), (r1, mc), (r0, mc)])
    return sorted(set(pts))


def main() -> None:
    from arc_agi import Arcade, OperationMode

    shutil.move(str(_18D), str(_ASIDE))
    print("moved 18d95033 aside — only a48e4b1d loads")
    try:
        arcade = Arcade(operation_mode=OperationMode.OFFLINE)
        env = arcade.make("s5i5")
        obs = env.step(reset_action())
        grid = canonical_layer(obs)
        seed_markers = _markers(grid)
        tracks = _tracks(grid)
        print(f"a48e4b1d L0 seed colour-13 markers (centroid,size): {seed_markers}")
        print(f"  tracks (edge-midpoints): {tracks}")
        print(f"  #markers={len(seed_markers)}  sizes={[s for _c, s in seed_markers]}")

        print("\nseed all regions (color,size,centroid):")
        for r in _all_regions(grid):
            print("   ", r)

        # Probe each track edge-midpoint from a FRESH reset; report ANY region that
        # moved (all colours), to find the movable goal.
        print("\n== track-edge probes (all-colour movement) ==")
        for k, (tr, tc) in enumerate(tracks):
            obs = env.step(reset_action())
            before = _all_regions(canonical_layer(obs))
            ac = click_action(x=tc, y=tr)
            obs = env.step(ac, data=ac.action_data.model_dump())
            moved = _moved_any(before, _all_regions(canonical_layer(obs)))
            print(f"track[{k}] click(row={tr},col={tc}): {moved if moved else '(nothing moved)'}")

        # Also probe the colour-4 control boxes (directional slider controls).
        controls = sorted(set(s5i5.Adapter()._control_buttons(
            find_regions(grid, background=most_common_color(grid), connectivity=8), grid)))
        print("\n== control-box probes (all-colour movement) ==")
        for k, (cr, cc) in enumerate(controls):
            obs = env.step(reset_action())
            before = _all_regions(canonical_layer(obs))
            ac = click_action(x=cc, y=cr)
            obs = env.step(ac, data=ac.action_data.model_dump())
            moved = _moved_any(before, _all_regions(canonical_layer(obs)))
            print(f"control[{k}] click(row={cr},col={cc}): {moved if moved else '(nothing moved)'}")
    finally:
        shutil.move(str(_ASIDE), str(_18D))
        print("restored 18d95033")


if __name__ == "__main__":
    main()
