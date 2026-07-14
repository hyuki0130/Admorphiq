"""THROWAWAY offline probe (NOT part of the shipped agent, not wired into any
test suite by design): does frame-only glyph tokenization for TR87's
rewrite-grammar win rule (see .wiki/wiki/rounds/r53_unified-harness.md,
"TR87 win-rule CRACKED") actually work against real captured frames?

Reads ONLY already-captured .npz files under data/ -- no live env stepping,
no game actions spent. Uses the R56 kernels (admorphiq.kernels.shapes) to
build rotation-invariant glyph signatures, then checks:

  1. Column/window layout of bar1 (target) / bar2 (editable) / the upper-grid
     rule-table blocks, via a background-gap scan (not find_regions -- see
     the design note this feeds, docs/tr87_frame_only_grammar_design_20260715.md,
     for why single-colour connected components fragment a 2-colour glyph).
  2. Whether NAIVE translation-only shape matching vs ROTATION-INVARIANT
     (dihedral) matching produce different alphabet sizes when comparing
     bar1/bar2's glyphs against the upper-grid rule-table's glyphs -- i.e.
     whether tr87.py's per-glyph independent random on-screen rotation
     (`set_rotation(random.choice([0, 90, 180, 270]))`, read verification-
     only, never touched by any solver) is a REAL confound for naive shape
     hashing, not just a theoretical one.
  3. Whether the dial genuinely cycles through exactly 7 distinct states
     (re-deriving tr87.py's `kjgicbtgrt = 7` independently from frames),
     using data/transitions/train/tr87.npz's connected transition graph
     (before/after frames chain: 1927/2000 samples connect to another
     sample's frame, confirmed below -- NOT a continuous single trace, but
     graph-connected enough to walk multi-step chains).
"""
from __future__ import annotations

import numpy as np

from admorphiq.kernels import crop_to_content, dihedral_transforms

BAR1_R0, BAR1_R1, BAR1_FILL = 41, 45, 10
BAR2_R0, BAR2_R1, BAR2_FILL = 52, 56, 7
BAR2_WINDOWS = [(15, 19), (22, 26), (29, 33), (36, 40), (43, 47)]
UPPER_BANDS = [(4, 10), (13, 19), (22, 28)]
BOARD_BG = {2, 3}  # background(2) + padding(3): both are true gaps in the upper grid
INK_COLOR = 5  # constant across every glyph family observed (verified below)
BRACKET_ROWS = (48, 49)


def gap_windows(frame, r0, r1, bg_colors, scan_c0=None, scan_c1=None):
    """Contiguous x-ranges (within [scan_c0, scan_c1]) where some row in
    [r0, r1] is NOT in bg_colors -- i.e. one glyph cell's pixel window."""
    c_lo = 0 if scan_c0 is None else scan_c0
    c_hi = frame.shape[1] - 1 if scan_c1 is None else scan_c1
    windows, in_glyph, start = [], False, None
    for c in range(c_lo, c_hi + 1):
        differs = any(frame[r][c] not in bg_colors for r in range(r0, r1 + 1))
        if differs and not in_glyph:
            in_glyph, start = True, c
        elif not differs and in_glyph:
            windows.append((start, c - 1))
            in_glyph = False
    if in_glyph:
        windows.append((start, c_hi))
    return windows


def band_extent(frame, r0, r1, fill_color):
    """The bar's own true horizontal span (where its fill colour appears at all)."""
    cols = [c for c in range(frame.shape[1]) if any(frame[r][c] == fill_color for r in range(r0, r1 + 1))]
    return min(cols), max(cols)


def ink_mask(frame, r0, r1, c0, c1, ink_color=INK_COLOR):
    return tuple(tuple(frame[r][c] == ink_color for c in range(c0, c1 + 1)) for r in range(r0, r1 + 1))


def translation_sig(mask):
    return crop_to_content(mask)["mask"]


def canonical_sig(mask):
    """Rotation+reflection-invariant signature: smallest cropped mask over all 8 dihedral transforms."""
    return min(crop_to_content(t["mask"])["mask"] for t in dihedral_transforms(mask))


def upper_grid_masks(frame):
    out = []
    for r0, r1 in UPPER_BANDS:
        for c0, c1 in gap_windows(frame, r0, r1, BOARD_BG):
            out.append(ink_mask(frame, r0, r1, c0, c1))
    return out


def main() -> None:
    d = np.load("data/traces/tr87.npz", allow_pickle=True)
    frames = d["frames"]
    f0 = frames[0]
    print(f"[traces] {len(frames)} frames loaded; all identical (single fixed-reset dataset)? "
          f"{all((frames[i] == f0).all() for i in range(len(frames)))}")

    print("\ncolours present across upper-grid bands:",
          sorted({int(f0[r][c]) for r0, r1 in UPPER_BANDS for r in range(r0, r1 + 1) for c in range(64)}))

    bar1_c0, bar1_c1 = band_extent(f0, BAR1_R0, BAR1_R1, BAR1_FILL)
    bar1_windows = gap_windows(f0, BAR1_R0, BAR1_R1, {BAR1_FILL}, bar1_c0, bar1_c1)
    bar1_masks = [ink_mask(f0, BAR1_R0, BAR1_R1, c0, c1) for c0, c1 in bar1_windows]
    print(f"\nbar1 windows: {bar1_windows}")

    upper_masks = upper_grid_masks(f0)
    print(f"upper-grid glyph blocks found: {len(upper_masks)} (level 0 has 6 rules "
          f"per tr87.py's marker list -- verification-only read -- so 12 LHS+RHS "
          f"single-glyph slots is the expected count for this level)")

    bar1_trans, bar1_canon = [translation_sig(m) for m in bar1_masks], [canonical_sig(m) for m in bar1_masks]
    upper_trans, upper_canon = [translation_sig(m) for m in upper_masks], [canonical_sig(m) for m in upper_masks]
    print(f"\nbar1 <-> upper-grid overlap: "
          f"translation-only={len(set(bar1_trans) & set(upper_trans))}/5, "
          f"rotation-invariant={len(set(bar1_canon) & set(upper_canon))}/5")
    print("  ^ THIS is the load-bearing measurement: naive shape matching finds almost none of "
          "bar1's targets among the rule-table glyphs; dihedral-canonical matching finds nearly all.")

    # ---- 7-state dial cycle, via the connected transition graph ----
    d2 = np.load("data/transitions/train/tr87.npz", allow_pickle=True)
    frames2, next_frames2, actions2 = d2["frames"], d2["next_frames"], d2["actions"]
    before_set = {f.tobytes() for f in frames2}
    after_set = {f.tobytes() for f in next_frames2}
    print(f"\n[transitions/train] {len(frames2)} samples, "
          f"{len(before_set & after_set)}/{len(before_set)} before-frames chain into another sample")

    edges = {}
    frame_by_bytes = {}
    for i in range(len(frames2)):
        k, nk = frames2[i].tobytes(), next_frames2[i].tobytes()
        frame_by_bytes[k], frame_by_bytes[nk] = frames2[i], next_frames2[i]
        edges[(k, int(actions2[i]))] = nk

    def bracket_x(frame):
        cells = [c for r in BRACKET_ROWS for c in range(frame.shape[1]) if frame[r][c] == 0]
        return sum(cells) / len(cells) if cells else None

    def nearest_col(x):
        centers = [(c0 + c1) / 2 for c0, c1 in BAR2_WINDOWS]
        return min(range(len(centers)), key=lambda i: abs(centers[i] - x))

    start_key = frames2[0].tobytes()
    col = nearest_col(bracket_x(frame_by_bytes[start_key]))
    c0, c1 = BAR2_WINDOWS[col]
    # measured separately: action id 0/1 never move the bracket (dial-step actions),
    # 2/3 always do (bracket-move actions) -- 0-indexed encoding in this capture,
    # distinct from the 1-indexed {1,2,3,4} in data/traces/tr87.npz.
    cur, canon_path, trans_path = start_key, [], []
    for _ in range(8):
        canon_path.append(canonical_sig(ink_mask(frame_by_bytes[cur], BAR2_R0, BAR2_R1, c0, c1)))
        trans_path.append(translation_sig(ink_mask(frame_by_bytes[cur], BAR2_R0, BAR2_R1, c0, c1)))
        nxt = edges.get((cur, 1))
        if nxt is None or nxt == start_key:
            break
        cur = nxt
    print(f"\ndial chain (action=1, dial-step) from a fixed start: {len(canon_path)} states reached "
          f"before the sample graph ran out")
    print(f"  distinct rotation-invariant signatures: {len(set(canon_path))}")
    print(f"  distinct translation-only signatures:   {len(set(trans_path))}  "
          f"(equal counts -> a slot's own on-screen rotation stays FIXED across its 7-state cycle)")


if __name__ == "__main__":
    main()
