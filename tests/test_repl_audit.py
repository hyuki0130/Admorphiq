"""Tests for the counter-triggered goal-falsification audit (R55 v7-3).

Lock the mechanism Codex specified: audits trigger at action thresholds (not
every N), demand structured falsifiable goal fields, track bounded-horizon
milestone misses, and force the alternative after two misses. Plus the agent
wiring is flag-gated (default OFF) so v6-vs-v7 stays one-variable.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from admorphiq.repl_agent.agent import ReplAgent
from admorphiq.repl_agent.audit import GoalAuditor


def _obs(frame, avail=(3, 4, 6), levels=0):
    return SimpleNamespace(frame=frame, state=SimpleNamespace(name="PLAYING"),
                           available_actions=list(avail), levels_completed=levels)


def _frame():
    f = np.zeros((16, 16), dtype=np.int16)
    f[5, 5] = 2
    return f


def test_due_fires_at_thresholds_once():
    """Purpose: due() fires when a threshold is reached and only once per
    threshold.

    Feedback: failure means audits never trigger or spam every turn.
    """
    a = GoalAuditor(thresholds=(12, 24))
    assert a.due(5) is False
    assert a.due(12) is True
    a.on_audit({"hypothesis": "h", "milestone": "m within 8 actions",
                "falsifier": "f", "alternative": "alt"}, 12)
    assert a.due(12) is False           # audited
    assert a.due(24) is True            # next threshold


def test_parse_extracts_structured_fields():
    """Purpose: the labeled audit fields parse out of a reply.

    Feedback: failure means the structured goal statement is lost.
    """
    raw = ("GOAL_HYPOTHESIS: deliver A to G\nEXPECTED_MILESTONE: A in G within 6 "
           "actions\nFALSIFIER: A never nears G\nALTERNATIVE_HYPOTHESIS: merge pairs\n"
           "LEFT")
    p = GoalAuditor().parse(raw)
    assert p["hypothesis"] == "deliver A to G"
    assert p["alternative"] == "merge pairs"


def test_milestone_miss_twice_forces_alternative():
    """Purpose: a declared milestone missed twice sets force_alternative, which
    the next audit prompt uses to require the alternative.

    Feedback: failure means a wrong goal is never abandoned (the su15 loop).
    """
    a = GoalAuditor(thresholds=(12, 24, 48), default_horizon=4)
    a.on_audit({"hypothesis": "wrong goal", "milestone": "X within 4 actions",
                "falsifier": "f", "alternative": "right goal"}, 12)
    # deadline = 16; no level advance by then -> miss.
    assert a.check_milestone(16, level_advanced=False) == "missed"
    assert a.state.misses == 1
    a.on_audit({"hypothesis": "wrong goal", "milestone": "X within 4 actions",
                "falsifier": "f", "alternative": "right goal"}, 24)
    assert a.check_milestone(28, level_advanced=False) == "missed"
    assert a.force_alternative() is True
    assert "ALTERNATIVE" in a.prompt_section() and "right goal" in a.prompt_section()


def test_milestone_met_resets_misses():
    """Purpose: a level advance meets the milestone and clears misses.

    Feedback: failure means a correct goal is wrongly penalized.
    """
    a = GoalAuditor(default_horizon=4)
    a.on_audit({"hypothesis": "g", "milestone": "m", "falsifier": "f",
                "alternative": "alt"}, 12)
    assert a.check_milestone(13, level_advanced=True) == "met"
    assert a.state.misses == 0


def test_agent_audit_is_flag_gated_off_by_default():
    """Purpose: with audit_enabled=False (default) no AUDIT block is emitted; with
    True it appears once the threshold is crossed.

    Feedback: failure means v6 (P0-only) would be contaminated by the audit.
    """
    prompts: list[str] = []

    def cap(prompt, images=None):
        prompts.append(prompt)
        return '{"action":"LEFT"}'

    off = ReplAgent(SimpleNamespace(complete=cap), render_images=False)
    for _ in range(14):
        off.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert not any("AUDIT" in p for p in prompts)  # default off

    prompts.clear()
    on = ReplAgent(SimpleNamespace(complete=cap), render_images=False,
                   audit_enabled=True)
    for _ in range(14):
        on.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert any("AUDIT" in p and "GOAL_HYPOTHESIS" in p for p in prompts)
    # audits_triggered counts REAL firings (once, at the 12 threshold), NOT the
    # prompt appearances (Codex v7 review: the latter overcounts).
    assert on.audits_triggered == 1


def test_nav_trigger_decoupled_from_audit():
    """Purpose: the re-ruled NAV trigger (default OFF) injects the shortest_path
    nudge on the boundary AFTER the model declares a nav-shaped goal — with audit
    OFF — and never fires when disabled or when no nav goal is declared.

    Feedback: failure means NAV is still audit-coupled, fires without a declared
    nav goal, or leaks when the flag is off.
    """
    prompts: list[str] = []

    def nav_cap(prompt, images=None):
        prompts.append(prompt)
        return "GOAL_HYPOTHESIS: reach the exit\nLEFT"

    # nav OFF -> no shortest_path nudge even though a nav goal is declared.
    a = ReplAgent(SimpleNamespace(complete=nav_cap), render_images=False)
    for _ in range(6):
        a.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert not any("navigation-shaped (reach" in p for p in prompts)

    # nav ON, audit OFF -> nudge fires after the goal declaration, no AUDIT section.
    prompts.clear()
    b = ReplAgent(SimpleNamespace(complete=nav_cap), render_images=False,
                  nav_steering=True)
    for _ in range(6):
        b.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert any("navigation-shaped (reach" in p and "AUDIT" not in p for p in prompts)

    # nav ON but the model never declares a nav goal -> never fires.
    prompts.clear()
    def flat_cap(prompt, images=None):
        prompts.append(prompt)
        return "GOAL: match the colors\nLEFT"
    c = ReplAgent(SimpleNamespace(complete=flat_cap), render_images=False,
                  nav_steering=True)
    for _ in range(6):
        c.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert not any("navigation-shaped (reach" in p for p in prompts)


def test_plan_trigger_needs_goal_and_milestone():
    """Purpose: the re-ruled PLAN trigger (default OFF) requests a MACRO once the
    model has declared BOTH a goal and a milestone — decoupled from the audit —
    and never fires with a goal alone or when disabled.

    Feedback: failure means PLAN fires without a milestone, stays audit-coupled,
    or leaks when off.
    """
    prompts: list[str] = []

    def gm_cap(prompt, images=None):
        prompts.append(prompt)
        return "GOAL_HYPOTHESIS: reach the exit\nMILESTONE: at the door\nLEFT"

    # plan OFF -> no macro nudge.
    off = ReplAgent(SimpleNamespace(complete=gm_cap), render_images=False)
    for _ in range(4):
        off.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert not any('"macro"' in p for p in prompts)

    # plan ON + goal & milestone declared -> macro nudge fires, no AUDIT section.
    prompts.clear()
    on = ReplAgent(SimpleNamespace(complete=gm_cap), render_images=False,
                   plan_enabled=True)
    for _ in range(4):
        on.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert any('"macro"' in p and "AUDIT" not in p for p in prompts)

    # plan ON but only a goal (no milestone) -> never fires.
    prompts.clear()
    def goal_only(prompt, images=None):
        prompts.append(prompt)
        return "GOAL_HYPOTHESIS: reach the exit\nLEFT"
    g = ReplAgent(SimpleNamespace(complete=goal_only), render_images=False,
                  plan_enabled=True)
    for _ in range(4):
        g.choose_action([], _obs(_frame(), avail=(1, 2, 3, 4)))
    assert not any('"macro"' in p for p in prompts)
