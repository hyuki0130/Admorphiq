"""LLM-as-policy: the M1-winner method family (Reki 2nd / forge 3rd), generic.

R53 research (`top_solutions_survey_20260708`) found: (a) offline model-swap is
capped by 96GB VRAM, so METHOD is the lever, not a bigger model; (b) the
strongest PUBLIC method is an LLM/VLM-as-policy loop — serialize the recent
game state, ask the model for a short JSON {reasoning, next_actions}, execute,
observe, repeat, with reflection memory + legal-action constraint + JSON
self-repair. This module is that policy core, model-agnostic (injectable chat)
and game-agnostic (frame + available-action ids only; no game ids).

It does NOT execute model-written code (that is the heavier Tufa REPL variant);
it constrains the model to emit ACTIONS from the legal set, which is safe and
was enough for M1 2nd/3rd place. The chosen actions are always validated
against the legal set before use, so a hallucinated action degrades to a
fallback rather than an illegal call.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import numpy as np

from .core import ChatFn, action_label, serialize_grid

_SIMPLE = {1, 2, 3, 4, 5, 7}  # simple action ids the policy may emit (RESET=0 excluded)

_POLICY_SYSTEM = (
    "You are playing an unknown 64x64 grid puzzle game. Each cell is an integer "
    "0-15 (a colour). You see the current frame and what recently changed. Choose "
    "the next 1-4 actions to make progress toward completing the level. Actions: "
    "ACTION1..ACTION5 and ACTION7 are simple; ACTION6 is a click needing x,y "
    "(column,row in 0..63). Reason briefly, then output ONLY one JSON object:\n"
    '{"reasoning": "<short>", "actions": [{"action": "ACTION1"}, '
    '{"action": "ACTION6", "x": 12, "y": 30}]}\n'
    "Only use actions from the AVAILABLE list. Prefer actions you expect to "
    "change the state toward the goal; avoid repeating actions that did nothing."
)


@dataclass
class PolicyDecision:
    """One policy step: the parsed action queue + provenance."""

    actions: list[tuple[str, tuple[int, int] | None]]
    reasoning: str = ""
    repaired: bool = False


@dataclass
class ReflectionMemory:
    """Bounded recent (action_label -> changed?) history fed back to the model.

    Reki's ~10-step reflection: the model is reminded which recent actions did
    nothing, so it stops re-trying inert actions (the dead-signature idea, but
    surfaced to the LLM in prose).
    """

    cap: int = 10
    events: list[tuple[str, bool]] = field(default_factory=list)

    def record(self, action_label_str: str, changed: bool) -> None:
        self.events.append((action_label_str, changed))
        if len(self.events) > self.cap:
            self.events.pop(0)

    def as_prompt(self) -> str:
        if not self.events:
            return "No actions taken yet."
        return "; ".join(
            f"{a}{'->changed' if c else '->no-change'}" for a, c in self.events
        )


def build_policy_prompt(
    frame: np.ndarray,
    available: list[int],
    memory: ReflectionMemory,
) -> list[dict[str, str]]:
    """Construct the chat messages for one policy decision (game-agnostic)."""
    avail_labels = ", ".join(action_label(a) if a < 5 else f"ACTION{a + 1}"
                             for a in available if isinstance(a, int))
    user = (
        f"CURRENT_FRAME (hex, one char/cell, 64 rows):\n{serialize_grid(frame)}\n\n"
        f"AVAILABLE actions: {avail_labels or 'ACTION1..ACTION5'}\n"
        f"RECENT actions: {memory.as_prompt()}\n\n"
        "Output the JSON object with your next 1-4 actions."
    )
    return [
        {"role": "system", "content": _POLICY_SYSTEM},
        {"role": "user", "content": user},
    ]


_JSON_OBJ = re.compile(r"\{.*\}", re.DOTALL)


def parse_policy_json(text: str, legal_simple: set[int], allow_click: bool) -> PolicyDecision:
    """Parse + REPAIR the model's JSON into a legal action queue.

    Robust to prose around the JSON and to a missing/!!broken object (self-repair:
    fall back to an empty queue so the caller uses its own default). Every action
    is validated against the legal set; illegal actions are dropped. ACTION6 keeps
    (x, y) only when clicks are allowed and coords are in range.
    """
    repaired = False
    m = _JSON_OBJ.search(text or "")
    if not m:
        return PolicyDecision(actions=[], reasoning="", repaired=True)
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        # crude repair: trim trailing commas / stray text after last brace
        snippet = m.group(0)
        snippet = re.sub(r",\s*([}\]])", r"\1", snippet)
        try:
            obj = json.loads(snippet)
            repaired = True
        except json.JSONDecodeError:
            return PolicyDecision(actions=[], reasoning="", repaired=True)

    out: list[tuple[str, tuple[int, int] | None]] = []
    for item in obj.get("actions", [])[:4]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("action", "")).upper()
        mm = re.fullmatch(r"ACTION([1-7])", name)
        if not mm:
            continue
        aid = int(mm.group(1))
        if aid == 6:
            if not allow_click:
                continue
            try:
                x, y = int(item["x"]), int(item["y"])
            except (KeyError, ValueError, TypeError):
                continue
            if not (0 <= x < 64 and 0 <= y < 64):
                continue
            out.append(("ACTION6", (x, y)))
        else:
            if aid not in legal_simple:
                continue
            out.append((f"ACTION{aid}", None))
    return PolicyDecision(
        actions=out, reasoning=str(obj.get("reasoning", ""))[:200], repaired=repaired
    )


def decide(
    chat: ChatFn,
    model: str,
    frame: np.ndarray,
    available: list[int],
    memory: ReflectionMemory,
    allow_click: bool,
    max_tokens: int = 1024,
) -> PolicyDecision:
    """One end-to-end policy step: prompt -> chat -> parse/repair -> legal queue."""
    messages = build_policy_prompt(frame, available, memory)
    text, _meta = chat(messages, model, max_tokens)
    legal_simple = {a for a in available if isinstance(a, int) and a in _SIMPLE}
    return parse_policy_json(text, legal_simple, allow_click)
