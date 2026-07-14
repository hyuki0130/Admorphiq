"""Tests for the frozen PLAN/NAV no-progress trigger controller (R55 item B).

Purpose: prove the TriggerController implements the Codex-frozen definitions
exactly — PLAN fires at 12 no-progress actions (cooldown 15, max 2), NAV fires at
4 stalled movements (cooldown 8, max 4, no-op without a traversability graph),
NAV precedes PLAN, and a level advance clears the stall streaks.

Expected feedback: a pass means the trigger logic matches the reviewed spec and
the 2x2 plannav experiment measures the intended intervention. A failure means
the triggers fire off-spec and any run would test the wrong thing.
"""

from __future__ import annotations

from admorphiq.repl_agent.triggers import TriggerConfig, TriggerController


def _stall(tc, n, *, movement=False, sh="s"):
    """Feed n stalled actions (no change, no progress)."""
    for i in range(n):
        tc.observe(movement=movement, board_changed=False, level_up=False,
                   state_hash=f"{sh}{i}")


def test_plan_fires_at_12_no_progress():
    """PLAN must fire only after 12 consecutive no-progress/no-change actions."""
    tc = TriggerController(plan_enabled=True)
    _stall(tc, 11)
    assert tc.decide(has_traversability_graph=False) is None  # 11 < 12
    _stall(tc, 1)
    assert tc.decide(has_traversability_graph=False) == "plan"


def test_plan_streak_resets_on_material_change():
    """A board change resets the PLAN streak — progress is being made."""
    tc = TriggerController(plan_enabled=True)
    _stall(tc, 11)
    tc.observe(movement=False, board_changed=True, level_up=False, state_hash="x")
    _stall(tc, 11)
    assert tc.decide(has_traversability_graph=False) is None  # streak restarted


def test_plan_respects_cooldown_and_max():
    """PLAN honors the 15-action cooldown and 2-invocation cap."""
    tc = TriggerController(config=TriggerConfig(plan_cooldown=15, plan_max=2),
                           plan_enabled=True)
    _stall(tc, 12)
    assert tc.decide(has_traversability_graph=False) == "plan"  # fire 1
    _stall(tc, 12)  # streak rebuilds but cooldown (15) not elapsed (only 12 actions)
    assert tc.decide(has_traversability_graph=False) is None
    _stall(tc, 3)   # now 15 since fire, streak >= 12
    assert tc.decide(has_traversability_graph=False) == "plan"  # fire 2
    _stall(tc, 20)
    assert tc.decide(has_traversability_graph=False) is None    # max 2 reached


def test_nav_fires_at_4_stalled_movements_with_graph():
    """NAV fires after 4 stalled movement attempts, but only when a traversability
    graph exists; without one it is a no-op that does not consume budget."""
    tc = TriggerController(nav_enabled=True)
    _stall(tc, 4, movement=True)
    assert tc.decide(has_traversability_graph=False) is None      # no-op, no graph
    # budget not consumed: with a graph now available it fires
    assert tc.decide(has_traversability_graph=True) == "nav"


def test_nav_progress_resets_stall():
    """A productive movement (board changed + novel state) resets the NAV stall."""
    tc = TriggerController(nav_enabled=True)
    _stall(tc, 3, movement=True)
    tc.observe(movement=True, board_changed=True, level_up=False, state_hash="new")
    _stall(tc, 3, movement=True)
    assert tc.decide(has_traversability_graph=True) is None  # stall < 4 after reset


def test_nav_loop_counts_as_stall():
    """Revisiting a recent state (a loop) is a stall even if the board changed."""
    tc = TriggerController(nav_enabled=True)
    # first a,b are novel (progress); the a,b,a,b that follow are a 4-step loop.
    for sh in ["a", "b", "a", "b", "a", "b"]:
        tc.observe(movement=True, board_changed=True, level_up=False, state_hash=sh)
    assert tc.decide(has_traversability_graph=True) == "nav"


def test_nav_precedes_plan_when_both_eligible():
    """In the Combined cell, when both triggers are ready only NAV fires."""
    tc = TriggerController(plan_enabled=True, nav_enabled=True)
    # 12 stalled movements -> both plan_streak>=12 and move_stall>=4
    _stall(tc, 12, movement=True)
    assert tc.decide(has_traversability_graph=True) == "nav"


def test_reset_level_clears_streaks():
    """A level advance clears stall streaks (progress) but preserves fire caps."""
    tc = TriggerController(plan_enabled=True)
    _stall(tc, 12)
    tc.decide(has_traversability_graph=False)  # fire 1 (count=1)
    tc.reset_level()
    _stall(tc, 11)
    assert tc.decide(has_traversability_graph=False) is None  # streak cleared
    assert tc.stats["plan_fires"] == 1  # cap counter preserved
