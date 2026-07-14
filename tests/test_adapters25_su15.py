"""Tests for the SU15 vacuum-merge adapter's R56 perception fixes
(2026-07-15) -- ``_spatial_subgroups``/``_scatter_colors``' stray-
contamination fix, ``_candidates``' dual-gap fragment fusion, and
``_ranked_targets``' first-click ``prefer_lone`` ordering.

Found via gold-replay divergence against ``data/traces/su15.npz``: (a) a
single game tile renders as ~15-17 DISCONNECTED same-colour fragments (a
symmetric bowtie sprite, not one connected blob) -- ``_candidates`` had no
fusion step, so every fragment was a separate spurious candidate; (b) one
UNRELATED same-coloured stray region could inflate an entire colour
group's scatter-density bbox, silently deleting a real tile's every
fragment from candidates; (c) on the very first (zero-evidence) decision,
the adapter defaulted to a same-colour PAIR ranking that couldn't
distinguish two coincidentally-same-coloured STATIC decorations from a
genuine mergeable pair, where gold's own first click instead targeted the
one colour-unique, genuinely movable tile.
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.su15 import (
    Adapter,
    _candidates,
    _ranked_targets,
    _scatter_colors,
    _spatial_subgroups,
)


def _region(color: int, bbox: tuple[int, int, int, int], size: int | None = None) -> dict:
    r0, c0, r1, c1 = bbox
    r, c = (r0 + r1) / 2, (c0 + c1) / 2
    return {"color": color, "bbox": bbox, "centroid": (r, c), "size": size or (r1 - r0 + 1) * (c1 - c0 + 1)}


def _grid(size: int, bg: int, stamps: list[tuple[int, int, int, int, int]]) -> tuple[tuple[int, ...], ...]:
    """A blank ``size``x``size`` grid of ``bg`` with each ``(colour, r0, c0,
    r1, c1)`` stamp painted on top."""
    g = [[bg] * size for _ in range(size)]
    for colour, r0, c0, r1, c1 in stamps:
        for r in range(r0, r1 + 1):
            for c in range(c0, c1 + 1):
                g[r][c] = colour
    return tuple(tuple(row) for row in g)


def test_spatial_subgroups_chains_close_regions_but_never_a_distant_one():
    """Purpose: _spatial_subgroups must group regions transitively (a chain
    of close-together members stays one subgroup even if its own two ends
    are farther apart than the radius) while never pulling in a genuinely
    distant, unrelated region.
    Expected feedback: failure means the scatter-density test downstream
    would either fragment one real decorative pattern into several
    under-threshold pieces (missing real scatter) or let a distant stray
    contaminate a real tile's own density measurement (the exact bug this
    fix closes)."""
    chain = [_region(0, (0, 0, 0, 0)), _region(0, (0, 4, 0, 4)), _region(0, (0, 8, 0, 8))]
    distant = _region(0, (0, 40, 0, 40))
    groups = _spatial_subgroups(chain + [distant], radius=5.0)
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 3]


def test_scatter_colors_ignores_a_distant_stray_region_of_the_same_colour():
    """Purpose: regression pin for the exact bug found via gold-replay
    divergence (su15.npz L2) -- a real, dense tile's own fragments must
    stay classified as non-scattered even when an UNRELATED, far-away
    region of the same colour also exists on the frame.
    Expected feedback: failure means a real tile's fragments would be
    wrongly excluded from candidates whenever a same-coloured stray
    happens to sit elsewhere on the board -- silently deleting it, not
    just mis-ranking it."""
    # 12 fragments packed into a tight 6x6 area (density 12/36 = 0.33, well
    # above the sparse threshold) -- the real bowtie's own shape, not a
    # spread-out diagonal.
    dense = [_region(0, (r, c, r, c)) for r in range(0, 6, 2) for c in range(0, 6, 2)] + [
        _region(0, (1, 1, 1, 1)),
        _region(0, (3, 3, 3, 3)),
        _region(0, (5, 5, 5, 5)),
    ]
    stray = _region(0, (60, 60, 60, 60))
    scattered = _scatter_colors(dense + [stray])
    assert 0 not in scattered


def test_scatter_colors_still_catches_a_genuinely_scattered_pattern():
    """Purpose: the fix must not blunt real scatter detection -- a colour
    rendered as many small clusters sparsely spread over ITS OWN bounding
    box (no distant-stray involvement at all) must still be classified as
    scattered decoration.
    Expected feedback: failure means the diagonal step-line (or any
    similar decorative pattern) would leak into candidates again."""
    line = [_region(3, (r, 50 - r, r, 50 - r)) for r in range(0, 40, 2)]  # 20 sparse diagonal dots
    scattered = _scatter_colors(line)
    assert 3 in scattered


def test_candidates_fuses_a_fragmented_tile_into_one_region():
    """Purpose: regression pin for su15.npz L2's colour-0 tile -- ~17
    disconnected fragments of one physical sprite must become ONE
    candidate with an aggregate centroid, not 17 spurious candidates.
    Expected feedback: failure means every same-colour-pair/goal-distance
    computation downstream operates on the wrong granularity (one
    arbitrary fragment instead of the tile's true position)."""
    bowtie = [
        (0, 10, 40, 10, 44),
        (0, 12, 38, 12, 39),
        (0, 12, 45, 12, 46),
        (0, 15, 36, 15, 37),
        (0, 15, 47, 15, 48),
        (0, 18, 40, 18, 44),
    ]
    goal = (9, 0, 0, 5, 5)  # large, distinct colour -- the goal container
    grid = _grid(50, 5, bowtie + [goal])
    cands = _candidates(grid)
    zero_colour = [c for c in cands if c["color"] == 0]
    assert len(zero_colour) == 1


def test_candidates_does_not_merge_two_genuinely_distinct_tiles():
    """Purpose: regression pin for su15.npz L9's colour-9 tiles -- four
    real, separate, similarly-sized tiles spread tens of pixels apart must
    stay four distinct candidates, not collapse into one via the fusion
    gap (falsifies an over-broad clustering radius).
    Expected feedback: failure means the fusion fix introduces the exact
    regression the team explicitly flagged as a risk -- merging distinct
    tiles the same colour happens to share."""
    tiles = [
        (9, 0, 0, 3, 3),
        (9, 0, 20, 3, 23),
        (9, 20, 0, 23, 3),
        (9, 20, 20, 23, 23),
    ]
    goal = (15, 40, 40, 45, 45)
    grid = _grid(50, 5, tiles + [goal])
    cands = _candidates(grid)
    nine_colour = [c for c in cands if c["color"] == 9]
    assert len(nine_colour) == 4


def test_ranked_targets_prefer_lone_puts_colour_unique_tile_before_a_pair():
    """Purpose: regression pin for the exact divergence measured against
    su15.npz L1 -- with prefer_lone=True, a colour-unique tile must rank
    ahead of a same-colour pair, even though the pair would normally rank
    first (nearest-pair-first).
    Expected feedback: failure means the adapter's first click reverts to
    guessing a same-colour pair with zero movement evidence, reproducing
    the original bug (targeting two static decorations by coincidence of
    colour)."""
    lone = _region(0, (50, 8, 54, 12))  # colour-unique, genuinely movable tile
    pair_a = _region(15, (4, 30, 6, 32))
    pair_b = _region(15, (58, 3, 60, 5))
    goal = _region(9, (11, 44, 19, 52), size=59)

    default_order = _ranked_targets([lone, pair_a, pair_b], goal)
    assert default_order[0][0] is pair_a  # unchanged: pairs still rank first by default

    lone_first_order = _ranked_targets([lone, pair_a, pair_b], goal, prefer_lone=True)
    assert lone_first_order[0][0] is lone


def test_ranked_targets_prefer_lone_does_not_reorder_tiles_that_have_a_partner():
    """Purpose: prefer_lone must ONLY promote genuinely colour-unique
    tiles -- a tile that already has a same-colour partner (and so also
    appears in the pair list) must stay in its normal after-pairs
    position among the "lone" fallback entries, not jump the queue too.
    Expected feedback: failure means prefer_lone over-applies, changing
    behaviour for tiles that were never part of the measured bug."""
    pair_a = _region(15, (4, 30, 6, 32))
    pair_b = _region(15, (58, 3, 60, 5))
    goal = _region(9, (11, 44, 19, 52), size=59)

    order = _ranked_targets([pair_a, pair_b], goal, prefer_lone=True)
    # No colour-unique tile exists (both are colour 15, a pair) -- order
    # must be identical to the non-prefer_lone case: the pair first.
    default_order = _ranked_targets([pair_a, pair_b], goal, prefer_lone=False)
    assert [entry[0] for entry in order] == [entry[0] for entry in default_order]


def test_adapter_prefers_the_isolated_tile_on_the_very_first_click():
    """Purpose: end-to-end regression pin, replaying su15.npz L1's exact
    frame-0 candidate geometry against the real Adapter -- the FIRST
    click's source must be the colour-unique tile (matching gold's own
    first move), not the coincidentally-same-coloured static pair.
    Expected feedback: failure means the adapter's live first decision
    still diverges from gold on level 1, the exact symptom this whole fix
    was built to close."""
    grid = _grid(
        64,
        5,
        [
            (15, 4, 30, 6, 32),
            (9, 11, 44, 19, 52),
            (0, 52, 9, 54, 11),
            (15, 58, 3, 60, 5),
        ],
    )
    adapter = Adapter()
    adapter._next_target(grid)
    assert adapter._pending_source_centroid == (53.0, 10.0)


def test_clicks_this_level_resets_on_level_up():
    """Purpose: prefer_lone must re-activate on EVERY new level (each
    level is a fresh board with zero movement evidence again), not only
    on the very first level of a run.
    Expected feedback: failure means level 2+ would carry over click
    history from level 1 and never re-probe an isolated tile first,
    silently disabling the fix after level 1."""
    adapter = Adapter()
    adapter._clicks_this_level = 5
    adapter._levels_seen = 0
    grid = tuple(tuple(0 for _ in range(10)) for _ in range(10))
    frame = SimpleNamespace(
        frame=[[list(row) for row in grid]],
        state=SimpleNamespace(name="NOT_FINISHED"),
        levels_completed=1,
        available_actions=[6],
    )
    adapter.choose_action([], frame)
    assert adapter._clicks_this_level == 0
