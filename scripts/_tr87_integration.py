"""THROWAWAY offline integration test (NOT shipped, NOT wired into any test
suite): does a genuinely frame-only pipeline -- discover structural bands,
group raw rule-side runs, split multi-token runs via the promoted
`kernels.parse.split_runs_by_pitch`, canonicalize tokens with C4-ONLY
rotation (per Codex's re-ruling, `docs/r56_codex_tr87_reruling_20260715.md`
step 2 -- NOT full D4, which the earlier probe used and which risks
collapsing distinct chiral tokens) -- correctly extract TR87's six rules
and predict bar2's target token sequence from bar1, matching the oracle
exactly on all three captured levels (L0/L1/L2)?

Reads ONLY already-captured .npz files (data/traces/tr87.npz frame 0,
data/traces/tr87_l1_reset.npz, data/traces/tr87_l2_reset.npz) -- no live env
calls in this script at all. The OPERATIONAL PATH (background discovery,
band discovery, band role classification, rule-side grouping, pitch
splitting, token canonicalization, rule extraction, greedy_parse) uses NO
fixed pixel coordinates and NO fixed palette constants -- every one of
those is discovered from the frame itself, composing existing kernels
(occupied_runs, color_mode, cluster_widths, split_runs_by_pitch,
dihedral_transforms, crop_to_content, greedy_parse). Oracle sprite names
(hardcoded below, from the same verification-only reads the capture
scripts already made) are used ONLY in the FINAL comparison step, to label
which predicted canonical signature corresponds to which real rule/token
identity and to check the prediction is correct -- never inside the
pipeline itself. This is the explicit boundary Codex's ruling drew:
"oracle only for the final comparison."

Two structural priors ARE declared (not pixel coordinates, not colours --
observed BOARD STRUCTURE, matching the R56 declared-intent doctrine that
a caller may declare roles/structure, just not hardcode coordinates):
  - A "rule-table" band is one whose column-projection (under the
    discovered board background) yields exactly 4 raw runs whose 3 gaps
    have a [small, LARGE, small] shape (the larger gap in the middle
    splits the band's two rules; the two smaller gaps are each one rule's
    own LHS|RHS split) -- this is the actual measured [3, 6, 3] signal,
    generalized to "find the largest of the 3 gaps," not hardcoded to the
    literal numbers 3 and 6.
  - Of the two remaining tall bands, the one with the SMALLER row start is
    bar1 (the static target row); the other is bar2 (the editable row) --
    bar1 always renders above bar2 in every level captured so far.
"""
from __future__ import annotations

import numpy as np

from admorphiq.kernels import (
    cluster_widths,
    color_mode,
    crop_to_content,
    dihedral_transforms,
    greedy_parse,
    occupied_runs,
    split_runs_by_pitch,
)

# ---- oracle ground truth (verification-only reads at capture time; see
# scripts/_tr87_capture_l1.py / _l2.py and docs/tr87_frame_only_grammar_design_20260715.md
# §7/§8 for provenance). Used ONLY for the final comparison, never inside
# the discovery/extraction pipeline. Rules are (LHS_names, RHS_names) in
# the SAME left-to-right, top-to-bottom board order the pipeline extracts
# them in (2 rules per rule-table band, 3 bands). ----
ORACLE = {
    "L0": {
        "npz": "data/traces/tr87.npz",
        "frame_key": ("frames", 0),
        "rules": [
            (["A3"], ["B6"]), (["A5"], ["B5"]), (["A1"], ["B1"]),
            (["A4"], ["B3"]), (["A2"], ["B2"]), (["A7"], ["B7"]),
        ],
        "bar1": ["A4", "A2", "A3", "A5", "A1"],
    },
    "L1": {
        "npz": "data/traces/tr87_l1_reset.npz",
        "frame_key": ("frame",),
        "rules": [
            (["B1"], ["C3"]), (["B4"], ["C4", "C3", "C6"]), (["B6"], ["C4", "C2"]),
            (["B5"], ["C2", "C2"]), (["B3"], ["C1", "C5", "C1"]), (["B7"], ["C7"]),
        ],
        "bar1": ["B1", "B3", "B5", "B7"],
    },
    "L2": {
        "npz": "data/traces/tr87_l2_reset.npz",
        "frame_key": ("frame",),
        "rules": [
            (["C6"], ["A4"]), (["C3", "C3"], ["A6", "A1"]), (["C4"], ["A7", "A7"]),
            (["C7", "C7"], ["A3"]), (["C1", "C5", "C1"], ["A6"]), (["C2"], ["A5"]),
        ],
        "bar1": ["C6", "C1", "C5", "C1", "C4", "C2", "C3", "C3"],
    },
}


def load_frame(entry):
    d = np.load(entry["npz"], allow_pickle=True)
    key = entry["frame_key"]
    arr = d[key[0]]
    return arr[key[1]] if len(key) > 1 else arr


def discover_background(frame):
    """Board background = the top frequency-tier of the whole-frame colour histogram."""
    all_vals = [int(v) for row in frame for v in row]
    hist = color_mode(all_vals, k=len(set(all_vals)))
    counts = [h["count"] for h in hist]
    clusters = cluster_widths(counts, ratio=1.5)
    return {hist[i]["color"] for i in clusters[-1]}


def discover_bands(frame, bg):
    """Horizontal structural bands: occupied_runs along rows, background-separated."""
    return occupied_runs(frame, axis="row", background=bg)["runs"]


def classify_bands(frame, bands, bg):
    """Split bands into (rule_bands[3], bar1_band, bar2_band) by structural signature.

    A band shorter than 4px is a bracket/counter artifact, ignored. Among
    the remaining (tall) bands: a rule-table band's column-projection
    (under `bg`) has exactly 4 runs whose middle gap is the largest of its
    3 gaps -- see module docstring. Everything else tall is a bar band;
    the two bar bands are ordered by row position (bar1 above bar2).
    """
    w = frame.shape[1]
    rule_bands, bar_bands = [], []
    for b in bands:
        if b["end"] - b["start"] < 4:
            continue
        out = occupied_runs(frame, axis="col", bbox=(b["start"], 0, b["end"] - 1, w - 1), background=bg)
        runs, gaps = out["runs"], out["gaps"]
        if len(runs) == 4 and len(gaps) == 3 and gaps[1] > gaps[0] and gaps[1] > gaps[2]:
            rule_bands.append(b)
        else:
            bar_bands.append(b)
    rule_bands.sort(key=lambda b: b["start"])
    bar_bands.sort(key=lambda b: b["start"])
    assert len(rule_bands) == 3, f"expected 3 rule-table bands, got {len(rule_bands)}"
    assert len(bar_bands) == 2, f"expected 2 bar bands, got {len(bar_bands)}"
    return rule_bands, bar_bands[0], bar_bands[1]


def canon_sig_c4(mask):
    """Rotation-ONLY (C4: identity/rot90/rot180/rot270) canonical signature -- no reflections.

    Per Codex's re-ruling: full D4 (dihedral_transforms' default 8-way,
    including 4 mirrored variants) risks collapsing chiral tokens that are
    genuinely different (mirror images of each other) into the same
    signature; this integration test must prove rotation-only identity
    without that collision risk. Slices dihedral_transforms' first 4
    entries (identity, rot90, rot180, rot270 -- its own documented fixed
    order) rather than calling a separate C4-only kernel.
    """
    return min(crop_to_content(t["mask"])["mask"] for t in dihedral_transforms(mask)[:4])


def rectangular_ink_mask(frame, row0, row1, col0, col1):
    """Boolean mask over [row0,row1] x [col0,col1): True where the pixel is the MINORITY colour.

    Discovers fill (majority) vs ink (minority) via color_mode on the
    region's own pixel values -- no fixed ink/fill colour assumed."""
    vals = [frame[r][c] for r in range(row0, row1 + 1) for c in range(col0, col1)]
    hist = color_mode(vals, k=len(set(vals)))
    fill = hist[0]["color"]
    return tuple(tuple(frame[r][c] != fill for c in range(col0, col1)) for r in range(row0, row1 + 1))


def extract_bar1_tokens(frame, bar1_band, bg):
    """bar1's own per-glyph tokens: window by the band's OWN fill colour (not board bg).

    Each of bar1's tokens is a single family with one shared fill colour
    (unlike the rule-table bands, which mix families/fill colours within
    one band) -- discovered here as the majority non-background colour
    within the band, then used AS the background for a second
    `occupied_runs` pass restricted to that colour's own column extent, so
    each glyph is one clean run with no inter-glyph pixel gap needed
    (measured true, no further pitch-splitting needed, on all 3 captured
    levels' bar1)."""
    row0, row1 = bar1_band["start"], bar1_band["end"] - 1
    w = frame.shape[1]
    non_bg_vals = [frame[r][c] for r in range(row0, row1 + 1) for c in range(w) if frame[r][c] not in bg]
    fill = color_mode(non_bg_vals, k=1)[0]["color"]
    fill_cols = [c for c in range(w) if any(frame[r][c] == fill for r in range(row0, row1 + 1))]
    c0, c1 = min(fill_cols), max(fill_cols)
    out = occupied_runs(frame, axis="col", bbox=(row0, c0, row1, c1), background={fill})
    tokens = []
    for run in out["runs"]:
        mask = tuple(
            tuple((r, c) in run["cells"] for c in range(run["start"], run["end"]))
            for r in range(row0, row1 + 1)
        )
        tokens.append(canon_sig_c4(mask))
    return tokens


def extract_rules(frame, rule_bands, bg):
    """Extract the 6 (LHS_tokens, RHS_tokens) rules: group raw sides FIRST, then split.

    Per Codex's ruling: flattening the 4 raw per-band runs before grouping
    would destroy the [gap, BIG-gap, gap] structural signal that says
    which two runs are one rule's LHS|RHS pair vs. the boundary to the
    next rule. So each band's own largest gap (not assumed to be at a
    fixed index) is found FIRST and used to split that band's 4 runs into
    two (LHS, RHS) pairs, and ONLY THEN is `split_runs_by_pitch` applied
    (to all bands' raw runs at once, one shared pitch) to recover
    multi-token sides.
    """
    w = frame.shape[1]
    all_parent_runs = []
    band_pair_indices = []  # per band: ((lhs_idx, rhs_idx), (lhs_idx, rhs_idx)) into all_parent_runs
    band_row_ranges = []  # per parent run global index -> (row0, row1)
    for band in rule_bands:
        out = occupied_runs(frame, axis="col", bbox=(band["start"], 0, band["end"] - 1, w - 1), background=bg)
        runs, gaps = out["runs"], out["gaps"]
        big_gap_pos = max(range(len(gaps)), key=lambda i: gaps[i])  # index of the largest of the 3 gaps
        split_at = big_gap_pos + 1  # runs[:split_at] = rule A's (LHS,RHS); runs[split_at:] = rule B's
        base = len(all_parent_runs)
        all_parent_runs.extend(runs)
        for r in runs:
            band_row_ranges.append((band["start"], band["end"] - 1))
        pair_a = (base, base + 1)
        pair_b = (base + split_at, base + split_at + 1)
        assert split_at == 2, f"expected the big gap at position 1 (4 runs -> 2+2 split), got split_at={split_at}"
        band_pair_indices.append((pair_a, pair_b))

    pitch = min(r["end"] - r["start"] for r in all_parent_runs)
    children = split_runs_by_pitch(all_parent_runs, pitch, axis="col")
    children_by_parent: dict[int, list] = {}
    for c in children:
        children_by_parent.setdefault(c["parent_index"], []).append(c)
    for idx in children_by_parent:
        children_by_parent[idx].sort(key=lambda c: c["start"])

    def tokens_for(parent_idx):
        row0, row1 = band_row_ranges[parent_idx]
        out_tokens = []
        for child in children_by_parent[parent_idx]:
            mask = rectangular_ink_mask(frame, row0, row1, child["start"], child["end"])
            out_tokens.append(canon_sig_c4(mask))
        return tuple(out_tokens)

    rules = []
    for pair_a, pair_b in band_pair_indices:
        for lhs_idx, rhs_idx in (pair_a, pair_b):
            rules.append((tokens_for(lhs_idx), tokens_for(rhs_idx)))
    return rules


def run_level(label):
    entry = ORACLE[label]
    frame = load_frame(entry)
    bg = discover_background(frame)
    bands = discover_bands(frame, bg)
    rule_bands, bar1_band, bar2_band = classify_bands(frame, bands, bg)
    rules = extract_rules(frame, rule_bands, bg)
    bar1_tokens = extract_bar1_tokens(frame, bar1_band, bg)

    # Build the oracle sprite-name <-> canonical-signature lookup for the
    # FINAL comparison only (never used inside the pipeline above). Every
    # LHS/RHS token position in `rules`, in extraction order, corresponds
    # 1:1 to the oracle's own flattened rule list in the SAME order
    # (measured/asserted, see extract_rules' assertions + the design doc's
    # exact 12/12 cross-validation).
    oracle_rules = entry["rules"]
    name_by_sig: dict[tuple, str] = {}
    collisions = []
    for (lhs_sig, rhs_sig), (lhs_names, rhs_names) in zip(rules, oracle_rules, strict=True):
        for sig, name in list(zip(lhs_sig, lhs_names, strict=True)) + list(zip(rhs_sig, rhs_names, strict=True)):
            if sig in name_by_sig and name_by_sig[sig] != name:
                collisions.append((sig, name_by_sig[sig], name))
            name_by_sig[sig] = name

    bar1_names_predicted = [name_by_sig.get(sig, "<UNKNOWN>") for sig in bar1_tokens]
    unknown = [n for n in bar1_names_predicted if n == "<UNKNOWN>"]

    print(f"\n=== {label} ===")
    print(f"  discovered background: {bg}")
    print(f"  discovered bands: {[(b['start'], b['end']) for b in bands]}")
    print(f"  rule_bands: {[(b['start'], b['end']) for b in rule_bands]}")
    print(f"  bar1_band: {(bar1_band['start'], bar1_band['end'])}  bar2_band: {(bar2_band['start'], bar2_band['end'])}")
    print(f"  extracted rule token-count shape: {[(len(lhs), len(rhs)) for lhs, rhs in rules]}")
    print(f"  oracle rule token-count shape:    {[(len(lhs), len(rhs)) for lhs, rhs in oracle_rules]}")
    print(f"  bar1 tokens recovered -> names: {bar1_names_predicted}")
    print(f"  bar1 oracle names:              {entry['bar1']}")
    print(f"  token collisions (same signature, different oracle name): {collisions}")

    if collisions:
        print(f"  *** KILL: token collision(s) on {label} ***")
        return False
    if unknown:
        print(f"  *** KILL: {len(unknown)} unknown token(s) on {label} (no matching rule-table signature) ***")
        return False
    if bar1_names_predicted != entry["bar1"]:
        print(f"  *** KILL: bar1 token identification mismatch on {label} ***")
        return False

    # greedy_parse(bar1_tokens, rules) -- predict bar2's target.
    greedy_rules = [(list(lhs), list(rhs)) for lhs, rhs in rules]
    parsed = greedy_parse(bar1_tokens, greedy_rules)
    if parsed is None:
        print(f"  *** KILL: greedy_parse FAILED to cover bar1 on {label} ***")
        return False

    predicted_names = [name_by_sig.get(sig, "<UNKNOWN>") for sig in parsed["result"]]
    oracle_target = []
    rule_by_lhs_names = {tuple(lhs): rhs for lhs, rhs in oracle_rules}
    for name in entry["bar1"]:
        oracle_target.extend(rule_by_lhs_names[(name,)])

    print(f"  predicted bar2 target: {predicted_names}")
    print(f"  oracle bar2 target:    {oracle_target}")
    match = predicted_names == oracle_target
    if not match:
        print(f"  *** KILL: target mismatch on {label} ***")
        return False
    print(f"  *** PASS: token-for-token oracle equality on {label} ***")
    return True


def main() -> None:
    results = {label: run_level(label) for label in ("L0", "L1", "L2")}
    print("\n" + "=" * 70)
    print("STEP 2 VERDICT:", results)
    overall = all(results.values())
    print("OVERALL:", "PASS (all 3 levels)" if overall else "KILL (at least one level failed)")


if __name__ == "__main__":
    main()
