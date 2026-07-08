"""UnifiedAgent — the self-improving retry loop that IS the general agent.

Per game it holds the Claude-built generic tools plus the code path (LLM writes
Python). At each decision boundary — the action queue empties, or progress
stalls — it computes the observable signature, pulls a minimal wiki slice
(harness.context), and asks the model to choose the NEXT move: run a tool or
write code. It runs the choice, feeds the resulting transition back to every
stateful tool, and on stall re-decides with that feedback. Reason -> act ->
observe -> re-decide, until the level is cleared or the budget is spent.

The model is a single injected ``llm(messages) -> str`` callable (ollama at
runtime, a fake in tests), so the loop is fully testable offline.
"""

from __future__ import annotations

import re
import sys
from typing import Any, Callable

import numpy as np

from admorphiq.harness.context import Signature, build_context, compute_signature
from admorphiq.tools.base import Step, Tool, availability, base_hash, frame_2d, has_frame, levels_completed, state_name
from admorphiq.tools.code_agent import build_code_prompt, run_code

LLM = Callable[[list[dict[str, str]]], str]

_DECIDE_SYS = (
    "You drive an ARC-AGI-3 agent. Given the observable game signature, a wiki "
    "slice describing the available tools, the tools already tried this level, "
    "and the latest feedback, choose the NEXT move. Reply ONLY with JSON: "
    '{"mode":"tool","tool":"<name>","why":"..."} to run a tool, or '
    '{"mode":"code","why":"..."} to write Python that inspects the frame and '
    "queues actions. Prefer a tool whose signature matches; fall back to code "
    "for transform/arrangement games no tool fits."
)


class UnifiedAgent:
    """Harness-contract agent (is_done/choose_action) built on the tool loop."""

    def __init__(
        self,
        tools: list[Tool],
        llm: LLM,
        *,
        giveup: int = 8000,
        stall: int = 12,
        ctx_budget: int = 6000,
    ) -> None:
        from admorphiq.adapter import AdmorphiqAdapter
        self._convert = AdmorphiqAdapter._convert_action
        # Keep the env alive across deaths: the run loop revives on GAME_OVER
        # only when this is set, so the agent gets its full budget to learn per
        # game instead of stopping at the first avatar death (else deep-level
        # games end in tens of actions). Matches GraphFrontierAgent.
        self.restart_on_game_over = True
        self.tools = {t.name: t for t in tools}
        self.llm = llm
        self.giveup = giveup
        self.stall = stall
        self.ctx_budget = ctx_budget
        self._reset_level()

    def _reset_level(self) -> None:
        for t in self.tools.values():
            t.reset()
        self._queue: list[Step] = []
        self._transitions: list[tuple[np.ndarray, int, np.ndarray]] = []
        self._tried: list[str] = []
        self._failed: set[str] = set()
        self._current: str | None = None
        self._prev_frame: np.ndarray | None = None
        self._prev_step: Step | None = None
        self._since_progress = 0
        self._steps = 0
        self._last_levels = 0
        self._seen_states: set[str] = set()
        self._feedback = "start of level"

    def is_done(self, frames: list[Any], latest_frame: Any) -> bool:
        return state_name(latest_frame) == "WIN" or self._steps >= self.giveup

    # -- decision -------------------------------------------------------------

    def _decide(self, sig: Signature) -> tuple[str, str | None]:
        """Ask the model for the next move -> (mode, tool_name)."""
        ctx = build_context(sig, self.ctx_budget)
        available = [n for n in self.tools if n not in self._failed] or list(self.tools)
        failed = ", ".join(sorted(self._failed)) or "none"
        user = (
            f"SIGNATURE: {sig.as_line()}\n\nWIKI:\n{ctx}\n\n"
            f"TOOLS AVAILABLE: {', '.join(available)}\n"
            f"ALREADY FAILED THIS LEVEL (do NOT pick these): {failed}\n"
            f"LATEST FEEDBACK: {self._feedback}\n\nNext move?"
        )
        try:
            txt = self.llm([{"role": "system", "content": _DECIDE_SYS},
                            {"role": "user", "content": user}])
        except Exception:  # noqa: BLE001 - offline-safe: fall back to best-signature tool
            return "tool", self._signature_default(sig)
        mode_m = re.search(r'"mode"\s*:\s*"(tool|code)"', txt)
        tool_m = re.search(r'"tool"\s*:\s*"(\w+)"', txt)
        mode = mode_m.group(1) if mode_m else "tool"
        if mode == "code":
            return "code", None
        name = tool_m.group(1) if tool_m and tool_m.group(1) in self.tools else None
        # Swap-on-failure: if the model re-picks a tool already retired this level
        # (or names none), route to the best-signature tool that hasn't failed.
        if name is None or name in self._failed:
            name = self._signature_default(sig)
        return "tool", name

    def _signature_default(self, sig: Signature) -> str:
        """Highest-detect tool for the signature that has NOT failed this level.
        Falls back to the global best only if every tool has been retired."""
        frames_stub: list[Any] = []
        best, best_name = -1.0, None
        for name, t in self.tools.items():
            if name in self._failed:
                continue
            try:
                c = t.detect(frames_stub, self._last_obs)
            except Exception:  # noqa: BLE001
                c = 0.0
            if c > best:
                best, best_name = c, name
        if best_name is not None:
            return best_name
        return next(iter(self.tools))  # all retired — reuse the first as last resort

    # -- refill ---------------------------------------------------------------

    def _redecide(self, frames: list[Any], obs: Any, sig: Signature) -> None:
        """LLM picks the tool/code path, then fills the queue. Called only at a
        genuine decision boundary (first action, or a stall) — NOT on every empty
        queue, so the expensive LLM call rate stays bounded (SWA breaks prompt
        caching; see r53). A progressing tool refills via _continue with no LLM."""
        # A re-decide triggered while a tool was active means that tool stalled
        # (reached no new state for `stall` steps) — retire it for this level so
        # the loop swaps strategy instead of re-picking the proven-failed tool.
        if self._current is not None:
            self._failed.add(self._current)
        prev_current = self._current
        mode, tool = self._decide(sig)
        self._current = tool if mode == "tool" else "code"
        # On a switch to a different tool, reset it so it starts from a clean
        # model (it may hold stale/polluted state from an earlier tenure). The
        # tool then builds its model purely from its OWN upcoming actions.
        if self._current != prev_current and self._current != "code":
            active = self.tools.get(self._current)
            if active is not None:
                active.reset()
        if self._current not in self._tried:
            self._tried.append(self._current)
        # Diagnostic trace (stderr) so a bench log shows the routing decision:
        # which tool the model picked for which signature, and why it re-decided.
        print(
            f"[harness] step={self._steps} pick={self._current} "
            f"sig=[{sig.as_line()}] feedback={self._feedback!r}",
            file=sys.stderr, flush=True,
        )
        self._fill_from_current(frames, obs)

    def _continue(self, frames: list[Any], obs: Any) -> None:
        """Re-run the CURRENT tool/code path without consulting the LLM, because
        it is still making progress and the queue merely emptied."""
        self._fill_from_current(frames, obs)

    def _fill_from_current(self, frames: list[Any], obs: Any) -> None:
        simple_ids, action6 = availability(obs)
        if self._current == "code":
            steps = self._write_code(obs)
        else:
            try:
                steps = self.tools[self._current].propose(frames, obs)
            except Exception:  # noqa: BLE001 - a broken tool never crashes the loop
                steps = []
        legal = [s for s in steps if self._legal(s, simple_ids, action6)]
        self._queue = legal or self._probe(simple_ids, action6)

    def _write_code(self, obs: Any) -> list[Step]:
        frame = frame_2d(obs).astype(np.int16)
        simple_ids, action6 = availability(obs)
        valid = [_NAME[i] for i in simple_ids if i in _NAME] + (["MOUSE"] if action6 else [])
        # Give the coding LLM the recent transitions it has actually observed.
        hist = [
            {"action": _NAME.get(a, f"ACTION{a}"), "changed": bool((p != n).any())}
            for p, a, n in self._transitions[-10:]
        ]
        try:
            text = self.llm(build_code_prompt(frame, hist, valid))
            return run_code(text, frame, hist, valid).actions
        except Exception:  # noqa: BLE001 - offline-safe
            return []

    # -- main loop ------------------------------------------------------------

    def choose_action(self, frames: list[Any], latest_frame: Any) -> Any:
        from admorphiq.types import ActionType, GameAction
        obs = latest_frame
        self._last_obs = obs
        state = state_name(obs)

        levels = levels_completed(obs)
        if levels > self._last_levels:
            self._reset_level()
            self._last_levels = levels
            self._feedback = f"cleared level {levels}"

        if state in ("GAME_OVER", "NOT_PLAYED") or not has_frame(obs):
            self._prev_frame = None
            self._queue.clear()
            return self._convert(GameAction.reset())

        frame = frame_2d(obs).astype(np.int16)
        # record the transition the previous action produced -> feed every tool
        if self._prev_frame is not None and self._prev_step is not None \
                and self._prev_frame.shape == frame.shape:
            changed = bool((self._prev_frame != frame).any())
            self._transitions.append((self._prev_frame, self._prev_step[0], frame))
            self._transitions = self._transitions[-256:]
            # Feed the transition ONLY to the tool that chose the action. Feeding
            # every tool pollutes a stateful tool's model (a graph's edges, a
            # world-model's table) with actions ANOTHER tool picked — measured to
            # break the graph tool inside the harness even though it clears the
            # same game when run alone. Each tool now sees only its own actions.
            if self._current is not None and self._current != "code":
                active = self.tools.get(self._current)
                if active is not None:
                    try:
                        active.observe(self._prev_frame, self._prev_step, changed)
                    except Exception:  # noqa: BLE001
                        pass
            # Progress = reaching a NOVEL state, not merely "the frame changed".
            # A tool that keeps mutating a small set of frames (e.g. paint clicks
            # toggling regions) changes the frame every step yet makes no progress
            # toward clearing the level; counting that as progress meant the loop
            # never re-decided and wandered for the whole budget on one wrong tool.
            h = base_hash(frame)
            novel = h not in self._seen_states
            self._seen_states.add(h)
            if novel:
                self._since_progress = 0
                self._feedback = f"{self._current or 'action'} reached a new state"
            else:
                self._since_progress += 1
                self._feedback = (
                    f"{self._current or 'action'} no new state x{self._since_progress}"
                )

        need_decision = self._current is None or self._since_progress >= self.stall
        if need_decision:
            sig = compute_signature(obs, self._transitions)
            self._redecide(frames, obs, sig)
            self._since_progress = 0
        elif not self._queue:
            # Same tool is progressing; refill without paying for an LLM call.
            # Do NOT reset _since_progress — inert-action accumulation must
            # survive across refills so a stalling tool still triggers redecide.
            self._continue(frames, obs)

        step = self._queue.pop(0)
        self._steps += 1
        self._prev_frame = frame
        self._prev_step = step
        aid, xy = step
        if xy is not None:
            return self._convert(GameAction.coordinate(int(xy[0]), int(xy[1])))
        return self._convert(GameAction.simple(ActionType(aid)))

    # -- helpers --------------------------------------------------------------

    def _legal(self, step: Step, simple_ids: list[int], action6: bool) -> bool:
        aid, xy = step
        if xy is not None:
            return action6 and aid == 6
        return aid in simple_ids or (aid == 7 and not simple_ids)

    def _probe(self, simple_ids: list[int], action6: bool) -> list[Step]:
        if simple_ids:
            return [(simple_ids[0], None)]
        if action6:
            return [(6, (32, 32))]
        return [(7, None)]


_NAME = {1: "UP", 2: "DOWN", 3: "LEFT", 4: "RIGHT", 5: "SPACE", 7: "ACTION7"}
