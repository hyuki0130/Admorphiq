"""Pins for R98's explanation checker — the thing that decides whether a model's stated
reason is TRUE of the animation it was shown.

Purpose
-------
This logic was wrong twice on the day it was written, in opposite directions: it convicted a
model for naming what was absent, and then, once counterfactuals were excused, it excused a
genuine negative claim as hypothetical. Either failure makes the checker useless in a way that
looks like it is working — one flags everything, the other flags nothing.

Expected feedback
-----------------
A failure means the checker has drifted back to matching words instead of claims, and any
verdict about a model's reasoning taken through it is unfounded.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_R98 = Path(__file__).resolve().parents[1] / "scripts" / "rounds" / "R98"
_spec = importlib.util.spec_from_file_location(
    "r98_explanation_check", _R98 / "explanation_check.py"
)
explanation_check = importlib.util.module_from_spec(_spec)
sys.modules["r98_explanation_check"] = explanation_check
_spec.loader.exec_module(explanation_check)

GEMMA4 = (
    "The animation showed a stream reaching the bottom edge and stopping, yet the level did "
    "not advance despite all targets being satisfied, implying the attempt was still active "
    "rather than failed. If the animation had ended immediately with a failure screen or a "
    "reset of the flow and targets upon that stream's termination, I would have chosen "
    "`terminate_fatal`."
)


def test_naming_what_was_absent_is_not_a_false_claim() -> None:
    """Purpose: pins the counterfactual rule against the reply that broke the first version.
    gemma4 names a failure screen only to say it did NOT appear, which is the opposite of
    asserting one.
    Expected feedback: a failure means the checker convicts a model for describing what it did
    not see, and every explanation that reasons by contrast is scored as a fabrication."""
    assert explanation_check.check(GEMMA4) == []


def test_a_negative_claim_is_still_a_claim() -> None:
    """Purpose: pins the second failure. The counterfactual guard once listed "no" and "not",
    so a genuine assertion about the animation was excused as hypothetical.
    Expected feedback: a failure means negation is being read as conditional framing again, and
    a whole class of false citations passes unchecked."""
    hits = explanation_check.check(
        "The targets were not satisfied when the stream stopped, so the level could not advance."
    )
    assert hits and "unsatisfied" in hits[0]


def test_a_fabricated_barrier_contact_is_caught() -> None:
    """Purpose: the capture shows no flow cell in the hazard row at all, so a reply claiming
    the flow entered or was destroyed by the barrier is citing something that did not happen.
    Expected feedback: a failure means the checker has stopped catching the citation it exists
    for."""
    hits = explanation_check.check(
        "The stream entered the barrier and was destroyed by it, so the attempt ended there."
    )
    assert hits and "hazard row" in hits[0]


def test_a_plain_observation_passes() -> None:
    """Purpose: the checker must stay quiet on an accurate report, or it will be switched off.
    Expected feedback: a failure means it flags truthful descriptions, which is the failure
    mode that makes a checker worse than none."""
    assert explanation_check.check(
        "A stream came to rest one row above the bottom edge and the level did not advance."
    ) == []
