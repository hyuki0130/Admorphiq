"""Attribution by proximity must be an ERROR, not a silent guess.

Purpose: pin that `scripts/trace_attribute.py` refuses to attribute an event to a level unless the
event line names the level itself.

Expected feedback: a FAIL means the refusal was weakened, and the carry-forward trap that produced
three withdrawn findings on 2026-08-28 is open again.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "trace_attribute",
    pathlib.Path(__file__).resolve().parent.parent / "scripts" / "trace_attribute.py",
)
assert _SPEC and _SPEC.loader
ta = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ta)


def test_events_naming_their_level_are_grouped_exactly() -> None:
    """An event that says which level it is on is counted against that level and no other.

    Purpose: proves the happy path attributes by the event's own field.

    Expected feedback: a FAIL means correct traces are being mis-grouped, which would make every
    per-level table wrong in the other direction.
    """
    per = ta.parse(
        ["[rp] lvl=6 pairings=2", "[rp] lvl=6 pairings=2", "[rp] lvl=5 pairings=1"], "rp"
    )
    assert per[6]["pairings=2"] == 2
    assert per[5]["pairings=1"] == 1
    assert 4 not in per


def test_an_event_without_a_level_is_refused() -> None:
    """A trace whose events do not name their level raises instead of guessing.

    Purpose: this is the whole reason the module exists — proximity attribution turned ten read
    failures into "499 of 500 actions" and assigned level 6's model to level 7.

    Expected feedback: a FAIL means the module went back to inferring the level from context.
    """
    with pytest.raises(SystemExit) as exc:
        ta.parse(["[rp] pairings=2", "[lvl] 6"], "rp")
    assert "no lvl=" in str(exc.value)


def test_other_tags_are_ignored() -> None:
    """Only the requested tag is parsed, so one trace can carry several instruments.

    Purpose: lets a single run be attributed per instrument without re-running the game.

    Expected feedback: a FAIL means tags leak into each other's counts.
    """
    per = ta.parse(["[rp] lvl=1 a=1", "[zz] b=2"], "rp")
    assert per[1]["a=1"] == 1
    assert len(per) == 1
