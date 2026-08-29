"""Contract pins for crag's MIRROR rule — a hazard recognised the other way up (round r101).

Engine-free: the frames and the two spike faces are built here, so the pins hold on a clean
checkout with no game environments present.

What this protects. crag identifies a cell by `_sig`, an order-free colour histogram of a window
that `_cores` insets a pixel on BOTH sides. On a family whose gravity reverses, the same hazard is
drawn twice — once pointing with the axis and once against it, the same art flipped — and that
window is NOT closed under the flip, so the two orientations arrive as two unrelated kinds and each
costs a death to learn. Measured on bp35: four spike deaths in a 730-action run, two of which named
a kind, and those two kinds are one glyph the two ways up.

`_faces` is the second, one-pixel-wider window that IS closed under the flip, and `_mirror_join`
names the twin lethal ON SIGHT. `_sig` is untouched — every routing decision in the file still runs
on the histogram, and the face is only ever read by this rule.
"""

from __future__ import annotations

import numpy as np

from admorphiq.tools.crag import CragTool, _cores, _faces, _sig

PITCH = 6
BG = 10


def _face_of(tile: list[list[int]]) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(v) for v in row) for row in tile)


def _grid(tiles: dict[tuple[int, int], list[list[int]]]) -> np.ndarray:
    """A 64x64 frame with one 7x7 glyph per cell, drawn on the pitch-6 lattice."""
    g = np.full((64, 64), BG, dtype=np.int64)
    for (r, c), art in tiles.items():
        y, x = r * PITCH, c * PITCH
        for dy, row in enumerate(art):
            for dx, v in enumerate(row):
                if v >= 0 and y + dy < 64 and x + dx < 64:
                    g[y + dy, x + dx] = v
    return g


# bp35's spike, as the game's own sprite table draws it: `hzusueifitk` is the art, and
# `ubhhgljbnpu` is the SAME art reversed. Colours are the game's own indices.
_SPIKE_UP = [
    [-1, 5, 5, 5, 5, 5, -1],
    [-1, 5, 11, 0, 11, 5, -1],
    [-1, 5, 15, 15, 15, 5, -1],
    [-1, 5, 15, 15, 15, 5, -1],
    [-1, 5, 15, 15, 15, 5, -1],
    [-1, 5, 15, 15, 15, 5, -1],
    [-1, -1, -1, -1, -1, -1, -1],
]
_SPIKE_DOWN = _SPIKE_UP[::-1]


def test_face_window_is_closed_under_a_vertical_flip() -> None:
    """Purpose: pin that `_faces` reads the window the mirror rule needs — rows 1..p-1 of a glyph
    drawn p+1 tall — so a glyph and its reverse give faces that are each other's flip.

    Expected feedback: failing means the window drifted back to `_cores`' doubly-inset core (which
    reads rows 1..p-2 and is NOT flip-closed), and the mirror rule can no longer join anything.
    """
    g = _grid({(1, 1): _SPIKE_UP, (3, 1): _SPIKE_DOWN})
    faces = dict(_faces(g, PITCH, 0, 0))
    up, down = faces[(1, 1)], faces[(3, 1)]
    assert up.shape == (PITCH - 1, PITCH - 1)
    assert np.array_equal(np.flipud(up), down)


def test_the_two_spike_orientations_are_two_signatures() -> None:
    """Purpose: pin the defect the rule exists for — the histogram crag routes on does NOT join the
    two orientations, so without the face they are two kinds and cost two deaths.

    Expected feedback: if this ever passes trivially (the sigs turn out equal) the rule is dead
    weight and should be deleted rather than kept "just in case".
    """
    g = _grid({(1, 1): _SPIKE_UP, (3, 1): _SPIKE_DOWN})
    cores = dict(_cores(g, PITCH, 0, 0))
    assert _sig(cores[(1, 1)]) != _sig(cores[(3, 1)])


def _tool_with(up_sig, down_sig, up_face, down_face) -> CragTool:
    t = CragTool()
    t._air = ((BG, 16),)
    t._lethal = {down_sig}
    t._face = {down_sig: {down_face}, up_sig: {up_face}}
    return t


def test_mirror_join_names_the_flipped_twin_lethal_on_sight() -> None:
    """Purpose: prove the rule fires without a death — the twin is named from the frame alone.

    Expected feedback: failing means bp35 pays a second discovery death on its fifth board, which
    is measured at 14 actions and 0.21 of that level's score.
    """
    g = _grid({(1, 1): _SPIKE_UP, (3, 1): _SPIKE_DOWN})
    cores, faces = dict(_cores(g, PITCH, 0, 0)), dict(_faces(g, PITCH, 0, 0))
    up_sig, down_sig = _sig(cores[(1, 1)]), _sig(cores[(3, 1)])
    t = _tool_with(up_sig, down_sig, _face_of(faces[(1, 1)]), _face_of(faces[(3, 1)]))
    t._mirror_join()
    assert up_sig in t._lethal


def test_mirror_join_refuses_a_kind_the_body_has_stood_on() -> None:
    """Purpose: pin that an OBSERVATION outranks the inference. A kind that has held the body
    without killing it is never renamed lethal, whatever it is drawn like.

    Expected feedback: failing means one false join can wall the tool into a pocket it walked out
    of a moment earlier — the shape that cost this tool two levels the last time its candidate set
    was widened.
    """
    g = _grid({(1, 1): _SPIKE_UP, (3, 1): _SPIKE_DOWN})
    cores, faces = dict(_cores(g, PITCH, 0, 0)), dict(_faces(g, PITCH, 0, 0))
    up_sig, down_sig = _sig(cores[(1, 1)]), _sig(cores[(3, 1)])
    t = _tool_with(up_sig, down_sig, _face_of(faces[(1, 1)]), _face_of(faces[(3, 1)]))
    t._safe = {up_sig}
    t._mirror_join()
    assert up_sig not in t._lethal


def test_mirror_join_refuses_an_ambiguous_kind() -> None:
    """Purpose: pin the guard against a histogram two different arrangements share. A signature
    seen with more than one face cannot be matched, in either direction.

    Expected feedback: failing means a colour count that happens to coincide is enough to condemn
    an innocent kind — the rule would then be a colour heuristic rather than a shape one.
    """
    g = _grid({(1, 1): _SPIKE_UP, (3, 1): _SPIKE_DOWN})
    cores, faces = dict(_cores(g, PITCH, 0, 0)), dict(_faces(g, PITCH, 0, 0))
    up_sig, down_sig = _sig(cores[(1, 1)]), _sig(cores[(3, 1)])
    t = _tool_with(up_sig, down_sig, _face_of(faces[(1, 1)]), _face_of(faces[(3, 1)]))
    other = _face_of(np.zeros((PITCH - 1, PITCH - 1), dtype=int))
    t._face[up_sig].add(other)
    t._mirror_join()
    assert up_sig not in t._lethal


def test_mirror_join_does_nothing_without_a_named_hazard() -> None:
    """Purpose: pin that the rule is driven by a hazard already learned, never by shape alone.
    Nothing in a frame says which of its kinds kills; the flip only ever COPIES a verdict.

    Expected feedback: failing means the tool invents lethality, and every board with a mirrored
    decoration becomes unwalkable.
    """
    g = _grid({(1, 1): _SPIKE_UP, (3, 1): _SPIKE_DOWN})
    cores, faces = dict(_cores(g, PITCH, 0, 0)), dict(_faces(g, PITCH, 0, 0))
    up_sig, down_sig = _sig(cores[(1, 1)]), _sig(cores[(3, 1)])
    t = _tool_with(up_sig, down_sig, _face_of(faces[(1, 1)]), _face_of(faces[(3, 1)]))
    t._lethal = set()
    t._mirror_join()
    assert not t._lethal
