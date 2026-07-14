"""Tests for the flag-gated engagement fixes (R55): action-first parsing.

Purpose: prove REPL_ACTION_FIRST parsing takes the FIRST action line so a
512-token truncation of trailing reasoning can't erase the action (sb26's
mechanism), while the default (action-last) parse stays byte-identical.

Expected feedback: a pass means the flag is a clean one-variable change — OFF
reproduces current behavior exactly, ON is truncation-robust — so its matched
run measures only the contract reorder. A failure means the default path drifted
or action-first doesn't actually recover the leading action.
"""

from __future__ import annotations

from admorphiq.repl_agent.agent import parse_model_output


def test_default_is_action_last_unchanged():
    """Default (action_first=False): only the LAST line yields a bare action."""
    raw = "MOUSE(5, 5)\nreasoning that ends without an action line"
    # last line is prose -> no action (action-last contract, unchanged)
    assert parse_model_output(raw).kind == "none"
    raw2 = "I will consider options\nUP"
    assert parse_model_output(raw2).actions == [{"action": "UP"}]


def test_action_first_takes_leading_action():
    """action_first=True: a leading action line wins; trailing prose is ignored."""
    raw = "MOUSE(5, 5)\nThe game appears to be a color-matching puzzle where..."
    p = parse_model_output(raw, action_first=True)
    assert p.kind == "actions"
    assert p.actions == [{"action": "MOUSE", "row": 5, "col": 5}]


def test_action_first_survives_truncation():
    """A reply cut off mid-reasoning still yields its first-line action."""
    raw = "UP\nThe agent needs to navigate around the red block obstacle at (36,"
    p = parse_model_output(raw, action_first=True)
    assert p.actions == [{"action": "UP"}]


def test_action_first_code_block_still_parses():
    """When the first line opens a code block (not a bare action), action-first
    falls through to the code path — code-first outputs still work."""
    raw = "```python\nprint(objects())\n```\nthen I will decide"
    p = parse_model_output(raw, action_first=True)
    assert p.kind == "code"


def test_action_first_no_action_line_is_none():
    """sb26 regression: pure prose (no action anywhere) parses to none in both
    modes — action-first doesn't fabricate an action."""
    raw = "EFFECT_PREDICT: changed\nThe top row has four colored frames and the"
    assert parse_model_output(raw, action_first=True).kind == "none"
    assert parse_model_output(raw, action_first=False).kind == "none"


def test_action_last_ignores_leading_action_first_stale():
    """Default mode must NOT pick up a leading action (the stale-action guard):
    an action only on line 1 with prose last stays unparsed under action-last."""
    raw = "MOUSE(1, 2)\nbut actually I should reconsider the whole board layout"
    assert parse_model_output(raw, action_first=False).kind == "none"
    assert parse_model_output(raw, action_first=True).actions == [
        {"action": "MOUSE", "row": 1, "col": 2}]
