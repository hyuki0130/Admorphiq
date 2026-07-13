"""Frame-only ROTATION-PUZZLE capability (R28 world-model-agent family).

A fourth member of the select-and-place family (after
:mod:`admorphiq.arrangement`'s descend-and-sweep, :mod:`admorphiq.sort_match`'s
match-to-order placement, and :mod:`admorphiq.merge_drag`'s click-drag gather).
This one handles the **attempt-limited rotation puzzle** sub-class: the game is
click-only (no movement actions), the board holds one or more compact
multi-colour PIECES — a border/frame colour enclosing an asymmetric interior
pattern of a second colour — plus a separate REFERENCE pattern elsewhere (an
isolated cluster of a third colour showing the target orientation). A widget
click rotates a piece's interior in place; every other click only burns an
on-board attempt/move counter (see ``.wiki/wiki/rounds/r53_unified-harness.md``,
"Wall anatomy #1/#2-8" and "s5i5 rotation-solver DESIGN") so blind exploration
self-destructs by design and the level requires a plan-first, click-exactly
approach.

S5I5 is the measured exemplar (two stacked 5x5 pieces with colour-4 frames /
colour-11 interiors, a colour-14 reference pattern top-centre) but nothing here
reads a game id / title / sprite tag — detection is purely structural:

1. :func:`detect_rotatable_pieces` — a PIECE is a compact frame-colour
   component enclosing a partially-filled interior of a second colour.
2. :func:`detect_reference_patterns` — a REFERENCE is a compact component of a
   colour not used by any piece, located elsewhere on the board.
3. :func:`plan_piece_targets` — for each piece, try all four ``np.rot90``
   orientations of its (tight-cropped) interior pattern against every
   candidate reference and greedily assign the best-scoring piece/reference
   pairs, returning the TARGET interior shape each piece should reach.
4. :func:`widget_candidates` — the click positions worth probing: each piece's
   own centroid and each reference's own centroid (widgets are not visually
   distinguished from background — the measured S5I5 widgets sit near a piece
   and near a reference respectively — so this is the generic geometric
   heuristic; it does not exhaustively grid-probe the board, trading recall for
   a bounded attempt cost). :func:`identify_moved_piece` then tells the live
   agent, from one probe's before/after frames, which piece (if any) that
   candidate controls.
5. :func:`piece_matches_target` — checks the LIVE frame's current interior
   pattern against a piece's target (shape-similarity, not exact pixel
   position), so the agent can re-click a piece's widget until it reaches the
   target and stop the instant it does — the same "let the env confirm"
   philosophy as the rest of the family, avoiding a fragile explicit rotation-
   count computation whose direction/step-size is unknown ahead of time.

Decorative "presentation" frames can be structurally indistinguishable from
real piece frames — measured directly against the live S5I5 environment, not
just the synthetic exemplar. The real S5I5 board draws a colour-4 ring
directly around each small reference glyph too — the SAME ring shape and size
class as the real piece frames, and the enclosed glyph colour (14)
independently has exactly one unrelated freestanding instance elsewhere
(mirroring the real pieces' own interior colour, 11, which likewise has one
unrelated freestanding "slider" component elsewhere). Every STATIC,
frame-local signal tried (ring-shape strictness, minimum interior fill,
frame-of-frame nesting exclusion, spatial containment of a reference inside a
candidate piece) is provably unable to separate the two classes on this
board, because the ambiguous pair is statistically identical to the genuine
pair under all of them — :func:`detect_rotatable_pieces` /
:func:`detect_reference_patterns` keep the falsifiers that ARE unambiguous
wins (each fixes a real false positive without any false negative on the
synthetic tests below) but do not attempt to resolve the decorative-vs-real
question by themselves.

Instead, :func:`detect_rotation_puzzle` resolves it INTERACTIVELY: when its
strict (unambiguous) attempt finds no assignable target, it falls back to
returning the full candidate set (real pieces AND decorative frames alike —
see its docstring), and the live agent's existing Stage-1 widget-probe loop
(``world_model_agent._rotate_step``, :func:`identify_moved_piece`) clicks
each candidate once and observes which ring interiors actually change. A
decorative frame's interior never responds to any click and so never earns a
discovered widget; the commit stage (Stage 2) already only acts on pieces
with a discovered widget, so decorative candidates are pruned for free by
that existing requirement — no separate static pruning step was added. This
is the same "let the env confirm" philosophy as :func:`piece_matches_target`.

Open limitation still recorded (unaddressed by the above): **the
widget-candidate heuristic** in (4) is a bounded geometric guess, not a
learned mapping — a game whose widgets sit further from both the piece and
the reference will not be found, so even with correct piece/reference
identification the live probe queue may never land on the TRUE widget
position (measured on S5I5: the real widgets sit on/near a piece's own
border, not exactly at its centroid). Widening the search (e.g. a coarse
click lattice) was deliberately NOT added because the attempt-limited counter
punishes exactly that kind of blind sweep; the correct generalisation is a
dedicated widget-discovery phase, left for a future round.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .arrangement import _HUD_ROW_CUTOFF
from .general_agent import connected_components

# ── Tunables ─────────────────────────────────────────────────────────────────

# A frame-colour component must span at least this many cells to be a plausible
# piece border (filters single-pixel speckle / anti-aliasing).
_MIN_FRAME_SIZE = 4
# A candidate interior pattern must fill at least this many cells. Measured on
# the real S5I5 board: a stray 1-2px dot that merely happens to fall inside an
# unrelated component's bbox (e.g. a single hint pixel inside the reference
# glyph's own near-ring-shaped silhouette) produces a degenerate "interior"
# that is noise, not a designed rotatable pattern (the real interiors are
# 7-cell shapes). This floor is generic (not tuned to 7) — it only rules out
# incidental few-pixel bbox overlap.
_MIN_INTERIOR_FILL = 3
# A piece's bounding box must be within [MIN, MAX] cells on each side to count
# as "compact" (the measured S5I5 pieces are 5x5). The floor excludes a 1-2 cell
# fragment; the ceiling excludes a board-spanning panel.
_MIN_PIECE_EXTENT = 3
_MAX_PIECE_EXTENT = 16
# A reference-pattern component must span at least this many cells (filters
# stray single-pixel dots that are not a real target shape).
_MIN_REFERENCE_SIZE = 4
# A (piece, reference) pair is only assignable when their best-rotation IoU
# reaches this floor. Measured as NECESSARY on the real S5I5 board:
# best_rotation/plan_piece_targets otherwise happily "assigns" a piece to
# whatever reference scores highest even when that score is low (e.g. an
# unrelated corner dot at ~0.19 IoU) — which made the STRICT detection attempt
# in detect_rotation_puzzle spuriously "succeed" on a garbage match and never
# fall through to the ambiguous probe-to-disambiguate path. 0.5 requires at
# least half the (padded) shape to genuinely overlap; every intentional match
# in the synthetic tests below scores 1.0, and the real decorative/real piece
# family matches on S5I5 score 1.0 too, so this only rejects noise.
_MIN_ASSIGNMENT_SCORE = 0.5
# Two shapes (after padding to a common canvas) count as a MATCH when their
# intersection-over-union reaches this fraction. Used only by
# :func:`piece_matches_target`'s live re-check.
_MATCH_THRESHOLD = 0.9
# Max additional widget clicks the commit stage spends per piece once its
# widget is known. One click may already have been spent identifying the
# widget during probing, so this bounds the piece to at most one full rotation
# cycle (4 distinct orientations) regardless of the (unknown) per-click step
# size or direction.
MAX_COMMIT_CLICKS_PER_PIECE = 3


# ── entity structures ───────────────────────────────────────────────────────


@dataclass
class RotatablePiece:
    """A detected rotatable piece: a frame-colour border around an interior.

    ``bbox`` is ``(r0, r1, c0, c1)`` inclusive, taken from the frame
    component's own extent. ``interior_mask`` is a boolean array shaped like
    the bbox, True where the (single, dominant) interior colour appears —
    including the empty frame-colour border cells, so rotating it with
    ``np.rot90`` rotates the whole piece in place.
    """

    frame_color: int
    interior_color: int
    bbox: tuple[int, int, int, int]
    interior_mask: np.ndarray
    cx: float
    cy: float


@dataclass
class ReferencePattern:
    """A detected reference shape: a tight-cropped mask of a distinct colour."""

    color: int
    mask: np.ndarray
    cx: float
    cy: float
    size: int


@dataclass
class RotationPuzzle:
    """A detected rotation puzzle ready for live probing + commit.

    ``targets[i]`` is the tight-cropped, rotated interior shape piece ``i``
    should reach (or ``None`` when no reference could be assigned to it).
    ``candidates`` is the ordered, de-duplicated list of ``(x, y)`` click
    positions worth probing for a widget (see :func:`widget_candidates`).
    """

    pieces: list[RotatablePiece]
    targets: list[np.ndarray | None]
    candidates: list[tuple[int, int]]


# ── shape helpers ───────────────────────────────────────────────────────────


def _tight_crop(mask: np.ndarray) -> np.ndarray:
    """Crop ``mask`` to the bounding box of its True cells (unchanged if empty)."""
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return mask
    r0, r1 = int(np.argmax(rows)), len(rows) - 1 - int(np.argmax(rows[::-1]))
    c0, c1 = int(np.argmax(cols)), len(cols) - 1 - int(np.argmax(cols[::-1]))
    return mask[r0 : r1 + 1, c0 : c1 + 1]


def _pad_to(mask: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    """Embed ``mask`` top-left into a zero canvas of ``shape``."""
    out = np.zeros(shape, dtype=bool)
    h, w = mask.shape
    out[:h, :w] = mask
    return out


def _shape_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Intersection-over-union of two boolean masks, padded to a shared canvas.

    Top-left-aligned padding rather than centring: both masks are already
    tight-cropped, so top-left alignment is the simplest canonical placement
    that is consistent between the two calls that matter — piece-vs-reference
    scoring in :func:`plan_piece_targets` and the live re-check in
    :func:`piece_matches_target` — without needing a registration search.
    """
    h = max(a.shape[0], b.shape[0])
    w = max(a.shape[1], b.shape[1])
    if h == 0 or w == 0:
        return 0.0
    pa, pb = _pad_to(a, (h, w)), _pad_to(b, (h, w))
    union = int(np.count_nonzero(pa | pb))
    if union == 0:
        return 0.0
    inter = int(np.count_nonzero(pa & pb))
    return inter / union


def _is_ring_component(c: dict) -> bool:
    """Do ``c``'s cells trace the COMPLETE border of ``c``'s own bounding box?

    A genuine piece frame is drawn as a closed rectangular outline: every cell
    on all four edges of its bbox belongs to the component (the interior may
    be partially or fully hollow — that is expected, it is where the enclosed
    colour lives). A component that only coincidentally overlaps a
    neighbour's bbox (a stray pixel, a small interior shape's own extent) will
    not satisfy this, which is what distinguishes a real frame candidate from
    incidental bbox overlap. Degenerate 1-cell-wide/tall boxes are rejected
    (a "ring" needs two distinct rows and columns). Pure / env-free.
    """
    cells = c["cells"]
    rows = [r for r, _c in cells]
    cols = [cc for _r, cc in cells]
    r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
    if r0 == r1 or c0 == c1:
        return False
    for col in range(c0, c1 + 1):
        if (r0, col) not in cells or (r1, col) not in cells:
            return False
    for row in range(r0, r1 + 1):
        if (row, c0) not in cells or (row, c1) not in cells:
            return False
    return True


# ── detection ────────────────────────────────────────────────────────────────


def detect_rotatable_pieces(layer: np.ndarray, background: int) -> list[RotatablePiece]:
    """Compact frame-colour components enclosing an asymmetric interior.

    A candidate frame component's bounding box is scanned for a single
    dominant non-frame, non-background colour; the piece is kept only when
    that colour's mask is NOT invariant under a 90-degree rotation (a solid
    block or a 4-fold-symmetric cross would look identical after any click,
    so no rotation could ever be observed or planned against). Two pieces may
    share the same frame colour (the measured S5I5 layout: both frames are
    colour 4) — ``connected_components`` already separates them into distinct
    components as long as they are not 4-connected to each other, so no
    per-colour de-duplication is applied here.

    Two structural falsifiers, both measured as necessary on the real S5I5
    board (a naive "any component enclosing another colour" test produced 12
    false pieces there — decorative rings drawn around the REFERENCE glyphs
    too, and an outer panel ring enclosing both real pieces together):

    1. **The frame must be a genuine closed ring** of its own bounding box
       (:func:`_is_ring_component`) — a component that merely happens to
       overlap another colour's bbox (e.g. a small interior shape's own
       stray pixels) is not a frame.
    2. **The interior fill excludes any CELL that belongs to another ring
       component** nested inside this bbox — this rejects an outer decorative
       ring whose "interior" is really another (inner) frame's own ring cells
       (frame-of-frame nesting), leaving only genuinely enclosed, non-frame
       content as candidate interior colour. The exclusion is per specific
       nested COMPONENT, not a colour-wide blacklist — a colour that forms a
       ring elsewhere on the board (an unrelated decoration) must not disqualify
       that same colour from being a genuine interior fill here.

    Pure / env-free.
    """
    comps = connected_components(layer, background)
    ring_cells: set[tuple[int, int]] = set()
    for c in comps:
        if _is_ring_component(c):
            ring_cells |= c["cells"]
    pieces: list[RotatablePiece] = []
    for frame_c in comps:
        if frame_c["size"] < _MIN_FRAME_SIZE or frame_c["cy"] >= _HUD_ROW_CUTOFF:
            continue
        if not _is_ring_component(frame_c):
            continue
        rows = [r for r, _c in frame_c["cells"]]
        cols = [c for _r, c in frame_c["cells"]]
        r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
        h, w = r1 - r0 + 1, c1 - c0 + 1
        if not (_MIN_PIECE_EXTENT <= h <= _MAX_PIECE_EXTENT):
            continue
        if not (_MIN_PIECE_EXTENT <= w <= _MAX_PIECE_EXTENT):
            continue
        sub = layer[r0 : r1 + 1, c0 : c1 + 1]
        frame_color = frame_c["color"]
        # Ring cells from OTHER nested ring components (not this frame's own
        # cells) never count as interior content — see falsifier 2 above.
        other_ring_cells = ring_cells - frame_c["cells"]
        other_vals = [
            int(layer[r, c])
            for r in range(r0, r1 + 1)
            for c in range(c0, c1 + 1)
            if layer[r, c] != background
            and layer[r, c] != frame_color
            and (r, c) not in other_ring_cells
        ]
        other = np.array(other_vals, dtype=layer.dtype)
        if other.size == 0:
            continue
        vals, counts = np.unique(other, return_counts=True)
        interior_color = int(vals[int(counts.argmax())])
        interior_mask = sub == interior_color
        if int(interior_mask.sum()) < _MIN_INTERIOR_FILL:
            continue
        if np.array_equal(interior_mask, np.rot90(interior_mask, 1)):
            # Rotationally symmetric interior (e.g. a solid block or a
            # 4-fold-symmetric cross): every orientation looks identical, so a
            # rotation click here would produce no observable change and
            # cannot be probed, matched, or planned against.
            continue
        pieces.append(
            RotatablePiece(
                frame_color=int(frame_color),
                interior_color=interior_color,
                bbox=(r0, r1, c0, c1),
                interior_mask=interior_mask,
                cx=frame_c["cx"],
                cy=frame_c["cy"],
            )
        )
    return pieces


def detect_reference_patterns(
    layer: np.ndarray, background: int, exclude_colors: set[int]
) -> list[ReferencePattern]:
    """Compact components of a colour not used by any piece, elsewhere on the board.

    ``exclude_colors`` is the caller-composed set of colours already claimed by
    detected pieces (frame + interior) plus the background, so the reference
    search never re-labels a piece's own cells as a target shape. Pure /
    env-free.
    """
    out: list[ReferencePattern] = []
    for c in connected_components(layer, background):
        if c["color"] in exclude_colors or c["cy"] >= _HUD_ROW_CUTOFF:
            continue
        if c["size"] < _MIN_REFERENCE_SIZE:
            continue
        rows = [r for r, _c in c["cells"]]
        cols = [cc for _r, cc in c["cells"]]
        r0, r1, c0, c1 = min(rows), max(rows), min(cols), max(cols)
        mask = np.zeros((r1 - r0 + 1, c1 - c0 + 1), dtype=bool)
        for r, cc in c["cells"]:
            mask[r - r0, cc - c0] = True
        out.append(
            ReferencePattern(color=c["color"], mask=mask, cx=c["cx"], cy=c["cy"], size=c["size"])
        )
    return out


def best_rotation(piece: RotatablePiece, reference: ReferencePattern) -> tuple[int, float]:
    """Best of the 4 ``np.rot90`` orientations of ``piece`` against ``reference``.

    Returns ``(k, score)`` where ``k`` is the rotation count (0-3, counter-
    clockwise per ``np.rot90``'s convention) whose tight-cropped shape best
    overlaps ``reference.mask``, and ``score`` is that overlap's IoU. Pure /
    env-free.
    """
    base = _tight_crop(piece.interior_mask)
    best_k, best_score = 0, -1.0
    for k in range(4):
        rotated = np.rot90(base, k)
        score = _shape_similarity(rotated, reference.mask)
        if score > best_score:
            best_k, best_score = k, score
    return best_k, best_score


def plan_piece_targets(
    pieces: list[RotatablePiece], references: list[ReferencePattern]
) -> list[np.ndarray | None]:
    """Per-piece target interior shape, greedily assigned by best IoU score.

    Every (piece, reference) pair is scored via :func:`best_rotation`, EXCEPT
    a pair whose reference centroid falls inside the piece's OWN bbox — that
    reference is the piece's own enclosed content (its own interior, or
    something else physically nested in the same frame), not an external
    target, so matching a piece against itself is excluded. This matters once
    :func:`detect_rotation_puzzle`'s ambiguous fallback stops excluding
    interior colours from reference candidacy: without this check, a piece's
    own interior would otherwise register as its own trivially-matching
    "reference" (always scoring 1.0 at k=0), which would make the ambiguous
    path find a spurious target for every piece regardless of whether a real
    external reference exists.

    Scored pairs below :data:`_MIN_ASSIGNMENT_SCORE` are dropped entirely — a
    piece is better left unassigned than greedily bound to a reference it
    barely resembles (see that constant's comment for why this matters:
    without it, a garbage low-score match can make a piece falsely register
    as "assignable"). Surviving pairs are then claimed highest-score-first,
    each piece and each reference used at most once (so two pieces do not
    both chase the same reference shape). A piece left without an assignable
    reference (more pieces than references, every reference excluded as
    self-nested or below the score floor, or no references at all) gets
    ``None`` and is skipped downstream. Pure / env-free.
    """
    targets: list[np.ndarray | None] = [None] * len(pieces)
    if not pieces or not references:
        return targets
    scored: list[tuple[float, int, int, int]] = []
    for pi, piece in enumerate(pieces):
        r0, r1, c0, c1 = piece.bbox
        for ri, ref in enumerate(references):
            if r0 <= ref.cy <= r1 and c0 <= ref.cx <= c1:
                continue
            k, score = best_rotation(piece, ref)
            if score < _MIN_ASSIGNMENT_SCORE:
                continue
            scored.append((score, pi, ri, k))
    scored.sort(key=lambda t: -t[0])
    assigned_piece: set[int] = set()
    assigned_ref: set[int] = set()
    for score, pi, ri, k in scored:
        if pi in assigned_piece or ri in assigned_ref:
            continue
        assigned_piece.add(pi)
        assigned_ref.add(ri)
        targets[pi] = np.rot90(_tight_crop(pieces[pi].interior_mask), k)
    return targets


def widget_candidates(
    pieces: list[RotatablePiece], references: list[ReferencePattern]
) -> list[tuple[int, int]]:
    """Ordered, de-duplicated click positions worth probing for a rotation widget.

    Widgets are not visually distinguished from background in the measured
    game (a click that rotates a piece looks like any other click until it is
    tried), so this is a bounded geometric heuristic rather than an exhaustive
    search: each piece's own centroid, then each reference's own centroid (the
    measured S5I5 widgets sit near a piece and near a reference respectively).
    See the module docstring's "Open limitation" for what this does not cover.
    Pure / env-free.
    """
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for p in pieces:
        pt = (int(round(p.cx)), int(round(p.cy)))
        if pt not in seen:
            seen.add(pt)
            out.append(pt)
    for r in references:
        pt = (int(round(r.cx)), int(round(r.cy)))
        if pt not in seen:
            seen.add(pt)
            out.append(pt)
    return out


def _try_puzzle(
    pieces: list[RotatablePiece], layer: np.ndarray, background: int, exclude: set[int]
) -> RotationPuzzle | None:
    """Build a :class:`RotationPuzzle` from ``pieces`` for one reference-exclude policy.

    Shared by :func:`detect_rotation_puzzle`'s strict (unambiguous) and loose
    (ambiguous-fallback) attempts — only the ``exclude`` set differs between
    them. Returns ``None`` when no reference or no assignable target results,
    exactly as before this function existed. Pure / env-free.
    """
    references = detect_reference_patterns(layer, background, exclude)
    if not references:
        return None
    targets = plan_piece_targets(pieces, references)
    if not any(t is not None for t in targets):
        return None
    return RotationPuzzle(
        pieces=pieces, targets=targets, candidates=widget_candidates(pieces, references)
    )


def detect_rotation_puzzle(layer: np.ndarray, background: int) -> RotationPuzzle | None:
    """Detect a rotation puzzle on ``layer``, or ``None`` when the structure is absent.

    Two attempts, strict then ambiguous-fallback, both composing
    :func:`detect_rotatable_pieces` + :func:`detect_reference_patterns` +
    :func:`plan_piece_targets` + :func:`widget_candidates` via
    :func:`_try_puzzle`:

    1. **Strict** — references are excluded by every colour already claimed as
       a piece's frame OR interior (a reference is, by definition, a THIRD
       colour distinct from any piece). This is byte-identical to the
       module's original behaviour and is tried first because it is cheaper
       (fewer candidates to probe) whenever the board is unambiguous.
    2. **Ambiguous fallback** — triggered only when (1) finds no assignable
       target, e.g. because every reference colour got consumed as some
       piece's interior. References are excluded by FRAME colour only, so a
       genuine reference colour that some OTHER (possibly decorative) piece
       also happens to enclose as its interior is still found. This can admit
       piece candidates that are actually decorative "presentation" frames —
       see the module docstring's "Open limitations": on the real S5I5 board,
       :func:`detect_rotatable_pieces` alone cannot tell a real piece frame
       from a ring drawn around a reference glyph, since both are structurally
       identical. Rather than guess, this function returns the FULL candidate
       set (real and decorative pieces alike) and leaves disambiguation to the
       live agent: its existing Stage-1 widget-probe loop
       (:func:`identify_moved_piece`) clicks each candidate once and only
       decorative pieces that never show a genuine interior change are
       skipped at commit time, because the commit queue already requires a
       DISCOVERED widget (see ``world_model_agent._rotate_step``) — no static
       piece/reference pruning is attempted here.

    Returns ``None`` when there are no pieces or neither attempt finds an
    assignable target — so the caller only engages the rotation phase when
    there is at least one piece/reference pairing worth probing. Pure /
    env-free.
    """
    pieces = detect_rotatable_pieces(layer, background)
    if not pieces:
        return None
    strict_exclude = {background} | {p.frame_color for p in pieces} | {
        p.interior_color for p in pieces
    }
    puzzle = _try_puzzle(pieces, layer, background, strict_exclude)
    if puzzle is not None:
        return puzzle
    loose_exclude = {background} | {p.frame_color for p in pieces}
    return _try_puzzle(pieces, layer, background, loose_exclude)


# ── live probing / commit helpers ───────────────────────────────────────────


def identify_moved_piece(
    pieces: list[RotatablePiece], before: np.ndarray, after: np.ndarray
) -> int | None:
    """Index of the piece whose interior changed between ``before``/``after``.

    Used by the live agent to fold one widget-candidate probe's result into a
    widget->piece mapping: a candidate click that changes no piece's interior
    is not a widget for this puzzle (it only burned the attempt counter) and
    is dropped. Pure / env-free.
    """
    if before.shape != after.shape:
        return None
    for i, p in enumerate(pieces):
        r0, r1, c0, c1 = p.bbox
        b = before[r0 : r1 + 1, c0 : c1 + 1] == p.interior_color
        a = after[r0 : r1 + 1, c0 : c1 + 1] == p.interior_color
        if not np.array_equal(b, a):
            return i
    return None


def piece_matches_target(
    piece: RotatablePiece, layer: np.ndarray, target: np.ndarray
) -> bool:
    """Does ``piece``'s CURRENT interior (read live from ``layer``) match ``target``?

    Re-extracts the interior mask from ``layer`` at ``piece.bbox`` (robust to
    the piece having actually moved/rotated since detection) and compares its
    tight-cropped shape to ``target`` via :func:`_shape_similarity`, so the
    live commit loop can re-click a widget until the piece reaches its target
    without needing to know the per-click rotation direction or step size
    ahead of time. Pure / env-free.
    """
    r0, r1, c0, c1 = piece.bbox
    sub = layer[r0 : r1 + 1, c0 : c1 + 1]
    current = _tight_crop(sub == piece.interior_color)
    return _shape_similarity(current, target) >= _MATCH_THRESHOLD
