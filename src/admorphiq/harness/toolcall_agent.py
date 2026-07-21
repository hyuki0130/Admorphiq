"""agent25 with NATIVE tool-calling + staged routing (R92 redesign).

The prior UnifiedAgent dumped a monolithic system prompt + regex-parsed free text
to pick a tool — which under-served the model (thin interface, no parameter docs,
one giant blob). This subclass keeps ALL of UnifiedAgent's machinery (transition
tracking, action queue, stall/giveup, observe, target-draw) and overrides ONLY the
two LLM-interaction methods to use real function-calling:

  Stage 1 (route): the model gets `select_strategy` as a function schema whose enum
  values each carry a RICH description of when to pick them, plus a minimal
  signature/stats context (no wiki blob, no kernel cards). It emits ONE tool_call.
  Stage 2 (kernel code): if it picked ``kernel_code``, a second call gives it
  `write_solver_code(code)` with the FULL kernel cards + observed transitions in the
  system prompt, and it returns the solver body as a typed argument (no fenced-code
  parsing).

Gated by the caller (the Kaggle bench builds this only when HARNESS_TOOLCALL=1); the
production UnifiedAgent is untouched, so the deployed graph_frontier card is
byte-identical.
"""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from admorphiq.harness.loop import (
    _CODE_BLOCKS_MAX,
    _NAME,
    UnifiedAgent,
)
from admorphiq.tools.base import Step
from admorphiq.tools.code_agent import (
    build_code_prompt,
    build_refine_prompt,
    run_code,
)

# Rich per-strategy descriptions — this is the routing knowledge the model needs.
_STRATEGY_DESCRIPTIONS = {
    "graph": "Frontier/BFS navigation over a state graph. Pick when a controllable "
             "avatar moves on a grid/maze and the level is reachability/pathing "
             "toward a goal cell.",
    "world_model": "Learn a tabular action->effect model online, then plan toward a "
                   "progress signal. Pick when actions have learnable deterministic "
                   "effects (push/slide/toggle state) and a sequence must be planned.",
    "paint": "Click-fills a region with a colour (flood/recolour). Pick when clicking "
             "a cell recolours an area toward a target colouring.",
    "toggle": "Click flips cell/region on/off state (lights-out class). Pick when "
              "clicks toggle states toward a uniform or target pattern.",
    "llm_goal": "Infer the transform TARGET (draw the solved board) and pursue it. "
                "Pick for arrangement/transform games where the goal is a specific "
                "final configuration.",
    "kernel_code": "Write custom Python composing the kernel library (K.*). Pick when "
                   "NO fixed tool fits: you inspect the frame + your observed "
                   "transitions, LEARN the dynamics, then compute a plan. Best for "
                   "novel mechanics needing composed perception + planning.",
}

_ROUTE_SYS = (
    "You drive an ARC-AGI-3 agent. From the observable game signature and your own "
    "observed action->effect statistics, call select_strategy exactly once to choose "
    "the NEXT strategy. Do not repeat a strategy listed as already-failed this level."
)

_WRITE_SOLVER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "write_solver_code",
        "description": (
            "Return a Python solver block for the current level. It runs in the "
            "sandbox with: current_frame (list[list[int]] 64x64 colours 0-15), "
            "transitions (your observed [{action,before,after}]), previous_frame, "
            "np, the kernel namespace K (see the system prompt's KERNEL TOOLBOX), "
            "and act(name,x=None,y=None) to QUEUE actions. Infer the goal, LEARN "
            "dynamics from transitions, then queue actions toward it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python solver body (calls act(...); may use "
                                   "K.* and transitions). No markdown fences.",
                    "minLength": 1,
                    "maxLength": 12000,
                },
            },
            "required": ["code"],
            "additionalProperties": False,
        },
    },
}


def _select_schema(strategies: list[str]) -> dict:
    enum_doc = "; ".join(f"{s}: {_STRATEGY_DESCRIPTIONS[s]}" for s in strategies
                         if s in _STRATEGY_DESCRIPTIONS)
    return {
        "type": "function",
        "function": {
            "name": "select_strategy",
            "description": "Choose the next strategy for this level. " + enum_doc,
            "parameters": {
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "enum": strategies,
                                 "description": "The strategy to run next."},
                    "reason": {"type": "string",
                               "description": "One short sentence citing the signal that drove the pick."},
                },
                "required": ["strategy"],
                "additionalProperties": False,
            },
        },
    }


class ToolCallAgent(UnifiedAgent):
    """UnifiedAgent variant that routes + writes code via native tool-calling."""

    def __init__(self, tools, llm, chat, **kw) -> None:
        super().__init__(tools, llm, **kw)
        self.chat = chat
        # Routable strategies: the fixed tools that are real peer strategies
        # (dealias/deadsig are always-on augmenters, never routed) + kernel_code.
        self._routable = [n for n in ("graph", "world_model", "paint", "toggle",
                                      "llm_goal") if n in self.tools] + ["kernel_code"]
        self._route_tool = [_select_schema(self._routable)]
        # telemetry the bench reads back
        self.route_calls = 0
        self.route_valid = 0
        self.code_calls = 0

    def _first_tool_call(self, msg: dict, fn_name: str) -> dict | None:
        for tc in msg.get("tool_calls", []):
            fn = tc.get("function", {})
            if fn.get("name") == fn_name:
                try:
                    return json.loads(fn.get("arguments") or "{}")
                except (json.JSONDecodeError, TypeError):
                    return None
        return None

    def _decide(self, sig: Any) -> tuple[str, str | None]:
        """Stage 1: native select_strategy tool-call (named, minimal context)."""
        self.route_calls += 1
        failed = ", ".join(sorted(self._failed)) or "none"
        user = (
            f"SIGNATURE: {sig.as_line()}\n"
            f"ALREADY FAILED THIS LEVEL (do not pick): {failed}\n"
            f"LATEST FEEDBACK: {self._feedback}\n"
            "Call select_strategy for the next move."
        )
        try:
            msg = self.chat(
                [{"role": "system", "content": _ROUTE_SYS},
                 {"role": "user", "content": user}],
                tools=self._route_tool,
                tool_choice={"type": "function", "function": {"name": "select_strategy"}},
            )
        except Exception:  # noqa: BLE001 - offline-safe fallback to signature tool
            return "tool", self._signature_default(sig)
        args = self._first_tool_call(msg, "select_strategy")
        strat = (args or {}).get("strategy")
        if strat in self._routable:
            self.route_valid += 1
        if strat == "kernel_code":
            return "code", None
        if strat in self.tools and strat not in self._failed:
            return "tool", strat
        return "tool", self._signature_default(sig)

    def _write_code(self, obs: Any) -> list[Step]:
        """Stage 2: native write_solver_code tool-call (full kernel cards + transitions)."""
        from admorphiq.tools.base import frame_2d
        frame = frame_2d(obs).astype(np.int16)
        if not hasattr(self, "_last_code"):
            self._last_code = None
        self._code_blocks = getattr(self, "_code_blocks", 0) + 1
        if self._code_blocks > _CODE_BLOCKS_MAX:
            self._failed.add("code")
            self._current = None
            return []
        from admorphiq.harness.loop import availability
        simple_ids, action6 = availability(obs)
        valid = [_NAME[i] for i in simple_ids if i in _NAME] + (["MOUSE"] if action6 else [])
        hist = [
            {"action": _NAME.get(a[0], f"ACTION{a[0]}"), "changed": bool((p != n).any())}
            for p, a, n in self._transitions[-10:]
        ]
        per: dict[Any, list[int]] = {}
        for p, a, n in self._transitions[-200:]:
            per.setdefault(a[0], []).append(int((p != n).sum()))
        dynamics = "\n".join(
            f"- {_NAME.get(a, f'ACTION{a}')}: {len(v)} tries, "
            f"{sum(1 for x in v if x)}/{len(v)} changed, median {int(np.median(v))} cells"
            for a, v in sorted(per.items(), key=lambda kv: str(kv[0]))
        ) or None
        trans = [(_NAME.get(a[0], f"ACTION{a[0]}"), a[1], p, n)
                 for p, a, n in self._transitions[-12:]]
        self.code_calls += 1
        try:
            if self._last_code is not None and self._last_code[1] == self._last_levels:
                prev_code, _lvl, prev_n = self._last_code
                ran = len(self._transitions) - prev_n
                changed = sum(1 for p, a, n in self._transitions[prev_n:] if (p != n).any())
                effect = (f"{ran} actions since the block ran; {changed} changed the "
                          f"frame; level NOT cleared (still level {self._last_levels}).")
                messages = build_refine_prompt(frame, prev_code, effect, valid, dynamics=dynamics)
            else:
                messages = build_code_prompt(frame, hist, valid, dynamics=dynamics)
            msg = self.chat(
                messages, tools=[_WRITE_SOLVER_SCHEMA],
                tool_choice={"type": "function", "function": {"name": "write_solver_code"}},
            )
            args = self._first_tool_call(msg, "write_solver_code")
            code = (args or {}).get("code", "")
            result = run_code(code, frame, hist, valid, transitions=trans)
            if result.actions:
                self._last_code = (result.code, self._last_levels, len(self._transitions))
            return result.actions
        except Exception:  # noqa: BLE001 - offline-safe
            return []
