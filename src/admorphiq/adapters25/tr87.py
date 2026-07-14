"""script25 quarantined adapter: TR87 (rule-derivation / rewrite-grammar family).

*** QUARANTINE — MODEL-NEVER-VISIBLE. See admorphiq.adapters25's package
docstring. ***

``docs/tr87_frame_only_grammar_design_20260715.md``,
``docs/r56_codex_tr87_review_20260715.md``, and
``docs/r56_codex_tr87_reruling_20260715.md`` (read for reference, not
imported) record TR87 as a token-rewrite-grammar game: the board holds
THREE rule-table row-bands (2 rules each, 6 rules total, each rule
``LHS_tokens -> RHS_tokens``), a static "bar1" row (the derivation SOURCE,
5-8 glyph columns depending on the level) and an editable "bar2" row (the
derivation TARGET the player must dial into place). A level clears when
bar2, column by column, equals the token sequence produced by greedily
parsing bar1 left-to-right against the six rules (first matching rule in
list order wins, no backtracking -- ``kernels.rewrite.greedy_parse``'s own
documented contract, chosen over ``derive_rewrites``/``find_derivation``
specifically because the real game's own win-check (verification-only
source read) is this exact deterministic single-pass algorithm, not a
branching search). ``avail=[1,2,3,4]`` -- keyboard-only, no ACTION6: a
bracket cursor (moved by ACTION3/ACTION4) selects which bar2 column is
being edited; ACTION1/ACTION2 step that column's dial through a CLOSED
7-state cycle (measured, `docs/tr87_frame_only_grammar_design_20260715.md`
section 2 -- every column shares the identical set of 7 canonical
rotation-invariant token shapes). The win-check runs automatically after
every dial-step action (verification-only source read,
``environment_files/tr87/*/tr87.py``'s ``step()``/``bsqsshqpox()``) --
there is no separate "confirm" action.

This adapter is the PACKAGED, adapter-owned form of the gold-trace-first
integration test ``scripts/_tr87_integration.py`` (THROWAWAY, not shipped)
which validated the discovery/extraction/greedy_parse pipeline
token-for-token against oracle ground truth on all three captured no-flags
levels (L0/L1/L2) -- see ``.wiki/wiki/rounds/r56_generic-kernels.md``'s
"TR87 gate arc" for the full step 1-3 provenance. Everything below
``load_frame``-level (background/band discovery, rule extraction, bar
tokenization, bracket-column detection, dial/bracket action planning) is
frame-only: no fixed pixel coordinates, no fixed palette constants, no
oracle reads anywhere in the operational path. Oracle sprite names never
appear in this file at all -- unlike the integration test (which needed
them for the final correctness comparison), an adapter has no oracle to
compare against; it only needs canonical SIGNATURE equality between a
bar2 column's current token and its greedy_parse-derived target, which
requires no naming step at all.

**Step 4 scope (this adapter): L0-L2 only ("the simple 3/6 slice"),
per the Codex ruling's own kill criterion** -- ``alter_rules``,
``tree_translation``, and ``double_translation`` (the three flags that
distinguish L4-L6, per the design doc's level/flag table) are NOT
measured or handled here. :func:`classify_bands`' own structural
assertions (exactly 3 rule-table bands with the measured
4-runs/[small,LARGE,small]-gap signature, exactly 2 bar bands, a
detectable bracket band adjacent to bar2) are the adapter's OWN
level-shape gate: if a level's board doesn't match this shape, the
level is UNSUPPORTED and the adapter falls back to a harmless
bracket-nudge policy rather than mis-planning against unmeasured
semantics -- "bank the simple slice instead of contaminating kernels"
(the ruling's own words), never an exploratory-recovery grind.

Composition from ``admorphiq.kernels`` (mirrors the integration test
exactly, ported here as adapter-owned pipeline code):
  - :func:`admorphiq.kernels.occupied_runs` -- row-band discovery, and
    (unchanged from step 2, per the ruling's own "rule-table sides keep
    the current grouping+splitting path, it's proven") the rule-table's
    own column-run grouping.
  - :func:`admorphiq.kernels.color_mode` / :func:`cluster_widths` --
    background discovery (top frequency-tier of the whole-frame
    histogram).
  - :func:`admorphiq.kernels.split_runs_by_pitch` -- BOTH the rule-table's
    multi-token-run splitting (step 1/2, unchanged) AND (step 3, this
    round) bar1/bar2's own LATTICE tokenization: the bar's full measured
    extent becomes ONE parent run (real ink cells, not a second
    ``occupied_runs`` pass), split into ``pitch``-wide slots positionally
    -- fixes a background-gap segmenter mistaking an ink-free column
    WITHIN one glyph for an inter-glyph boundary (measured: L2's bar1 C4
    glyph, and L1's bar2, both fragment under the old approach).
  - :func:`admorphiq.kernels.dihedral_transforms` / :func:`crop_to_content`
    -- C4-only (NOT full D4) rotation-invariant canonical token identity;
    reflections risk collapsing genuinely distinct chiral tokens, per
    Codex's re-ruling.
  - :func:`admorphiq.kernels.rewrite.greedy_parse` -- the actual derivation
    engine, chosen over the BFS-search ``derive_rewrites``/
    ``find_derivation`` specifically because it matches the real game's
    own deterministic single-pass win-check semantics (see module
    docstring above).

Bracket-column detection and the dial executor are adapter-owned policy
(declared HERE, not in the kernel layer, which knows nothing about
brackets, dials, or bar2): the bracket is a short (<4px tall) row-band
immediately adjacent to bar2 (structurally discovered, not a fixed row
number); its own ink column-run, projected onto bar2's already-measured
column lattice, gives the CURRENTLY SELECTED column index. Both the
bracket-move direction (ACTION3 vs ACTION4) and the dial-step direction
are MEASURED live on first use, never assumed from the verification-only
source read (Codex's own instruction, this round) -- one calibration
probe per level, cached for the rest of that level's dial-executor calls.
"""

from __future__ import annotations

from typing import Any

from admorphiq.adapters25.base import (
    GameAction,
    GameAdapter,
    available_action_ids,
    canonical_layer,
    reset_action,
    simple_action,
    state_name,
)
from admorphiq.kernels import (
    cluster_widths,
    color_mode,
    crop_to_content,
    dihedral_transforms,
    greedy_parse,
    occupied_runs,
    split_runs_by_pitch,
)

GAME_ID = "tr87"

Grid = tuple[tuple[int, ...], ...]
Sig = tuple[tuple[bool, ...], ...]

_GIVEUP_DEFAULT = 500

# A multi-layer transient frame stack at level entry mis-reads structure
# (the same class of finding as sb26/ft09's own settle-wait; TR87's own
# design doc measured up to 30 stacked layers at a level transition).
# TR87 has NO idle/no-op action (avail=[1,2,3,4] only, every one has a
# real side effect) -- ACTION3 (a bracket move) is used as the settle
# action instead of a throwaway click, because bracket movement never
# touches win-check state (only WHICH column is selected), so it is
# never wasted even if settling turns out to take a while.
_SETTLE_MAX_WAIT = 6

# The dial is a MEASURED closed 7-state cycle (every column shares the
# identical set of 7 canonical shapes) -- 7 dial-step presses in either
# direction are GUARANTEED to reach any rule-table-derived target, since
# greedy_parse's own RHS output is always one of those 6-of-7 rule-table
# tokens. +1 is a defensive safety margin only, never load-bearing.
_DIAL_MAX_STEPS = 8

# A rule-table band's own column-run count/gap-shape signature (measured,
# `docs/tr87_frame_only_grammar_design_20260715.md`: exactly 4 raw glyph
# runs whose 3 gaps have a [small, LARGE, small] shape -- the LARGE
# middle gap is the boundary BETWEEN two rules; the two small gaps are
# each one rule's own LHS|RHS split).
_RULE_BAND_RUN_COUNT = 4


def _grid_from_latest(latest_frame: Any) -> Grid:
    return canonical_layer(latest_frame)


def discover_background(frame: Grid) -> set[int]:
    """Board background = the top frequency-tier of the whole-frame colour histogram."""
    all_vals = [int(v) for row in frame for v in row]
    hist = color_mode(all_vals, k=len(set(all_vals)))
    counts = [h["count"] for h in hist]
    clusters = cluster_widths(counts, ratio=1.5)
    return {hist[i]["color"] for i in clusters[-1]}


def discover_bands(frame: Grid, bg: set[int]) -> list[dict[str, Any]]:
    """Horizontal structural bands: occupied_runs along rows, background-separated."""
    return occupied_runs(frame, axis="row", background=bg)["runs"]


def classify_bands(
    frame: Grid, bands: list[dict[str, Any]], bg: set[int]
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    """Split bands into (rule_bands[3], bar1_band, bar2_band, bracket_band).

    A rule-table band's column-projection has exactly 4 runs whose middle
    gap is the largest of its 3 gaps (see module docstring). Among the
    remaining TALL (>=4px) bands, the one with the smaller row start is
    bar1 (static), the other bar2 (editable) -- bar1 always renders above
    bar2. The bracket band is the SHORT (<4px) band structurally adjacent
    (within 3px) to bar2's own start or end -- not a fixed row number.

    Returns ``None`` (never raises) when the board doesn't match this
    shape -- the caller's own "unsupported level, fall back" gate, per
    this adapter's documented L0-L2-only scope.
    """
    w = len(frame[0])
    rule_bands, tall_bands, short_bands = [], [], []
    for b in bands:
        height = b["end"] - b["start"]
        if height < 4:
            short_bands.append(b)
            continue
        out = occupied_runs(frame, axis="col", bbox=(b["start"], 0, b["end"] - 1, w - 1), background=bg)
        runs, gaps = out["runs"], out["gaps"]
        if len(runs) == _RULE_BAND_RUN_COUNT and len(gaps) == 3 and gaps[1] > gaps[0] and gaps[1] > gaps[2]:
            rule_bands.append(b)
        else:
            tall_bands.append(b)
    rule_bands.sort(key=lambda b: b["start"])
    tall_bands.sort(key=lambda b: b["start"])
    if len(rule_bands) != 3 or len(tall_bands) != 2:
        return None
    bar1_band, bar2_band = tall_bands[0], tall_bands[1]

    bracket_band = None
    for b in short_bands:
        touches_start = abs(b["end"] - bar2_band["start"]) <= 3
        touches_end = abs(b["start"] - bar2_band["end"]) <= 3
        if touches_start or touches_end:
            bracket_band = b
            break
    if bracket_band is None:
        return None
    return rule_bands, bar1_band, bar2_band, bracket_band


def canon_sig_c4(mask: tuple[tuple[bool, ...], ...]) -> Sig:
    """Rotation-ONLY (C4: identity/rot90/rot180/rot270) canonical signature -- no reflections.

    Full D4 (dihedral_transforms' default 8-way, including 4 mirrored
    variants) risks collapsing chiral tokens that are genuinely different
    into the same signature -- Codex's re-ruling. Slices
    dihedral_transforms' first 4 entries (identity, rot90, rot180, rot270
    -- its own documented fixed order).
    """
    return min(crop_to_content(t["mask"])["mask"] for t in dihedral_transforms(mask)[:4])


def rectangular_ink_mask(frame: Grid, row0: int, row1: int, col0: int, col1: int) -> tuple[tuple[bool, ...], ...]:
    """Boolean mask over [row0,row1] x [col0,col1): True where the pixel is the MINORITY colour."""
    vals = [frame[r][c] for r in range(row0, row1 + 1) for c in range(col0, col1)]
    hist = color_mode(vals, k=len(set(vals)))
    fill = hist[0]["color"]
    return tuple(tuple(frame[r][c] != fill for c in range(col0, col1)) for r in range(row0, row1 + 1))


def extract_rules(
    frame: Grid, rule_bands: list[dict[str, Any]], bg: set[int]
) -> tuple[list[tuple[Sig, ...]], int] | None:
    """Extract the 6 (LHS_tokens, RHS_tokens) rules and the shared glyph pitch.

    Group raw sides FIRST (the [gap, BIG-gap, gap] structural signal says
    which two runs are one rule's LHS|RHS pair), THEN split via
    split_runs_by_pitch (recovers multi-token sides). Returns ``None``
    (never raises) if a band's own big-gap position isn't where every
    measured level puts it (split_at == 2, i.e. 4 runs -> 2+2) -- an
    unsupported board shape, not a bug to crash on.
    """
    w = len(frame[0])
    all_parent_runs: list[dict[str, Any]] = []
    band_pair_indices = []
    band_row_ranges: list[tuple[int, int]] = []
    for band in rule_bands:
        out = occupied_runs(frame, axis="col", bbox=(band["start"], 0, band["end"] - 1, w - 1), background=bg)
        runs, gaps = out["runs"], out["gaps"]
        big_gap_pos = max(range(len(gaps)), key=lambda i: gaps[i])
        split_at = big_gap_pos + 1
        if split_at != 2:
            return None
        base = len(all_parent_runs)
        all_parent_runs.extend(runs)
        band_row_ranges.extend([(band["start"], band["end"] - 1)] * len(runs))
        band_pair_indices.append(((base, base + 1), (base + split_at, base + split_at + 1)))

    if not all_parent_runs:
        return None
    pitch = min(r["end"] - r["start"] for r in all_parent_runs)
    children = split_runs_by_pitch(all_parent_runs, pitch, axis="col")
    children_by_parent: dict[int, list] = {}
    for c in children:
        children_by_parent.setdefault(c["parent_index"], []).append(c)
    for idx in children_by_parent:
        children_by_parent[idx].sort(key=lambda c: c["start"])

    def tokens_for(parent_idx: int) -> Sig:
        row0, row1 = band_row_ranges[parent_idx]
        return tuple(
            canon_sig_c4(rectangular_ink_mask(frame, row0, row1, child["start"], child["end"]))
            for child in children_by_parent[parent_idx]
        )

    rules = []
    for pair_a, pair_b in band_pair_indices:
        for lhs_idx, rhs_idx in (pair_a, pair_b):
            rules.append((tokens_for(lhs_idx), tokens_for(rhs_idx)))
    return rules, pitch


def extract_bar_tokens(frame: Grid, band: dict[str, Any], bg: set[int], pitch: int) -> list[Sig]:
    """A bar's (bar1 OR bar2) own per-glyph tokens, LATTICE-split by ``pitch``.

    NOT occupied_runs-segmented -- a background gap WITHIN one glyph's own
    cell (measured on TR87 bar1's C4 glyph and on bar2 generally) is
    indistinguishable, under occupied_runs alone, from the gap BETWEEN two
    glyphs. The bar's own fill colour and full column extent are
    discovered exactly as before, but the whole extent becomes ONE parent
    run (its true ink-cell set, computed directly, not via a second
    occupied_runs pass) handed to split_runs_by_pitch, which carves it
    into pitch-wide slots POSITIONALLY -- purely from the bar's own
    measured geometry, never from where the background happens to show
    through a glyph's ink.
    """
    row0, row1 = band["start"], band["end"] - 1
    w = len(frame[0])
    non_bg_vals = [frame[r][c] for r in range(row0, row1 + 1) for c in range(w) if frame[r][c] not in bg]
    if not non_bg_vals:
        return []
    fill = color_mode(non_bg_vals, k=1)[0]["color"]
    fill_cols = [c for c in range(w) if any(frame[r][c] == fill for r in range(row0, row1 + 1))]
    if not fill_cols:
        return []
    c0, c1 = min(fill_cols), max(fill_cols)
    ink_cells = frozenset(
        (r, c) for r in range(row0, row1 + 1) for c in range(c0, c1 + 1) if frame[r][c] != fill
    )
    parent_run = {"start": c0, "end": c1 + 1, "cells": ink_cells}
    children = split_runs_by_pitch([parent_run], pitch, axis="col")
    tokens = []
    for child in children:
        mask = tuple(
            tuple((r, c) in child["cells"] for c in range(child["start"], child["end"]))
            for r in range(row0, row1 + 1)
        )
        tokens.append(canon_sig_c4(mask))
    return tokens


def bar_column_bounds(frame: Grid, band: dict[str, Any], bg: set[int], pitch: int) -> list[tuple[int, int]]:
    """The [start, end) column bounds of every lattice slot in ``band`` -- same
    extent/pitch measurement :func:`extract_bar_tokens` uses, exposed so
    the bracket detector can map a pixel column to a slot INDEX."""
    row0, row1 = band["start"], band["end"] - 1
    w = len(frame[0])
    non_bg_vals = [frame[r][c] for r in range(row0, row1 + 1) for c in range(w) if frame[r][c] not in bg]
    if not non_bg_vals:
        return []
    fill = color_mode(non_bg_vals, k=1)[0]["color"]
    fill_cols = [c for c in range(w) if any(frame[r][c] == fill for r in range(row0, row1 + 1))]
    if not fill_cols:
        return []
    c0, c1 = min(fill_cols), max(fill_cols)
    width = c1 + 1 - c0
    if width % pitch != 0:
        return []
    return [(c0 + i * pitch, c0 + (i + 1) * pitch) for i in range(width // pitch)]


def detect_bracket_column(
    frame: Grid, bracket_band: dict[str, Any], bg: set[int], col_bounds: list[tuple[int, int]]
) -> int | None:
    """Which bar2 lattice slot the bracket band's own ink overlaps most.

    The bracket is a short structural mark (not a glyph) -- its own
    non-background column-run(s), projected onto ``col_bounds`` (bar2's
    already-measured lattice), give the CURRENTLY SELECTED column. Ties
    (ink spanning multiple slots) resolve to whichever slot has the most
    overlapping ink columns. Returns ``None`` if the band has no ink at
    all (structurally unexpected -- caller's own fallback gate).
    """
    w = len(frame[0])
    row0, row1 = bracket_band["start"], bracket_band["end"] - 1
    ink_cols = [c for c in range(w) if any(frame[r][c] not in bg for r in range(row0, row1 + 1))]
    if not ink_cols or not col_bounds:
        return None
    overlap_counts = [sum(1 for c in ink_cols if start <= c < end) for start, end in col_bounds]
    best = max(range(len(overlap_counts)), key=lambda i: overlap_counts[i])
    return best if overlap_counts[best] > 0 else None


def plan_bar2_target(frame: Grid) -> tuple[list[Sig], list[Sig], dict[str, Any], dict[str, Any], int] | None:
    """Full discovery pipeline: background -> bands -> rules -> bar1 -> greedy_parse.

    Returns ``(bar2_target_tokens, bar1_tokens, bar2_band, bracket_band,
    pitch)`` on success, ``None`` on ANY structural mismatch (unsupported
    level shape) or a failed/incomplete greedy_parse -- the caller's own
    "bail rather than mis-plan" gate; never raises.
    """
    if not frame or not frame[0]:
        return None
    bg = discover_background(frame)
    bands = discover_bands(frame, bg)
    classified = classify_bands(frame, bands, bg)
    if classified is None:
        return None
    rule_bands, bar1_band, bar2_band, bracket_band = classified
    extracted = extract_rules(frame, rule_bands, bg)
    if extracted is None:
        return None
    rules, pitch = extracted
    bar1_tokens = extract_bar_tokens(frame, bar1_band, bg, pitch)
    if not bar1_tokens:
        return None
    greedy_rules = [(list(lhs), list(rhs)) for lhs, rhs in rules]
    parsed = greedy_parse(bar1_tokens, greedy_rules)
    if parsed is None:
        return None
    return list(parsed["result"]), bar1_tokens, bar2_band, bracket_band, pitch


class Adapter(GameAdapter):
    """Rule-derivation dial executor, composed entirely from admorphiq.kernels."""

    GAME_ID = GAME_ID

    def __init__(self, giveup: int = _GIVEUP_DEFAULT) -> None:
        self.restart_on_game_over = True

        self._giveup = giveup
        self._step = 0
        self._levels_seen = -1
        self._settle_wait = 0

        self._plan_attempted = False
        self._target: list[Sig] | None = None
        self._bar2_band: dict[str, Any] | None = None
        self._bracket_band: dict[str, Any] | None = None
        self._pitch: int | None = None
        self._col_bounds: list[tuple[int, int]] = []

        # Live-calibrated per level: which bracket-move action increases
        # the selected column index by 1 (measured, not assumed from the
        # verification-only source read).
        self._bracket_plus: int | None = None
        self._bracket_calibrating = False
        self._pending_bracket_col: int | None = None

        # Which target column index the dial executor is currently
        # driving the bracket toward / stepping.
        self._work_col = 0
        self._dial_steps_this_col = 0

    # ── harness contract ────────────────────────────────────────────────

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._step >= self._giveup

    def choose_action(self, frames: list[Any], latest_frame: Any) -> GameAction:
        state = state_name(latest_frame)
        if state in ("NOT_PLAYED", "GAME_OVER"):
            self._reset_level_state()
            return reset_action()

        raw_layers = getattr(latest_frame, "frame", None) or []
        if not raw_layers:
            return reset_action()

        levels = int(getattr(latest_frame, "levels_completed", 0) or 0)
        if levels != self._levels_seen:
            self._levels_seen = levels
            self._reset_level_state()

        self._step += 1

        # Settle-wait: a multi-layer transient frame stack at level entry
        # mis-reads structure. ACTION3 (a bracket move) is used instead
        # of a throwaway action -- it never touches win-check state, so
        # it's never wasted even mid-settle.
        if len(raw_layers) > 1 and self._settle_wait < _SETTLE_MAX_WAIT:
            self._settle_wait += 1
            simple_ids, _ = available_action_ids(latest_frame)
            if 3 in simple_ids:
                return simple_action(3)
            return simple_action(simple_ids[0]) if simple_ids else reset_action()

        grid = _grid_from_latest(latest_frame)
        if not grid or not grid[0]:
            return reset_action()

        if not self._plan_attempted:
            self._plan_attempted = True
            planned = plan_bar2_target(grid)
            if planned is not None:
                target, _bar1_tokens, bar2_band, bracket_band, pitch = planned
                self._target = target
                self._bar2_band = bar2_band
                self._bracket_band = bracket_band
                self._pitch = pitch
                bg = discover_background(grid)
                self._col_bounds = bar_column_bounds(grid, bar2_band, bg, pitch)

        simple_ids, _action6_ok = available_action_ids(latest_frame)
        return self._decide(grid, simple_ids)

    # ── level bookkeeping ───────────────────────────────────────────────

    def _reset_level_state(self) -> None:
        self._settle_wait = 0
        self._plan_attempted = False
        self._target = None
        self._bar2_band = None
        self._bracket_band = None
        self._pitch = None
        self._col_bounds = []
        self._bracket_plus = None
        self._bracket_calibrating = False
        self._pending_bracket_col = None
        self._work_col = 0
        self._dial_steps_this_col = 0

    # ── planning: bracket-move / dial-step one action per call ──────────

    def _decide(self, grid: Grid, simple_ids: list[int]) -> GameAction:
        if self._target is None or self._bracket_band is None or not self._col_bounds:
            # Unsupported board shape (flagged level, or a structural
            # mismatch this adapter doesn't handle) -- harmless bracket
            # nudge, never a blind dial-step that could corrupt an
            # unmeasured board's state. Never grinds toward a guess.
            return self._safe_fallback(simple_ids)

        bg = discover_background(grid)

        # Bracket-direction calibration: press ACTION3 once, observe the
        # resulting column index, and record which action increases it --
        # measured live, once per level, not assumed from source.
        if self._bracket_plus is None:
            if not self._bracket_calibrating:
                col = detect_bracket_column(grid, self._bracket_band, bg, self._col_bounds)
                if col is None:
                    return self._safe_fallback(simple_ids)
                self._pending_bracket_col = col
                self._bracket_calibrating = True
                if 3 in simple_ids:
                    return simple_action(3)
                return self._safe_fallback(simple_ids)
            col = detect_bracket_column(grid, self._bracket_band, bg, self._col_bounds)
            before = self._pending_bracket_col
            self._bracket_calibrating = False
            if col is None or before is None or col == before:
                return self._safe_fallback(simple_ids)
            n = len(self._col_bounds)
            moved_forward = (before + 1) % n == col
            self._bracket_plus = 3 if moved_forward else 4
            # Falls through to the normal current-column re-detection
            # below (same grid, so it re-derives the identical `col`) --
            # no special-casing needed, the calibration move is just an
            # ordinary bracket step from _move_bracket_toward's own
            # perspective on the NEXT call.

        if self._work_col >= len(self._target):
            return self._safe_fallback(simple_ids)

        current_col = detect_bracket_column(grid, self._bracket_band, bg, self._col_bounds)
        if current_col is None:
            return self._safe_fallback(simple_ids)

        if current_col != self._work_col:
            return self._move_bracket_toward(current_col, self._work_col, simple_ids)

        # Bracket is on the target column -- read it, compare to target.
        tokens = extract_bar_tokens(grid, self._bar2_band, bg, self._pitch)
        idx = self._work_col
        if idx < len(tokens) and tokens[idx] == self._target[idx]:
            self._work_col += 1
            self._dial_steps_this_col = 0
            return self._decide(grid, simple_ids)

        if self._dial_steps_this_col >= _DIAL_MAX_STEPS:
            # The measured 7-state closed cycle guarantees a match within
            # 7 hops -- exceeding the bound means this column's read is
            # unreliable, not that more spinning will help. Move on
            # rather than grind forever on one column.
            self._work_col += 1
            self._dial_steps_this_col = 0
            return self._decide(grid, simple_ids)

        self._dial_steps_this_col += 1
        if 2 in simple_ids:
            return simple_action(2)
        if 1 in simple_ids:
            return simple_action(1)
        return self._safe_fallback(simple_ids)

    def _move_bracket_toward(self, current_col: int, target_col: int, simple_ids: list[int]) -> GameAction:
        n = len(self._col_bounds)
        forward_dist = (target_col - current_col) % n
        backward_dist = (current_col - target_col) % n
        plus_action = self._bracket_plus
        minus_action = 3 if plus_action == 4 else 4
        action = plus_action if forward_dist <= backward_dist else minus_action
        if action in simple_ids:
            return simple_action(action)
        return self._safe_fallback(simple_ids)

    def _safe_fallback(self, simple_ids: list[int]) -> GameAction:
        """A harmless, budget-costing-but-state-safe action for unsupported
        boards or a detection miss -- a bracket move, never a dial step,
        since dial steps are the only action that can move the puzzle
        further from a not-yet-understood target."""
        if 3 in simple_ids:
            return simple_action(3)
        if simple_ids:
            return simple_action(simple_ids[0])
        return reset_action()
