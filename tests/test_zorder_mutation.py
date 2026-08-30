"""Contract tests for the paint-order mutation arm (`src/admorphiq/zorder_mutation.py`).

The instrument's validity is its deliverable — a mutation that changes the MECHANIC
produces a lower score that means nothing and looks exactly like a transfer failure. These
tests pin the two properties the validity argument rests on: the permutation never moves a
sprite across a layer boundary, and it is a permutation of the very same objects.
"""

from __future__ import annotations

import pytest

from admorphiq.zorder_mutation import (
    SameLayerPermutation,
    ZOrderMutation,
    build,
    same_layer_permute,
)


class _S:
    """A sprite stand-in carrying the only attribute the permutation reads."""

    def __init__(self, tag: str, layer: int) -> None:
        self.tag = tag
        self.layer = layer

    def __repr__(self) -> str:  # pragma: no cover - failure messages only
        return f"{self.tag}@{self.layer}"


def _layers(sprites: list[_S]) -> list[int]:
    return [s.layer for s in sprites]


def test_permutation_preserves_every_layer_slot() -> None:
    """Purpose: pin the rule the whole validity argument rests on — a same-layer
    permutation must leave the sequence of LAYERS byte-identical, so no sprite can ever
    be drawn on the wrong side of a layer boundary.

    Expected feedback: a failure here means the arm has become a cross-layer reordering,
    which changes an authored property of the board and makes every score it produces
    unreadable — the run must be discarded, not re-interpreted.
    """
    sprites = [_S("a", 1), _S("b", 2), _S("c", 1), _S("d", 2), _S("e", 1)]
    for kind in ("rev", "rot"):
        out = same_layer_permute(sprites, kind)
        assert _layers(out) == _layers(sprites), kind


def test_permutation_is_a_permutation_of_the_same_objects() -> None:
    """Purpose: prove no sprite is gained, lost or duplicated. ``ZOrderPatch`` refuses the
    frame when this fails at runtime; this test says the primitive itself never does.

    Expected feedback: a failure means the board being rendered is not the board the game
    built, and every action count from the arm describes a different game.
    """
    sprites = [_S(c, i % 3) for i, c in enumerate("abcdefgh")]
    for kind in ("rev", "rot"):
        out = same_layer_permute(sprites, kind)
        assert sorted(id(s) for s in out) == sorted(id(s) for s in sprites), kind


def test_reversal_actually_reverses_within_a_layer() -> None:
    """Purpose: the arm must DO something. An inert mutation that scores identically is
    the failure mode this campaign has paid for repeatedly, so the primitive's effect is
    pinned rather than assumed.

    Expected feedback: a failure means `zrev` is a no-op and every "identical" result it
    produced is evidence of nothing.
    """
    sprites = [_S("a", 1), _S("b", 2), _S("c", 1), _S("d", 1)]
    out = same_layer_permute(sprites, "rev")
    assert [s.tag for s in out] == ["d", "b", "c", "a"]


def test_rotation_is_a_different_permutation_from_reversal() -> None:
    """Purpose: `zrot` exists so two arms can disagree — one permutation scoring
    identically could be luck of which pair happened to swap, exactly as `cperm` /
    `cperm2` guard the colour arm (rule 7ce).

    Expected feedback: a failure means the second arm is a duplicate of the first and buys
    no independence, so a flat pair of results is one measurement, not two.
    """
    sprites = [_S("a", 0), _S("b", 0), _S("c", 0)]
    rev = [s.tag for s in same_layer_permute(sprites, "rev")]
    rot = [s.tag for s in same_layer_permute(sprites, "rot")]
    assert rev == ["c", "b", "a"]
    assert rot == ["b", "c", "a"]
    assert rev != rot


def test_a_lone_sprite_on_its_layer_never_moves() -> None:
    """Purpose: a layer with one sprite has no sibling to swap with, so the mutation must
    leave it exactly where it is — the arm's disturbance is bounded by the board's own
    stacking, not by the arm.

    Expected feedback: a failure means the arm is perturbing boards that cannot exhibit
    the defect, and an 'inert' verdict would stop meaning "this game is not exposed".
    """
    sprites = [_S("a", 1), _S("b", 2), _S("c", 3)]
    assert [s.tag for s in same_layer_permute(sprites, "rev")] == ["a", "b", "c"]
    assert [s.tag for s in same_layer_permute(sprites, "rot")] == ["a", "b", "c"]


def test_identity_arm_returns_the_list_untouched() -> None:
    """Purpose: the control arm is the run's own negative control and must be an exact
    no-op; `rendergate_compare.py` refuses a verdict without it.

    Expected feedback: a failure means the control cannot reproduce the baseline and no
    other arm in that run can be read.
    """
    sprites = [_S("a", 1), _S("b", 1)]
    assert ZOrderMutation().permute(sprites) is sprites


def test_build_refuses_an_unknown_arm() -> None:
    """Purpose: there is deliberately no silent default — an unrecognised arm falling back
    to the identity would report a perfect transfer over a mutation that never ran.

    Expected feedback: a failure means a typo in a driver script can silently produce a
    flat, meaningless result.
    """
    with pytest.raises(KeyError):
        build("zreverse")
    assert isinstance(build("zrev"), SameLayerPermutation)
    assert build("identity").name == "identity"


def test_an_unknown_permutation_kind_is_rejected_at_construction() -> None:
    """Purpose: the kind is validated where it is set rather than deep inside a render
    call, so a bad arm fails before a single game is played.

    Expected feedback: a failure means a misconfigured arm would surface as a mid-run
    exception per frame, which the runner's accounting would report as a broken game
    rather than as a broken instrument.
    """
    with pytest.raises(ValueError):
        SameLayerPermutation("shuffle", "zshuffle")
