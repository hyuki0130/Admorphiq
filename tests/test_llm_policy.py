"""Contract tests for the LLM-as-policy core (R53 / US-13, Reki M1 method)."""

from __future__ import annotations

import numpy as np

from admorphiq.ewm.llm_policy import (
    ReflectionMemory,
    build_policy_prompt,
    decide,
    parse_policy_json,
)


def test_parse_legal_actions_and_click():
    """Purpose: valid JSON yields the parsed action queue; ACTION6 keeps in-range
    (x,y) when clicks are allowed.

    Expected feedback: pass ⇒ the policy queue faithfully reflects a well-formed
    model response; fail ⇒ action parsing is broken.
    """
    txt = 'reasoning first {"reasoning":"go","actions":[{"action":"ACTION2"},{"action":"ACTION6","x":12,"y":30}]}'
    d = parse_policy_json(txt, legal_simple={1, 2, 3}, allow_click=True)
    assert d.actions == [("ACTION2", None), ("ACTION6", (12, 30))]
    assert d.reasoning == "go"


def test_illegal_and_out_of_range_actions_dropped():
    """Purpose: actions outside the legal simple set, clicks when disallowed, and
    out-of-range coords must be dropped — a hallucinated action can never reach
    the env.

    Expected feedback: pass ⇒ only legal actions survive; fail ⇒ illegal/
    hallucinated actions leak to execution.
    """
    txt = '{"actions":[{"action":"ACTION4"},{"action":"ACTION6","x":99,"y":1},{"action":"ACTION9"}]}'
    d = parse_policy_json(txt, legal_simple={1, 2}, allow_click=True)
    assert d.actions == []  # ACTION4 illegal, click OOB, ACTION9 invalid
    d2 = parse_policy_json('{"actions":[{"action":"ACTION6","x":1,"y":1}]}',
                           legal_simple={1}, allow_click=False)
    assert d2.actions == []  # clicks disallowed


def test_json_self_repair_trailing_comma_and_prose():
    """Purpose: a response with prose + a trailing-comma JSON must self-repair
    (Reki's documented feature), not crash to empty.

    Expected feedback: pass ⇒ the repaired queue is recovered and flagged; fail ⇒
    a minor formatting slip wastes the whole step.
    """
    txt = 'Here is my plan:\n{"reasoning":"x","actions":[{"action":"ACTION1"},]}'
    d = parse_policy_json(txt, legal_simple={1}, allow_click=False)
    assert d.actions == [("ACTION1", None)]
    assert d.repaired is True


def test_broken_json_degrades_to_empty_not_crash():
    """Purpose: unrecoverable output yields an empty queue (caller falls back to
    its own policy), never an exception.

    Expected feedback: pass ⇒ the game loop is robust to garbage generations;
    fail ⇒ a bad LLM response crashes the agent.
    """
    d = parse_policy_json("no json here at all", legal_simple={1}, allow_click=True)
    assert d.actions == []
    assert d.repaired is True


def test_reflection_memory_bounded_and_surfaced():
    """Purpose: reflection memory keeps only the last `cap` events and surfaces
    changed/no-change so the model can avoid inert actions (Reki reflection).

    Expected feedback: pass ⇒ memory is bounded and informative; fail ⇒ the
    prompt grows unbounded or loses the no-change signal.
    """
    mem = ReflectionMemory(cap=3)
    for i in range(5):
        mem.record(f"ACTION{i % 5 + 1}", changed=(i % 2 == 0))
    assert len(mem.events) == 3
    assert "no-change" in mem.as_prompt() or "changed" in mem.as_prompt()


def test_decide_round_trips_with_fake_llm():
    """Purpose: the end-to-end decide() wires prompt->chat->parse and only emits
    actions from the AVAILABLE set.

    Expected feedback: pass ⇒ the policy loop is correctly assembled; fail ⇒ the
    step does not produce legal actions from a well-formed model reply.
    """
    def fake_chat(messages, model, max_tokens):
        assert "AVAILABLE actions" in messages[1]["content"]
        return '{"actions":[{"action":"ACTION3"}]}', {}

    frame = np.zeros((64, 64), dtype=np.int16)
    d = decide(fake_chat, "mock", frame, available=[1, 2, 3], memory=ReflectionMemory(),
               allow_click=False)
    assert d.actions == [("ACTION3", None)]


def test_prompt_is_game_agnostic():
    """Purpose: the policy prompt must contain only frame + action ids, never a
    game id/title (generality guard).

    Expected feedback: pass ⇒ the method transfers to unseen games; fail ⇒ a
    game-specific leak crept into the prompt.
    """
    frame = np.zeros((64, 64), dtype=np.int16)
    msgs = build_policy_prompt(frame, [1, 2, 3], ReflectionMemory())
    blob = (msgs[0]["content"] + msgs[1]["content"]).lower()
    for token in ("ft09", "cd82", "sb26", "game_id", "title"):
        assert token not in blob
