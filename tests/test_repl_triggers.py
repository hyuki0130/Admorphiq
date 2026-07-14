"""Tests for the re-ruled semantic-eligibility PLAN/NAV triggers (R55 item-B).

Purpose: prove the TriggerController implements the Codex re-ruling
(`docs/r55_codex_trigger_reruling_20260714.md`): NAV fires while a declared
nav-signature goal stands (cooldown 8 env actions, max 4, no graph gate); PLAN
fires while a declared goal+milestone stand (cooldown 15, max 2); NAV precedes
PLAN; a level-up invalidates eligibility; cooldowns count executed env actions.

Expected feedback: a pass means the 2x2 plannav experiment injects the nudges on
the reviewed semantic schedule. A failure means exposure is off-spec and the run
would test the wrong schedule.
"""

from __future__ import annotations

from admorphiq.repl_agent.triggers import (
    TriggerController,
    classify_declaration,
)


def test_classify_nav_signature():
    """A navigation-shaped goal is detected; a non-nav goal is not."""
    nav, _ = classify_declaration("GOAL_HYPOTHESIS: reach the exit at the bottom")
    assert nav is True
    nav2, _ = classify_declaration("GOAL: match every colored tile to its slot")
    assert nav2 is False


def test_classify_goal_and_milestone():
    """PLAN eligibility needs BOTH a goal and a milestone in the text."""
    _, gm = classify_declaration("GOAL: sort the blocks\nMILESTONE: all four aligned")
    assert gm is True
    _, gm2 = classify_declaration("GOAL: sort the blocks")  # no milestone
    assert gm2 is False


def test_nav_fires_when_eligible_and_respects_cooldown_and_cap():
    """NAV fires at the boundary after a nav declaration, then every >=8 env
    actions, up to 4 times."""
    tc = TriggerController(nav_enabled=True)
    tc.note_declaration("GOAL_HYPOTHESIS: navigate to the target square")
    assert tc.decide() == "nav"          # fire 1
    for _ in range(7):
        tc.observe_action()
    assert tc.decide() is None           # only 7 < cooldown 8
    tc.observe_action()
    assert tc.decide() == "nav"          # fire 2 at 8 actions
    for _ in range(8 * 2):
        tc.observe_action()
    assert tc.decide() == "nav" and tc.decide() is None  # fire 3, then cooldown
    for _ in range(8):
        tc.observe_action()
    assert tc.decide() == "nav"          # fire 4
    for _ in range(8):
        tc.observe_action()
    assert tc.decide() is None           # cap 4 reached


def test_nav_needs_declaration():
    """No nav-goal declared -> NAV never fires (no stall predicate, but also no
    unconditional firing without eligibility)."""
    tc = TriggerController(nav_enabled=True)
    tc.note_declaration("GOAL: fill the grid with the right colors")  # not nav
    assert tc.decide() is None


def test_plan_fires_on_goal_and_milestone_cooldown_15_max_2():
    """PLAN fires while goal+milestone stand, cooldown 15, max 2."""
    tc = TriggerController(plan_enabled=True)
    tc.note_declaration("GOAL: reach exit\nMILESTONE: player adjacent to door")
    assert tc.decide() == "plan"         # fire 1
    for _ in range(15):
        tc.observe_action()
    assert tc.decide() == "plan"         # fire 2 at 15
    for _ in range(15):
        tc.observe_action()
    assert tc.decide() is None           # cap 2 reached


def test_nav_precedence_in_combined():
    """When both are eligible and ready, only NAV fires; PLAN stays pending and
    fires at the next boundary."""
    tc = TriggerController(plan_enabled=True, nav_enabled=True)
    tc.note_declaration("GOAL_HYPOTHESIS: navigate to exit\nMILESTONE: at the door")
    assert tc.decide() == "nav"          # NAV precedence
    assert tc.decide() == "plan"         # PLAN did not lose eligibility/budget


def test_level_up_invalidates_eligibility():
    """A level-up voids the active goal; eligibility resumes only on re-declaration."""
    tc = TriggerController(nav_enabled=True)
    tc.note_declaration("GOAL: reach the exit")
    assert tc.decide() == "nav"
    tc.invalidate_goal()
    for _ in range(8):
        tc.observe_action()
    assert tc.decide() is None           # goal void until re-declared
    tc.note_declaration("GOAL: reach the new exit")
    assert tc.decide() == "nav"          # re-declared -> eligible again


def test_disabled_flags_never_fire():
    """A disabled mechanism never injects even with a standing eligible goal."""
    tc = TriggerController(plan_enabled=False, nav_enabled=False)
    tc.note_declaration("GOAL_HYPOTHESIS: reach exit\nMILESTONE: at door")
    assert tc.decide() is None
