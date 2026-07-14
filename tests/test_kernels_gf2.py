"""Tests for the pure GF(2) linear-algebra kernels (R56)."""

import pytest

from admorphiq.kernels.gf2 import gf2_nullspace, gf2_solve


def _matvec(matrix_rows, x):
    """Reference matrix-vector product mod 2, used only to VERIFY kernel
    output in these tests — never imported by the kernel itself."""
    return [sum(row[j] * x[j] for j in range(len(x))) % 2 for row in matrix_rows]


def _plus_stencil_3x3():
    """The classic 3x3 'clicking a cell toggles itself + orthogonal
    neighbors' coefficient matrix, built programmatically (not hand-typed)
    so the test data itself is trustworthy."""

    def idx(r, c):
        return r * 3 + c

    a = [[0] * 9 for _ in range(9)]
    for r in range(3):
        for c in range(3):
            i = idx(r, c)
            a[i][i] = 1
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < 3 and 0 <= nc < 3:
                    a[i][idx(nr, nc)] = 1
    return a


def test_gf2_solve_3x3_toggle_system_verified_by_reapplication():
    """Purpose: on a real 3x3 toggle-stencil system (9 equations, 9
    variables, built programmatically), gf2_solve must return a solution
    that, when matrix-multiplied back through A, reproduces the exact
    target — the only trustworthy way to check a linear-algebra kernel
    (comparing to a specific expected vector would be wrong whenever the
    system has multiple valid solutions).
    Expected feedback: failure means the Gaussian elimination itself is
    wrong (a real, checkable arithmetic error), not a data-mismatch."""
    a = _plus_stencil_3x3()
    k_star = [1, 0, 1, 0, 1, 0, 1, 0, 1]  # an arbitrary known assignment
    target = _matvec(a, k_star)  # derive a GUARANTEED-solvable target from it

    solution = gf2_solve(a, target)
    assert solution is not None
    assert _matvec(a, solution) == target


def test_gf2_nullspace_full_rank_matrix_is_empty():
    """Purpose: the 3x3 plus-stencil matrix above is full rank (a real,
    measured property of that system — every column ends up a pivot
    column), so its null space must be the trivial {zero vector} — the
    documented 'empty basis list' contract for a uniquely-solvable system.
    Expected feedback: failure (a nonempty basis) means free-column
    detection is wrong, which would make gf2_solve's companion
    'combine with a nullspace vector for alternates' guidance false for
    this system."""
    a = _plus_stencil_3x3()
    assert gf2_nullspace(a) == []


def test_gf2_solve_unsolvable_system_returns_none():
    """Purpose: two equations that directly contradict each other
    (row0 forces x0=0, row1 forces the SAME x0=1) must be detected as
    inconsistent and return None, not a garbage/partial vector.
    Expected feedback: failure means the post-elimination consistency
    check (leftover row has zero coefficients but a nonzero target bit)
    is missing or broken — silently returning a vector that does NOT
    actually satisfy the system."""
    assert gf2_solve([[1, 0], [1, 0]], [0, 1]) is None


def test_gf2_nullspace_basis_vectors_verify_and_combine():
    """Purpose: a genuinely rank-deficient system (2 equations, 4
    variables — guaranteed at least 2 degrees of freedom) must return a
    basis whose vectors EACH satisfy A v = 0, and whose XOR combination
    ALSO satisfies A v = 0 (closure of the null space under addition mod
    2) — proving the basis is real, not just the right size.
    Expected feedback: failure on any single vector means free-variable
    back-substitution is wrong; failure on the combination means the
    basis vectors aren't actually independent solutions of the same
    homogeneous system."""
    a = [[1, 0, 1, 0], [0, 1, 0, 1]]
    basis = gf2_nullspace(a)
    assert len(basis) == 2
    for v in basis:
        assert _matvec(a, v) == [0, 0]
    combo = tuple(x ^ y for x, y in zip(basis[0], basis[1]))
    assert _matvec(a, list(combo)) == [0, 0]


def test_gf2_solve_plus_nullspace_vector_is_an_alternate_solution():
    """Purpose: on the same rank-deficient system, gf2_solve's own
    documented composition guidance must actually hold: XOR-ing its
    returned solution with a nullspace basis vector produces a DIFFERENT
    vector that still satisfies A x = target — the mechanism a caller
    would use to search for a lower-weight (fewer set bits) solution.
    Expected feedback: failure means the solution and null space live in
    inconsistent coordinate systems (e.g. a column-ordering mismatch
    between the two functions), breaking the documented composition."""
    a = [[1, 0, 1, 0], [0, 1, 0, 1]]
    target = [1, 1]
    solution = gf2_solve(a, target)
    basis = gf2_nullspace(a)
    alternate = tuple(s ^ b for s, b in zip(solution, basis[0]))
    assert alternate != solution
    assert _matvec(a, list(alternate)) == target


def test_gf2_solve_coerces_non_binary_ints_via_parity():
    """Purpose: only the PARITY of each input value matters (matching the
    'clicked an even/odd number of times' semantics this kernel is meant
    to serve) — a 2 or 3 in the input must behave exactly like 0 or 1.
    Expected feedback: failure means the module trusts raw truthiness/
    equality instead of explicit `& 1` masking, which would silently
    misbehave on any caller passing raw click counts instead of pre-
    reduced parities."""
    assert gf2_solve([[2, 0], [0, 3]], [0, 1]) == (0, 1)


def test_gf2_solve_empty_system_is_trivial():
    """Purpose: zero equations (and therefore zero inferable variables)
    is a degenerate but well-defined case — the empty solution `()`,
    not an error.
    Expected feedback: failure means a genuinely empty observation (no
    equations formed yet) crashes instead of returning the trivially
    correct 'nothing to solve' answer."""
    assert gf2_solve([], []) == ()
    assert gf2_nullspace([]) == []


def test_gf2_solve_mismatched_target_length_raises():
    """Purpose: a target vector whose length doesn't match the number of
    equations is a caller error (a genuine shape mismatch, not something
    the kernel should silently truncate or pad) and must raise loudly.
    Expected feedback: failure means a caller's off-by-one bug in
    assembling the system produces a silently wrong or index-crashing
    result instead of a clear, immediate error."""
    with pytest.raises(ValueError):
        gf2_solve([[1, 0], [0, 1]], [0, 0, 0])


def test_gf2_matrix_ragged_rows_raises():
    """Purpose: matrix_rows whose rows disagree on variable count is an
    invalid system and must raise, for both entry points.
    Expected feedback: failure means ragged input silently produces a
    wrong variable count (derived from just the first row) instead of
    being rejected."""
    with pytest.raises(ValueError):
        gf2_solve([[1, 0], [1, 0, 1]], [0, 0])
    with pytest.raises(ValueError):
        gf2_nullspace([[1, 0], [1, 0, 1]])
