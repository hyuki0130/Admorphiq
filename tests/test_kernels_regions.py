"""Tests for the pure region-segmentation and relation kernels (R56)."""

from admorphiq.kernels import (
    find_regions,
    group_by_axis,
    multiset_signature,
    multisets_equal,
    region_relations,
    size_clusters,
    tile_bbox,
)

# A frame with two diagonal same-colour cells and two separate sections used
# by the region_relations test — see test_region_relations_* for the layout
# rationale (each section isolates exactly one relation type).
_RELATIONS_FRAME = [
    [1, 1, 1, 1, 1, 9, 3, 4],
    [1, 9, 9, 9, 1, 9, 9, 9],
    [1, 9, 2, 9, 1, 9, 9, 9],
    [1, 9, 9, 9, 1, 9, 9, 9],
    [1, 1, 1, 1, 1, 9, 9, 9],
    [9, 9, 9, 9, 9, 9, 9, 9],
    [9, 9, 9, 9, 9, 9, 9, 5],
    [9, 9, 9, 9, 9, 9, 9, 9],
    [9, 7, 9, 9, 9, 8, 9, 9],
    [9, 9, 9, 9, 9, 9, 9, 9],
]


def test_find_regions_4_vs_8_connectivity_splits_or_merges_diagonal():
    """Purpose: two same-colour cells touching only diagonally must be two
    separate regions under 4-connectivity but one merged region under
    8-connectivity — the defining difference between the two modes.
    Expected feedback: failure means the neighbour-offset table for one of
    the two connectivity modes is wrong, corrupting every downstream
    region count for diagonally-touching same-colour clusters."""
    frame = [[1, 0], [0, 1]]
    regions_4 = find_regions(frame, background=0, connectivity=4)
    assert len(regions_4) == 2
    assert all(r["size"] == 1 for r in regions_4)

    regions_8 = find_regions(frame, background=0, connectivity=8)
    assert len(regions_8) == 1
    assert regions_8[0]["size"] == 2


def test_find_regions_gap_tolerant_join_vs_gap_zero_split():
    """Purpose: two same-colour cells separated by exactly one background
    cell (Chebyshev distance 2) must stay split at gap=0 (even with
    connectivity=8, distance 2 > 1) but merge into one region at gap=1
    (bridging radius gap+1=2).
    Expected feedback: failure means the gap-tolerant bridging radius is
    off-by-one or ignores the documented gap+1 contract, silently changing
    which clusters a gap-tolerant caller (e.g. an active-marker-split
    sprite) reconnects."""
    frame = [[1, 0, 1]]
    regions_gap0 = find_regions(frame, background=0, connectivity=8, gap=0)
    assert len(regions_gap0) == 2

    regions_gap1 = find_regions(frame, background=0, gap=1)
    assert len(regions_gap1) == 1
    assert regions_gap1[0]["size"] == 2


def test_find_regions_background_exclusion():
    """Purpose: a background colour (single int or a set) must never appear
    as a region, while omitting background entirely makes it a normal
    region like any other colour.
    Expected feedback: failure means the background filter is applied
    inconsistently (e.g. only in the outer scan, not on interior cells),
    letting background cells leak into a region's own cell set."""
    frame = [[5, 5, 0], [5, 5, 0]]
    regions_none = find_regions(frame, background=None)
    colors_none = {r["color"] for r in regions_none}
    assert colors_none == {5, 0}

    regions_excl = find_regions(frame, background=0)
    assert len(regions_excl) == 1
    assert regions_excl[0]["color"] == 5
    assert regions_excl[0]["size"] == 4

    regions_excl_set = find_regions(frame, background={0, 5})
    assert regions_excl_set == []


def test_region_relations_contains_adjacent_aligned_on_crafted_frame():
    """Purpose: on one frame containing four independent relation instances
    (a ring strictly containing a centre dot; two cells touching at
    4-connectivity; two regions sharing a column centroid without touching;
    two regions sharing a row centroid without touching), each relation
    type must be detected at the correct (a, b) index pair, and unrelated
    pairs must not spuriously acquire a relation.
    Expected feedback: failure isolates exactly which relation predicate
    (containment, touching, or either axis alignment) is wrong, since each
    section of the frame exercises only one relation in isolation."""
    regions = find_regions(_RELATIONS_FRAME, background=9, connectivity=4)
    # Deterministic sort order (bbox row0, col0, then color) fixes indices.
    colors_in_order = [r["color"] for r in regions]
    assert colors_in_order == [1, 3, 4, 2, 5, 7, 8]
    idx = {r["color"]: i for i, r in enumerate(regions)}

    relations = region_relations(regions)

    assert {"a": idx[1], "b": idx[2], "relation": "contains"} in relations
    assert {"a": idx[3], "b": idx[4], "relation": "adjacent"} in relations
    assert {"a": idx[4], "b": idx[5], "relation": "aligned_col"} in relations
    assert {"a": idx[7], "b": idx[8], "relation": "aligned_row"} in relations

    # The ring (color 3) and the bottom-left dot (color 7) share no bbox
    # overlap, touching, or axis alignment at all -> no relation entry.
    pair = {idx[3], idx[7]}
    assert not any({r["a"], r["b"]} == pair for r in relations)


def test_group_by_axis_row_tolerance_and_within_group_col_sort():
    """Purpose: five regions whose row-centroids form two tolerance-chained
    clusters (gap 0.3-0.6 within a cluster, gap 4.1 between clusters) must
    split into exactly those two groups, each returned sorted by the OTHER
    axis (column) rather than by original index.
    Expected feedback: failure in group count means the tolerance chaining
    is wrong; failure in within-group order means the other-axis sort was
    skipped or applied to the wrong axis."""
    regions = [
        {"centroid": (0.0, 5.0)},
        {"centroid": (0.3, 1.0)},
        {"centroid": (0.9, 3.0)},
        {"centroid": (5.0, 2.0)},
        {"centroid": (5.4, 0.0)},
    ]
    groups = group_by_axis(regions, axis="row", tolerance=1.0)
    assert groups == [[1, 2, 0], [4, 3]]


def test_multiset_signature_translation_invariant_shape_color_sensitive():
    """Purpose: multiset_signature must be identical for a shape and its own
    translated copy, but differ for a same-size different shape, and
    multisets_equal must accept a reordered/translated multiset of regions
    while rejecting one with a shape or colour substitution.
    Expected feedback: failure in the direct signature check means the
    origin-normalization is wrong; failure in multisets_equal means the
    Counter-based comparison isn't actually order/position independent."""
    l_shape = {"color": 1, "cells": frozenset({(0, 0), (0, 1), (1, 0)})}
    l_shape_translated = {"color": 1, "cells": frozenset({(3, 2), (3, 3), (4, 2)})}
    line_shape = {"color": 1, "cells": frozenset({(0, 0), (0, 1), (0, 2)})}
    l_shape_diff_color = {"color": 2, "cells": frozenset({(0, 0), (0, 1), (1, 0)})}

    assert multiset_signature(l_shape) == multiset_signature(l_shape_translated)
    assert multiset_signature(l_shape) != multiset_signature(line_shape)

    assert multisets_equal([l_shape], [l_shape_translated]) is True
    assert multisets_equal([l_shape], [line_shape]) is False
    assert multisets_equal([l_shape], [l_shape_diff_color]) is False

    square = {"color": 3, "cells": frozenset({(0, 0), (0, 1), (1, 0), (1, 1)})}
    square_translated = {"color": 3, "cells": frozenset({(10, 10), (10, 11), (11, 10), (11, 11)})}
    assert multisets_equal(
        [l_shape, square], [square_translated, l_shape_translated]
    ) is True


def test_size_clusters_splits_at_ratio_jump():
    """Purpose: six regions with sizes forming two tight size classes
    (10/11/12 and 48/50/55) separated by a 4.0x jump must split into
    exactly those two clusters (by original index, referenced through the
    size-sorted order), not into more or fewer groups.
    Expected feedback: failure means the consecutive next/prev ratio test
    is comparing the wrong pair or using the wrong threshold direction."""
    regions = [
        {"size": 10},
        {"size": 50},
        {"size": 12},
        {"size": 55},
        {"size": 11},
        {"size": 48},
    ]
    clusters = size_clusters(regions, ratio=1.5)
    assert clusters == [[0, 4, 2], [5, 1, 3]]


def test_tile_bbox_exact_cover_no_overlap():
    """Purpose: tiling a bbox whose dimensions do not divide evenly by the
    requested rows/cols must still produce tiles whose union is EXACTLY the
    original bbox's cells with zero overlap — the "integer-fair partition"
    contract.
    Expected feedback: failure (missing cells, duplicated cells, or a tile
    count != rows*cols) means the fair-partition remainder distribution or
    the cursor advancement between tiles is wrong."""
    bbox = (0, 0, 6, 7)  # 7 rows x 8 cols, not evenly divisible by 3
    tiles = tile_bbox(bbox, 3, 3)
    assert len(tiles) == 9

    all_cells: set[tuple[int, int]] = set()
    total_area = 0
    for r0, c0, r1, c1 in tiles:
        cells = {(r, c) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)}
        assert not (cells & all_cells)
        all_cells |= cells
        total_area += len(cells)

    full = {(r, c) for r in range(0, 7) for c in range(0, 8)}
    assert all_cells == full
    assert total_area == 56
