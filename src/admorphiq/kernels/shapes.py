"""Pure shape-transform and assignment kernels ("shape_transforms_and_assignment", R56).

Generic geometry the LLM (or a quarantined public-game adapter script)
composes by supplying boolean masks and a score matrix — no game semantics,
no coordinates, no board layout, no environment access. This is the reusable
math behind puzzle classes where a piece must be matched to a target shape
under some symmetry (rotation/reflection) and multiple pieces must be paired
to multiple targets optimally (e.g. the S5I5-class rotation-puzzle family:
see :mod:`admorphiq.rotation` for the game-specific detection/probing layer
this kernel group was extracted from — this module knows nothing about
pieces, frames, references, or widgets, only masks and score matrices).

Masks are represented as a tuple of tuples of ``bool`` (or ``0``/``1``),
row-major, normalized on entry so callers may pass any nested sequence.
Empty masks (zero rows, or all-empty rows) are supported throughout.

Stdlib only — no numpy. These kernels must run inside the sandboxed REPL
where only the standard library and explicitly provided modules exist.
"""

from __future__ import annotations

from collections.abc import Sequence

BoolRow = tuple[bool, ...]
BoolMask = tuple[BoolRow, ...]

_DIHEDRAL_NAMES = (
    "identity",
    "rot90",
    "rot180",
    "rot270",
    "flip_h",
    "flip_h_rot90",
    "flip_h_rot180",
    "flip_h_rot270",
)


def _normalize_mask(mask: Sequence[Sequence[object]]) -> BoolMask:
    """Coerce any nested sequence of truthy/falsy values into a ``BoolMask``.

    Ragged input rows are not expected (every row must share a width); an
    empty outer sequence, or a sequence of empty rows, normalizes to an
    empty mask (``()``).
    """
    rows = tuple(tuple(bool(v) for v in row) for row in mask)
    if not rows or all(len(row) == 0 for row in rows):
        return ()
    return rows


def _dims(mask: BoolMask) -> tuple[int, int]:
    if not mask:
        return (0, 0)
    return (len(mask), len(mask[0]))


def _rotate90(mask: BoolMask) -> BoolMask:
    """Rotate 90 degrees counter-clockwise (matches ``numpy.rot90``'s default)."""
    h, w = _dims(mask)
    if h == 0 or w == 0:
        return mask
    return tuple(
        tuple(mask[r][c] for r in range(h))
        for c in range(w - 1, -1, -1)
    )


def _flip_h(mask: BoolMask) -> BoolMask:
    """Mirror left-right (reverse each row)."""
    return tuple(tuple(reversed(row)) for row in mask)


def dihedral_transforms(mask: Sequence[Sequence[object]]) -> list[dict[str, object]]:
    """Apply the 8 symmetries of the dihedral group D4 to ``mask``.

    Returns a list of ``{"name": ..., "mask": ...}`` in a fixed, deterministic
    order: the 4 rotations of the original (``identity``, ``rot90``,
    ``rot180``, ``rot270``), then the 4 rotations of its horizontal mirror
    (``flip_h``, ``flip_h_rot90``, ``flip_h_rot180``, ``flip_h_rot270``).
    Rotating a non-square mask transposes its dimensions, which is expected —
    the caller compares transformed masks by content (e.g. via :func:`iou`),
    not by fixed shape.
    """
    base = _normalize_mask(mask)
    out: list[dict[str, object]] = []
    current = base
    for i in range(4):
        out.append({"name": _DIHEDRAL_NAMES[i], "mask": current})
        current = _rotate90(current)
    current = _flip_h(base)
    for i in range(4):
        out.append({"name": _DIHEDRAL_NAMES[4 + i], "mask": current})
        current = _rotate90(current)
    return out


def crop_to_content(mask: Sequence[Sequence[object]]) -> dict[str, object]:
    """Tight bounding box of ``mask``'s truthy cells.

    Returns ``{"mask": cropped, "offset": (row, col)}`` where ``offset`` is
    the top-left corner of the bounding box in the original mask's
    coordinates. A mask with no truthy cells (including an empty mask)
    returns an empty mask and offset ``(0, 0)``.
    """
    norm = _normalize_mask(mask)
    truthy = [(r, c) for r, row in enumerate(norm) for c, v in enumerate(row) if v]
    if not truthy:
        return {"mask": (), "offset": (0, 0)}
    rows = [r for r, _c in truthy]
    cols = [c for _r, c in truthy]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    cropped = tuple(tuple(norm[r][c0 : c1 + 1]) for r in range(r0, r1 + 1))
    return {"mask": cropped, "offset": (r0, c0)}


def _pad_to_origin(mask: BoolMask, h: int, w: int) -> BoolMask:
    """Embed ``mask`` top-left into a zero (all-False) canvas of ``h`` x ``w``."""
    mh, mw = _dims(mask)
    return tuple(
        tuple(mask[r][c] if r < mh and c < mw else False for c in range(w))
        for r in range(h)
    )


def iou(mask_a: Sequence[Sequence[object]], mask_b: Sequence[Sequence[object]]) -> float:
    """Intersection-over-union of two masks' truthy cells.

    Alignment rule: both masks are top-left-aligned at the origin and padded
    with False out to the common bounding size (``max`` of each mask's height
    and width independently) — no registration search is performed, so
    callers that want translation-invariant comparison should
    :func:`crop_to_content` both masks first (as :func:`best_transform_match`
    does by default). Two empty masks (or two masks with no truthy cells)
    are defined as a perfect match, ``1.0``.
    """
    a = _normalize_mask(mask_a)
    b = _normalize_mask(mask_b)
    ah, aw = _dims(a)
    bh, bw = _dims(b)
    h, w = max(ah, bh), max(aw, bw)
    if h == 0 or w == 0:
        return 1.0
    pa = _pad_to_origin(a, h, w)
    pb = _pad_to_origin(b, h, w)
    inter = 0
    union = 0
    for r in range(h):
        for c in range(w):
            x, y = pa[r][c], pb[r][c]
            if x or y:
                union += 1
                if x and y:
                    inter += 1
    if union == 0:
        return 1.0
    return inter / union


def best_transform_match(
    source_mask: Sequence[Sequence[object]],
    target_mask: Sequence[Sequence[object]],
    crop: bool = True,
) -> dict[str, object]:
    """The dihedral transform of ``source_mask`` maximizing IoU against ``target_mask``.

    When ``crop`` is True (default), both masks are tight-cropped via
    :func:`crop_to_content` before scoring, so the match is translation-
    invariant. Returns ``{"name": ..., "iou": ..., "mask": ...}`` for the
    best-scoring transform; ties are broken by the fixed
    :func:`dihedral_transforms` order (``identity`` first, then the
    remaining rotations/flips in that order).
    """
    target = _normalize_mask(target_mask)
    if crop:
        target = crop_to_content(target)["mask"]
    best: dict[str, object] | None = None
    for candidate in dihedral_transforms(source_mask):
        cand_mask = candidate["mask"]
        if crop:
            cand_mask = crop_to_content(cand_mask)["mask"]
        score = iou(cand_mask, target)
        if best is None or score > best["iou"]:
            best = {"name": candidate["name"], "iou": score, "mask": cand_mask}
    assert best is not None
    return best


def assign_pairs(score_matrix: Sequence[Sequence[float]]) -> list[tuple[int, int]]:
    """Maximum-total-score bipartite assignment for a rectangular score matrix.

    ``score_matrix[i][j]`` is the value of pairing row ``i`` with column
    ``j``. Returns ``[(row_index, col_index), ...]`` covering every row when
    there are at least as many columns as rows (each row assigned exactly
    once, each column at most once), or every column when there are more
    columns than rows. An empty matrix (no rows, or rows of zero width)
    returns ``[]``.

    Exact search via bitmask DP over the smaller dimension's slots, scanning
    the larger dimension's items in order (Held-Karp-style over subsets),
    which is optimal (unlike a greedy highest-score-first pick) and exact
    for the small sizes this kernel targets (n <= ~15; DP state space is
    ``items * 2**slots``). Deterministic for a given matrix: reconstruction
    always walks items last-to-first and, among slots tied for the same
    optimal value, prefers the lowest slot index.
    """
    rows = [tuple(float(v) for v in row) for row in score_matrix]
    if not rows or len(rows[0]) == 0:
        return []
    n_rows = len(rows)
    n_cols = len(rows[0])
    # DP is over "which slots are used so far, after considering the first i
    # items", so it scales with 2**slots — always DP over the SMALLER
    # dimension's slots, with the LARGER dimension supplying items (some of
    # which go unassigned, since there are more items than slots to fill).
    # If rows are fewer, transpose so slots = rows and transpose back after.
    if n_cols <= n_rows:
        matrix = rows
        transposed = False
        n_items, n_slots = n_rows, n_cols
    else:
        matrix = [tuple(rows[r][c] for r in range(n_rows)) for c in range(n_cols)]
        transposed = True
        n_items, n_slots = n_cols, n_rows

    neg_inf = float("-inf")
    full = 1 << n_slots
    full_mask = full - 1
    # dp[i][mask] = best total score assigning some subset of items [0, i)
    # to exactly fill the slots in `mask` (popcount(mask) items used, the
    # rest of the first i items left unassigned).
    dp: list[list[float]] = [[neg_inf] * full for _ in range(n_items + 1)]
    dp[0][0] = 0.0
    for i in range(n_items):
        for mask in range(full):
            cur = dp[i][mask]
            if cur == neg_inf:
                continue
            if cur > dp[i + 1][mask]:
                dp[i + 1][mask] = cur
            for slot in range(n_slots):
                bit = 1 << slot
                if mask & bit:
                    continue
                nxt = mask | bit
                val = cur + matrix[i][slot]
                if val > dp[i + 1][nxt]:
                    dp[i + 1][nxt] = val
    # n_items >= n_slots always (n_slots is the smaller dimension), so a full
    # assignment (every slot filled) is always reachable.
    pairs: list[tuple[int, int]] = []
    mask = full_mask
    for i in range(n_items, 0, -1):
        target = dp[i][mask]
        for slot in range(n_slots):
            bit = 1 << slot
            if not (mask & bit):
                continue
            prev_mask = mask & ~bit
            if abs(dp[i - 1][prev_mask] + matrix[i - 1][slot] - target) < 1e-9:
                pairs.append((i - 1, slot))
                mask = prev_mask
                break
        # If no slot bit matches, item i-1 was left unassigned on the
        # optimal path (mask unchanged) and the loop moves to item i-2.
    pairs.reverse()
    if transposed:
        pairs = [(slot, item) for item, slot in pairs]
    pairs.sort()
    return pairs
