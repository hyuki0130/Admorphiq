"""Private shared normalization helper for the kernel modules (R56).

Not part of the public kernel API — never imported via
``admorphiq.kernels.__init__``/``__all__``. This module exists solely so
``motion.py``, ``regions.py``, and ``canonical.py`` share ONE
frame-normalization implementation instead of independently maintained
(and, until this module existed, silently DIVERGING — ``regions.py``'s own
copy omitted the ``int(v)`` cast the other two modules applied, so a caller
passing ``1`` and ``1.0`` for the same colour got different grouping
behaviour in ``find_regions`` than in ``motion``/``canonical``'s functions;
see ``docs/r56_kernel_catalog.md``'s API-inconsistency note #1) private
copies.
"""

from __future__ import annotations

from collections.abc import Sequence

Grid = tuple[tuple[int, ...], ...]


def normalize_frame(frame: Sequence[Sequence[object]]) -> Grid:
    """Coerce any nested sequence of int-castable values into a ``Grid``.

    Every cell is cast via ``int(v)`` so callers passing mixed int/float
    colour indices (e.g. ``1`` and ``1.0``) normalize to the SAME value and
    are never silently treated as different colours by a downstream
    same-colour comparison. Row/column counts are preserved exactly as
    given — this does NOT collapse an all-empty-rows grid to ``()``; a
    caller that needs that additional collapse (as ``canonical.py`` does,
    for its own documented empty-frame contract) applies it on top of this
    function's result.
    """
    return tuple(tuple(int(v) for v in row) for row in frame)
