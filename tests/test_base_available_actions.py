"""Tests for ``admorphiq.adapters25.base.available_action_ids`` (task #46).

The function classifies a frame's ``available_actions`` into
``(simple_non_coordinate_ids, action6_ok)``. It previously dropped ACTION7,
which silently made undo unreachable for every adapter that filtered on the
returned id list (ar25/sk48 listed 7 in their filters but never received it;
bp35/lf52 pass the whole list through as move labels). These tests pin the
corrected contract so ACTION7 cannot be re-dropped by a future edit.
"""

from __future__ import annotations

from types import SimpleNamespace

from admorphiq.adapters25.base import available_action_ids


def _frame(available):
    return SimpleNamespace(available_actions=available)


def test_action7_is_surfaced():
    """Purpose: prove ACTION7 (undo) now appears in the simple-id list — the
    exact regression this task fixes. Expected feedback: a PASS means every
    adapter that filters on this list can reach undo; a FAIL means ACTION7 was
    dropped again and undo is silently unreachable."""
    simple_ids, action6_ok = available_action_ids(_frame([1, 2, 3, 4, 7]))
    assert 7 in simple_ids
    assert simple_ids == [1, 2, 3, 4, 7]
    assert action6_ok is False


def test_action6_is_a_flag_not_an_id():
    """Purpose: ACTION6 (the only coordinate action) stays reported as the
    ``action6_ok`` flag, never mixed into the simple-id list. Expected
    feedback: a FAIL means a click id leaked into the move-id list, which
    would make ``simple_action(6)`` (a coordinate action issued with no
    coordinates) reachable."""
    simple_ids, action6_ok = available_action_ids(_frame([1, 6]))
    assert action6_ok is True
    assert 6 not in simple_ids
    assert simple_ids == [1]


def test_reset_id_zero_is_excluded():
    """Purpose: RESET (id 0) is driven explicitly by adapters, not chosen as a
    move, so it must not appear as a simple id. Expected feedback: a FAIL means
    RESET could be picked mid-plan as if it were a normal action."""
    simple_ids, _ = available_action_ids(_frame([0, 1, 2]))
    assert 0 not in simple_ids
    assert simple_ids == [1, 2]


def test_order_preserved_and_object_actions_supported():
    """Purpose: ids are returned in ``available_actions`` order, and action
    objects (carrying ``.value``/``.id``) are accepted alongside bare ints —
    the two shapes arcengine may hand an adapter. Expected feedback: a FAIL
    means either the order was silently changed (callers that rely on
    ``[0]`` would pick a different action) or object-form actions were skipped
    (an adapter would see an empty action set on a live frame)."""
    simple_ids, action6_ok = available_action_ids(
        _frame([SimpleNamespace(value=4), SimpleNamespace(value=1), SimpleNamespace(value=6)])
    )
    assert simple_ids == [4, 1]
    assert action6_ok is True


def test_empty_or_missing_actions():
    """Purpose: a frame with no actions (or the attribute absent) yields an
    empty set, not a crash. Expected feedback: a FAIL means a NOT_PLAYED /
    frameless observation could raise inside an adapter's decision path."""
    assert available_action_ids(_frame([])) == ([], False)
    assert available_action_ids(SimpleNamespace()) == ([], False)
