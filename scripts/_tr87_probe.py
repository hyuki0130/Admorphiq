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
  3. Whether the dial genuinely CLOSES a 7-state cycle and whether the
     "reverse" action is genuinely the exact inverse at every step -- NOT
     just "7 distinct states were seen" (that alone doesn't prove closure).
     The first version of this probe only chained EXACT frame bytes and ran
     out of connected samples at 7 states without ever observing a return
     to the start -- see "Claims audit" in the design doc for why that was
     an overclaim. This version instead builds an ABSTRACTED graph over
     (column, rotation-invariant signature) states -- correctly merging
     samples that differ in some OTHER column/position but share the same
     dial-state for the column being walked -- using
     data/transitions/train/tr87.npz's 2000 samples, restricted to the two
     actions independently measured to never move the bracket (dial-step
     actions; see column-encoding note below), and additionally verifies
     the bracket truly didn't move on every sample used (not merely
     assumed from the earlier aggregate measurement). Every observed
     `(column, signature, action) -> signature` edge is also checked for
     CONFLICTS (more than one distinct outcome for the same key) rather
     than silently overwritten -- the earlier exact-frame-byte version of
     this probe DID silently overwrite, and a separate Codex review found
     4 conflicting pairs in that version (see
     docs/r56_codex_tr87_review_20260715.md).
  4. Whether a simple PITCH-MULTIPLE SPLITTER recovers the individual
     glyphs a background-gap scan merges into one run (the level-1
     falsification measured in docs/tr87_frame_only_grammar_design_20260715.md
     §7 -- multi-token rule sides render with NO gap between sibling
     glyphs, so `occupied_runs` correctly sees one wide run, not several).
     The splitter is throwaway (not promoted to a kernel yet): detect the
     single-glyph pitch as the smallest run width anywhere on the board,
     then divide every run's width by that pitch to recover its token
     count. Tested against BOTH data/traces/tr87_l1_reset.npz and
     data/traces/tr87_l2_reset.npz (captured via scripts/_tr87_capture_l1.py
     / _l2.py), cross-validated against each level's own oracle rule-table
     token counts (verification-only reads at capture time, hardcoded below
     with provenance -- this section itself makes no live env calls).
"""
from __future__ import annotations

import numpy as np

from admorphiq.kernels import crop_to_content, dihedral_transforms, occupied_runs

BAR1_R0, BAR1_R1, BAR1_FILL = 41, 45, 10
BAR2_R0, BAR2_R1, BAR2_FILL = 52, 56, 7
BAR2_WINDOWS = [(15, 19), (22, 26), (29, 33), (36, 40), (43, 47)]
UPPER_BANDS = [(4, 10), (13, 19), (22, 28)]
BOARD_BG = {2, 3}  # background(2) + padding(3): both are true gaps in the upper grid
INK_COLOR = 5  # constant across every glyph family observed (verified below)
BRACKET_ROWS = (48, 49)
# measured (main(), section 3 below): action id 0/1 never move the bracket in
# data/transitions/train/tr87.npz's 0-indexed action encoding (dial-step
# actions); 2/3 always do (bracket-move actions). This capture's encoding is
# 0-indexed, distinct from the 1-indexed {1,2,3,4} in data/traces/tr87.npz.
DIAL_FORWARD, DIAL_BACKWARD = 1, 0


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


def bracket_x(frame):
    cells = [c for r in BRACKET_ROWS for c in range(frame.shape[1]) if frame[r][c] == 0]
    return sum(cells) / len(cells) if cells else None


def nearest_col(x):
    centers = [(c0 + c1) / 2 for c0, c1 in BAR2_WINDOWS]
    return min(range(len(centers)), key=lambda i: abs(centers[i] - x))


def detect_pitch(runs):
    """Single-glyph pitch: the smallest run width present on the board.

    Assumes at least one run is a genuine single (unmerged) glyph -- true
    on every board measured so far (L0/L1/L2 each have at least one 1-token
    rule side)."""
    return min(r["end"] - r["start"] for r in runs)


def recovered_token_counts(runs, pitch):
    """For each run, how many pitch-wide glyph slots it represents (width // pitch).

    This IS the throwaway recovery heuristic: no gap/marker detection, just
    "assume every run's width is an exact multiple of the observed
    single-glyph pitch, and that multiple is the token count." Returns
    (counts, exact) where exact is False if any run's width was NOT a clean
    multiple of pitch (the heuristic's precondition failing -- would mean
    the recovered counts below are not trustworthy)."""
    counts = []
    exact = True
    for r in runs:
        width = r["end"] - r["start"]
        if pitch <= 0 or width % pitch != 0:
            exact = False
        counts.append(width // pitch if pitch > 0 else width)
    return counts, exact


# Oracle ground truth (verification-only reads via the running game object
# at capture time, scripts/_tr87_capture_l1.py / _tr87_capture_l2.py --
# see docs/tr87_frame_only_grammar_design_20260715.md §7 for the full rule
# tables). Used ONLY to cross-validate the splitter below; this probe makes
# no live env calls of its own. Each level's 6 rules' (LHS, RHS) token
# counts, flattened in rule order (rule0.LHS, rule0.RHS, rule1.LHS, ...) --
# matches the upper-grid's "2 rules per row-band x 3 bands" render order.
L1_ORACLE_TOKEN_COUNTS = [1, 1, 1, 3, 1, 2, 1, 2, 1, 3, 1, 1]
L2_ORACLE_TOKEN_COUNTS = [1, 1, 2, 2, 1, 2, 2, 1, 3, 1, 1, 1]


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

    # ---- section 3: does the dial genuinely CLOSE a 7-state cycle? ----
    d2 = np.load("data/transitions/train/tr87.npz", allow_pickle=True)
    frames2, next_frames2, actions2 = d2["frames"], d2["next_frames"], d2["actions"]
    n = len(frames2)
    print(f"\n[transitions/train] {n} samples, actions present: "
          f"{sorted({int(a) for a in actions2})}")

    # Build the ABSTRACTED (column, signature, action) -> signature graph.
    # Every dial-step sample (action in {0,1}) is used, but ONLY after
    # verifying (per-sample, not assumed) that the bracket column is
    # unchanged before/after -- a genuine precondition check, not inherited
    # from the earlier aggregate measurement. Observations are collected as
    # SETS first (not a plain dict) so a conflicting/nondeterministic edge
    # is DETECTED and reported, not silently overwritten by whichever
    # sample happened to be processed last -- the earlier exact-frame-byte
    # version of this probe did overwrite silently (Codex's review,
    # docs/r56_codex_tr87_review_20260715.md, found 4 conflicting pairs in
    # that version); this abstracted graph is checked explicitly instead of
    # assuming the same bug can't recur here.
    observations: dict[tuple[int, tuple, int], set] = {}
    used, bracket_moved = 0, 0
    for i in range(n):
        a = int(actions2[i])
        if a not in (DIAL_FORWARD, DIAL_BACKWARD):
            continue
        xb, xa = bracket_x(frames2[i]), bracket_x(next_frames2[i])
        if xb is None or xa is None:
            continue
        col_b, col_a = nearest_col(xb), nearest_col(xa)
        if col_b != col_a:
            bracket_moved += 1
            continue
        c0, c1 = BAR2_WINDOWS[col_b]
        sig_before = canonical_sig(ink_mask(frames2[i], BAR2_R0, BAR2_R1, c0, c1))
        sig_after = canonical_sig(ink_mask(next_frames2[i], BAR2_R0, BAR2_R1, c0, c1))
        observations.setdefault((col_b, sig_before, a), set()).add(sig_after)
        used += 1
    conflicts = {k: v for k, v in observations.items() if len(v) > 1}
    print(f"dial-step samples used for the abstracted graph: {used} "
          f"(bracket unexpectedly moved on {bracket_moved} dial-step samples, excluded)")
    print(f"distinct (column, signature, action) edges: {len(observations)} "
          f"(5 columns x <=7 states x 2 actions = 70 max)")
    print(f"edges with CONFLICTING (nondeterministic) outcomes across samples: {len(conflicts)}")
    edges = {k: next(iter(v)) for k, v in observations.items() if len(v) == 1}

    for col in range(5):
        states = sorted({s for (c, s, _a) in edges if c == col})
        if not states:
            print(f"column {col}: no dial-step samples observed")
            continue
        start = states[0]
        path = [start]
        cur = start
        closure_hop = None
        for step in range(len(states) + 2):
            nxt = edges.get((col, cur, DIAL_FORWARD))
            if nxt is None:
                break
            if nxt == start:
                closure_hop = step + 1
                path.append(nxt)
                break
            path.append(nxt)
            cur = nxt
        print(f"\ncolumn {col}: {len(states)} distinct canonical states")
        if closure_hop is None:
            print(f"  action={DIAL_FORWARD} walk from a fixed start did NOT return to start "
                  f"within {len(path) - 1} hops (path length {len(path)}) -- closure NOT demonstrated")
            continue
        print(f"  action={DIAL_FORWARD} walk CLOSED after exactly {closure_hop} hops -- "
              f"cycle length CONFIRMED, not inferred from a distinct-state count")

        # Reverse-edge check: for every forward hop s_i -> s_{i+1} on the
        # confirmed cycle, does (col, s_{i+1}, DIAL_BACKWARD) map back to s_i?
        hops = list(zip(path[:-1], path[1:]))
        confirmed = sum(1 for s_i, s_ip1 in hops if edges.get((col, s_ip1, DIAL_BACKWARD)) == s_i)
        print(f"  reverse-action exact-inverse check: {confirmed}/{len(hops)} hops confirmed")

    # Cross-column check: do all 5 columns share the same SET of canonical
    # dial states (not merely the same COUNT)? Reported, not assumed.
    state_sets = [frozenset(s for (c, s, _a) in edges if c == col) for col in range(5)]
    print(f"\nall 5 columns share the exact same canonical state SET (not just the same count)? "
          f"{len(set(state_sets)) == 1}")

    # ---- section 4: does the pitch-multiple splitter recover the tokens the
    # falsified segmentation merged, on BOTH level 1 and level 2? ----
    print("\n" + "=" * 70)
    print("SECTION 4: pitch-multiple splitter, cross-validated against oracle rule tables")
    print("=" * 70)
    for label, npz_path, oracle in [
        ("L1", "data/traces/tr87_l1_reset.npz", L1_ORACLE_TOKEN_COUNTS),
        ("L2", "data/traces/tr87_l2_reset.npz", L2_ORACLE_TOKEN_COUNTS),
    ]:
        frame = np.load(npz_path)["frame"]
        all_runs = []
        band_run_counts = []
        for r0, r1 in UPPER_BANDS:
            out = occupied_runs(frame, axis="col", bbox=(r0, 0, r1, frame.shape[1] - 1), background=BOARD_BG)
            all_runs.extend(out["runs"])
            band_run_counts.append(len(out["runs"]))
        widths = [r["end"] - r["start"] for r in all_runs]
        pitch = detect_pitch(all_runs)
        counts, exact = recovered_token_counts(all_runs, pitch)
        match = counts == oracle
        print(f"\n{label} ({npz_path}):")
        print(f"  runs per band: {band_run_counts} (expect [4, 4, 4] -- 2 rules x (LHS,RHS) per band)")
        print(f"  measured widths: {widths}")
        print(f"  detected pitch: {pitch}px")
        print(f"  arithmetic exact (every width is a clean multiple of pitch)? {exact}")
        print(f"  recovered token counts: {counts}")
        print(f"  oracle token counts:    {oracle}")
        print(f"  {'*** SPLITTER SURVIVES ***' if match else '*** SPLITTER FALSIFIED ***'} "
              f"({label}: recovered == oracle -> {match})")


if __name__ == "__main__":
    main()
