"""Pure linear-algebra-over-GF(2) kernels (R56).

Solves systems of linear equations over the field with two elements
(0 and 1, addition = XOR) via Gaussian elimination, and computes the
solution space (null space / kernel) of a coefficient matrix. This is
generic parity-system math — a matrix row states "the XOR of these
variables equals this target bit"; the kernel knows nothing about what
the variables or equations represent. Rows are accepted and returned as
tuples of 0/1 ints (documented choice — the alternative, packed integer
bitmasks, is used internally for the actual elimination since XOR-ing
whole rows as single ints is both simpler and faster than per-column
tuple arithmetic, but the public boundary stays tuple-of-bits for
readability and composability with the other frame-only kernels, whose
own coordinates/masks are always plain Python containers).

Stdlib only — no numpy. These kernels must run inside the sandboxed REPL
where only the standard library and explicitly provided modules exist.
"""

from __future__ import annotations

from collections.abc import Sequence

Row = tuple[int, ...]


def _pack(bits: Sequence[int]) -> int:
    """Bit ``i`` of the returned int is ``bits[i] & 1``."""
    value = 0
    for i, b in enumerate(bits):
        if int(b) & 1:
            value |= 1 << i
    return value


def _validate_matrix(matrix_rows: Sequence[Sequence[int]]) -> tuple[list[Row], int, int]:
    rows = [tuple(int(v) & 1 for v in row) for row in matrix_rows]
    m = len(rows)
    n = len(rows[0]) if rows else 0
    if any(len(r) != n for r in rows):
        raise ValueError("every row in matrix_rows must have the same length")
    return rows, m, n


def _reduce(packed: list[int], n: int) -> tuple[list[int], dict[int, int]]:
    """Full (reduced-row-echelon-form) elimination over columns ``0..n-1``.

    ``packed`` rows may carry extra bits at position ``>= n`` (an augmented
    target column, for :func:`gf2_solve`) — those ride along unchanged
    through every XOR row-operation, so this one routine correctly serves
    both an augmented ``[A|b]`` system and a bare coefficient matrix.

    Returns ``(reduced_rows, {pivot_column: pivot_row_index})``. Pivot rows
    end up at indices ``0..rank-1`` (in column-processing order); indices
    ``rank..len(packed)-1`` are exactly the rows with no live coefficient
    bits (in columns ``0..n-1``) left — either genuinely redundant
    equations, or (for an augmented system) an inconsistency signal in
    their target bit.
    """
    rows = list(packed)
    m = len(rows)
    pivot_row_of_col: dict[int, int] = {}
    pivot_row = 0
    for col in range(n):
        sel = None
        for r in range(pivot_row, m):
            if (rows[r] >> col) & 1:
                sel = r
                break
        if sel is None:
            continue
        rows[pivot_row], rows[sel] = rows[sel], rows[pivot_row]
        for r in range(m):
            if r != pivot_row and (rows[r] >> col) & 1:
                rows[r] ^= rows[pivot_row]
        pivot_row_of_col[col] = pivot_row
        pivot_row += 1
    return rows, pivot_row_of_col


def gf2_solve(matrix_rows: Sequence[Sequence[int]], target: Sequence[int]) -> Row | None:
    """Solve ``A x = target`` over GF(2) via Gaussian elimination.

    ``matrix_rows`` is ``A``: ``m`` equations over ``n`` variables, each row
    a length-``n`` sequence of 0/1 (row ``i``, entry ``j`` = coefficient of
    variable ``j`` in equation ``i``). ``target`` is a length-``m`` sequence
    of 0/1, the required right-hand side of each equation. Returns ONE
    particular solution — a length-``n`` tuple of 0/1 with every free
    (non-pivot) variable set to 0 — or ``None`` when the system is
    inconsistent (no assignment satisfies every equation). When the system
    is under-determined, other valid solutions exist; combine the returned
    solution with any vector from :func:`gf2_nullspace` (via elementwise
    XOR) to enumerate them. An all-empty ``matrix_rows`` (``m == 0``)
    trivially solves to ``()`` (zero variables, nothing to satisfy).
    """
    rows, m, n = _validate_matrix(matrix_rows)
    t = [int(v) & 1 for v in target]
    if len(t) != m:
        raise ValueError(f"target length {len(t)} must match matrix_rows row count {m}")
    packed = [_pack(rows[i]) | (t[i] << n) for i in range(m)]
    reduced, pivot_row_of_col = _reduce(packed, n)
    rank = len(pivot_row_of_col)
    for r in range(rank, m):
        coeff_zero = (reduced[r] & ((1 << n) - 1)) == 0
        target_bit = (reduced[r] >> n) & 1
        if coeff_zero and target_bit:
            return None
    x = [0] * n
    for col, r in pivot_row_of_col.items():
        x[col] = (reduced[r] >> n) & 1
    return tuple(x)


def gf2_nullspace(matrix_rows: Sequence[Sequence[int]]) -> list[Row]:
    """A basis for the null space of ``A`` (vectors ``x`` with ``A x = 0``).

    Returns one length-``n`` tuple of 0/1 per FREE variable of ``A`` (one
    basis vector per degree of freedom) — every 0/1 linear combination
    (elementwise XOR) of these vectors is also a solution to ``A x = 0``,
    giving the full null space (``2**len(basis)`` vectors) without
    enumerating it directly. An empty list means ``A`` has a trivial null
    space (only the all-zero vector, i.e. every column is a pivot column —
    the system, when solvable, has a UNIQUE solution).
    """
    rows, _m, n = _validate_matrix(matrix_rows)
    packed = [_pack(r) for r in rows]
    reduced, pivot_row_of_col = _reduce(packed, n)
    pivot_cols = set(pivot_row_of_col)
    free_cols = [c for c in range(n) if c not in pivot_cols]
    basis: list[Row] = []
    for f in free_cols:
        vec = [0] * n
        vec[f] = 1
        for col, r in pivot_row_of_col.items():
            vec[col] = (reduced[r] >> f) & 1
        basis.append(tuple(vec))
    return basis
