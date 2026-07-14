"""Contract tests for the vision-LLM-as-policy agent (R54, vlm_policy).

These lock the deterministic scaffolding around the multimodal model: the
labeled-image / ASCII renderer shapes, the JSON action parser + self-repair +
legal-action masking, and the policy loop's online mechanics (LLM-call
amortization via the plan queue, dead-signature avoidance, reflection capture,
level reset, offline degradation). The VLM itself is injected as a stub so the
suite runs offline; model quality is measured separately on the bench.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from admorphiq.vlm_policy import (
    ARC_PALETTE,
    VLMPolicyAgent,
    ascii_grid,
    parse_plan,
    render_frame_png,
)


def _obs(frame, state="PLAYING", avail=(1, 2, 6), levels=0):
    return SimpleNamespace(
        frame=frame,
        state=SimpleNamespace(name=state),
        available_actions=list(avail),
        levels_completed=levels,
    )


def _blank():
    return np.zeros((64, 64), dtype=np.int16)


# ----- rendering -------------------------------------------------------------
def test_render_frame_png_is_valid_png():
    """Purpose: the renderer emits a real PNG the vision model can ingest.

    Feedback: failure means the image plumbing is broken and every VLM call
    would fail — the agent is non-functional.
    """
    png = render_frame_png(_blank())
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 100


def test_palette_covers_16_colors():
    """Purpose: ARC frames use color indices 0-15; the palette must map all.

    Feedback: failure means high indices clip to one color, losing information
    the model needs to distinguish game entities.
    """
    assert len(ARC_PALETTE) == 16
    assert all(len(c) == 3 for c in ARC_PALETTE)


def test_ascii_grid_shape_and_headers():
    """Purpose: the ASCII grid gives the model an exact cross-reference to the
    image, with a row per board row plus a header.

    Feedback: failure means the textual board is misaligned, degrading the
    model's coordinate grounding.
    """
    g = _blank()
    g[0, 0] = 2
    text = ascii_grid(g)
    lines = text.splitlines()
    assert len(lines) == 65  # header + 64 rows
    assert lines[1].strip().startswith("0")  # row 0 marker


# ----- parser + self-repair --------------------------------------------------
def test_parse_plan_extracts_masked_actions():
    """Purpose: the parser returns only legal actions with valid coords.

    Feedback: failure means the agent could emit illegal/malformed actions that
    the env rejects, wasting budget.
    """
    reply = (
        'prose {"observation":"box","hypothesis":"click it",'
        '"plan":[{"action":6,"x":10,"y":20},{"action":1}]}'
    )
    plan, meta = parse_plan(reply, {1, 6}, action6_ok=True)
    assert plan == [(6, 10, 20), (1, 0, 0)]
    assert meta["hypothesis"] == "click it"


def test_parse_plan_repairs_single_action_and_string_id():
    """Purpose: self-repair handles a bare single-action dict and a string
    action id like "ACTION3".

    Feedback: failure means brittle parsing that drops valid model output.
    """
    plan, _ = parse_plan('```json\n{"action":"ACTION3"}\n```', {1, 2, 3}, False)
    assert plan == [(3, 0, 0)]


def test_parse_plan_drops_illegal_and_missing_coords():
    """Purpose: illegal action ids and ACTION6 without coordinates are dropped.

    Feedback: failure means the legal-action mask leaks, causing env errors.
    """
    reply = '{"plan":[{"action":6},{"action":9},{"action":2}]}'
    plan, _ = parse_plan(reply, {2, 6}, action6_ok=True)
    assert plan == [(2, 0, 0)]  # 6 has no coords, 9 illegal


def test_parse_plan_empty_on_garbage():
    """Purpose: unparseable replies yield an empty plan (loop falls back).

    Feedback: failure means a crash or a bogus action on model gibberish.
    """
    plan, meta = parse_plan("no json here", {1}, False)
    assert plan == []
    assert meta == {}


# ----- policy loop -----------------------------------------------------------
def test_queue_amortizes_llm_calls():
    """Purpose: queued actions run WITHOUT extra LLM calls; the loop re-plans
    only when the queue empties.

    Feedback: failure means an LLM call per action — untenable latency under the
    9h / 110-game budget.
    """
    calls = {"n": 0}

    def vlm(prompt, images):
        calls["n"] += 1
        assert images and isinstance(images[0], str)
        return '{"hypothesis":"h","plan":[{"action":6,"x":10,"y":10},{"action":1}]}'

    ag = VLMPolicyAgent(vlm=vlm)
    f = _blank()
    ag.choose_action([], _obs(f))
    ag.choose_action([], _obs(f))
    assert calls["n"] == 1  # two actions, one plan


def test_dead_signature_grows_on_no_effect():
    """Purpose: an action that leaves the frame unchanged is recorded as dead so
    the model is told to avoid it.

    Feedback: failure means the agent re-tries provably inert actions, wasting
    the efficiency-critical action budget.
    """

    def vlm(prompt, images):
        return '{"plan":[{"action":1}]}'

    ag = VLMPolicyAgent(vlm=vlm)
    f = _blank()
    ag.choose_action([], _obs(f))  # do ACTION1
    ag.choose_action([], _obs(f))  # same frame -> ACTION1 was inert
    assert (1, -1, -1) in ag._dead


def test_reflection_hypothesis_captured():
    """Purpose: the model's hypothesis becomes running reflection memory exposed
    as last_hypothesis (the bench records it).

    Feedback: failure means no online memory carries across turns.
    """

    def vlm(prompt, images):
        return '{"hypothesis":"reach the goal","plan":[{"action":1}]}'

    ag = VLMPolicyAgent(vlm=vlm)
    ag.choose_action([], _obs(_blank()))
    assert ag.last_hypothesis == "reach the goal"


def test_level_up_resets_per_level_state():
    """Purpose: on level completion the queue/dead/step state resets (mechanics
    may change between levels) while play continues.

    Feedback: failure means stale dead-signatures or history bleed across levels.
    """

    def vlm(prompt, images):
        return '{"plan":[{"action":1}]}'

    ag = VLMPolicyAgent(vlm=vlm)
    f = _blank()
    ag.choose_action([], _obs(f))
    ag.choose_action([], _obs(f))  # builds a dead signature
    assert ag._dead
    ag.choose_action([], _obs(f, levels=1))  # level up
    assert ag._dead == set()


def test_offline_degrades_without_crash():
    """Purpose: when the VLM is unreachable the agent still returns legal actions
    via the exploratory fallback.

    Feedback: failure means a network miss crashes the whole bench run.
    """

    def broken(prompt, images):
        raise ConnectionError("down")

    ag = VLMPolicyAgent(vlm=broken)
    f = _blank()
    acts = [ag.choose_action([], _obs(f)) for _ in range(4)]
    assert len(acts) == 4
    assert ag._llm_ok is False


def test_is_done_on_win_and_budget():
    """Purpose: is_done ends on WIN and on exhausting the giveup budget.

    Feedback: failure means the run never terminates or stops prematurely.
    """
    ag = VLMPolicyAgent(vlm=lambda p, i: '{"plan":[{"action":1}]}', giveup=2)
    assert ag.is_done([], _obs(_blank(), state="WIN")) is True
    ag._steps = 2
    assert ag.is_done([], _obs(_blank())) is True
