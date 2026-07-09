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
from admorphiq.tools.targetgrid import TARGET_RES, build_target_prompt, parse_and_validate_target

LLM = Callable[[list[dict[str, str]]], str]

# Target draws fire after this many steps into the level (the probe-validated
# warmup), and are REPEATED up to _TARGET_MAX_DRAWS times, _TARGET_REDRAW_GAP
# steps apart: single-draw quality is measured stochastic (~50% good on cd82 —
# ollama fp nondeterminism varies the drawn grid), so multiple spaced draws turn
# a coin-flip into ~87% per level for two extra LLM calls at most. Each redraw
# sees the CURRENT (evolved) board, so it is a genuinely fresh sample.
_TARGET_WARMUP = 40
_TARGET_MAX_DRAWS = 3
_TARGET_REDRAW_GAP = 400
# A redraw additionally requires the tool to report its current-target pursuit
# has made no proximity improvement for this many propose-calls.
_TARGET_STALL_WINDOW = 300

# A tool whose own frame-based detect() is at least this confident OWNS the game
# (it is not retired on a stall) — its signature match is trusted over the swap.
_PRIMARY_CONF = 0.7

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
        draw_llm: LLM | None = None,
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
        # Dedicated draw callable: the target draw is measured-sensitive to LLM
        # params, so callers can align it with the probe-validated configuration.
        self.draw_llm = draw_llm or llm
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
        self._primary_owns = False
        self._prev_frame: np.ndarray | None = None
        self._prev_step: Step | None = None
        self._since_progress = 0
        self._steps = 0
        self._last_levels = 0
        self._seen_states: set[str] = set()
        self._target_draws = 0
        self._propose_errors = 0
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

    def _better_alternative_exists(self) -> bool:
        """True when some non-failed tool OTHER than the current one reports a
        strictly higher detect() right now. When nothing better exists, a stalled
        tool KEEPS RUNNING (the stall window restarts so this re-checks later) —
        swapping to a weaker tool is pure downside, measured in the deployed
        sweep which lost solid clears to churn."""
        cur_tool = self.tools.get(self._current) if self._current != "code" else None
        try:
            cur_conf = cur_tool.detect([], self._last_obs) if cur_tool is not None else 0.0
        except Exception:  # noqa: BLE001
            cur_conf = 0.0
        best_other = 0.0
        for name, t in self.tools.items():
            if name == self._current or name in self._failed:
                continue
            try:
                best_other = max(best_other, t.detect([], self._last_obs))
            except Exception:  # noqa: BLE001
                continue
        if best_other > cur_conf:
            return True
        self._since_progress = 0
        return False

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
            # The novelty key space is per-tool (each tool's state_key differs),
            # so start the new tool's progress measure from a clean seen-set.
            self._seen_states.clear()
        if self._current not in self._tried:
            self._tried.append(self._current)
        # Does the newly-picked tool own the game (high frame-based confidence)?
        self._primary_owns = False
        if self._current != "code":
            tool_obj = self.tools.get(self._current)
            if tool_obj is not None:
                try:
                    self._primary_owns = tool_obj.detect(frames, obs) >= _PRIMARY_CONF
                except Exception:  # noqa: BLE001
                    self._primary_owns = False
        # Diagnostic trace (stderr) so a bench log shows the routing decision:
        # which tool the model picked for which signature, and why it re-decided.
        print(
            f"[harness] step={self._steps} pick={self._current} "
            f"sig=[{sig.as_line()}] feedback={self._feedback!r}",
            file=sys.stderr, flush=True,
        )
        self._fill_from_current(frames, obs)

    def _state_key(self, frame: np.ndarray) -> str:
        """Progress key for novelty: the active tool's own state identity if it
        exposes ``state_key`` (graph's masked/de-aliased key), else raw hash."""
        if self._current is not None and self._current != "code":
            tool_obj = self.tools.get(self._current)
            sk = getattr(tool_obj, "state_key", None)
            if callable(sk):
                try:
                    return str(sk(frame))
                except Exception:  # noqa: BLE001
                    pass
        return base_hash(frame)

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
            except Exception as exc:  # noqa: BLE001 - a broken tool never crashes the loop
                # NEVER silent: a tool that throws every propose would silently
                # degrade the agent to single-probe actions for the whole budget.
                self._propose_errors += 1
                if self._propose_errors <= 3 or self._propose_errors % 500 == 0:
                    print(f"[harness] {self._current}.propose error "
                          f"#{self._propose_errors}: {exc}", file=sys.stderr, flush=True)
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

    def _maybe_draw_target(self, frame: np.ndarray) -> None:
        """Ask the LLM to DRAW the solved board and inject it into the active
        graph-like tool (set_target_frame) — the measured richer-goal lever.
        Draw quality is stochastic (~50% good), so up to _TARGET_MAX_DRAWS draws
        fire per level, _TARGET_REDRAW_GAP steps apart; a later draw sees the
        evolved board and OVERWRITES the previous target. Offline-safe: any
        failure/invalid draw means no injection (frame-only base kept)."""
        if self._current is None or self._target_draws >= _TARGET_MAX_DRAWS:
            return
        if self._steps < _TARGET_WARMUP + self._target_draws * _TARGET_REDRAW_GAP:
            return
        tool_obj = self.tools.get(self._current)
        inject = getattr(tool_obj, "set_target_frame", None)
        if not callable(inject):
            return
        # REDRAW gate: never overwrite a target that is still paying off —
        # blind periodic redraws measurably replaced good targets mid-pursuit
        # (harness cd82 0/4 vs single-draw probe 2/3). Only redraw once the
        # tool reports its pursuit has stalled.
        if self._target_draws >= 1:
            stalled = getattr(tool_obj, "target_stalled", None)
            if callable(stalled) and not stalled(_TARGET_STALL_WINDOW):
                return
        self._target_draws += 1  # one draw round per slot, success or not
        prompt = build_target_prompt(frame)
        for attempt in (1, 2):
            try:
                txt = self.draw_llm([{"role": "user", "content": prompt}])
            except Exception as exc:  # noqa: BLE001 - offline-safe
                print(f"[harness] target draw failed: {exc}", file=sys.stderr, flush=True)
                return
            tgt, reason = parse_and_validate_target(txt, frame)
            if tgt is None:
                print(f"[harness] target draw attempt {attempt} rejected: {reason}",
                      file=sys.stderr, flush=True)
                continue
            scale = max(1, 64 // TARGET_RES)
            inject(np.kron(tgt, np.ones((scale, scale), dtype=np.int64)), res=TARGET_RES)
            self._feedback = "target frame drawn and injected"
            print(f"[harness] TARGET injected (attempt {attempt})", file=sys.stderr, flush=True)
            return

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
            # Novelty is measured with the ACTIVE tool's OWN state identity when
            # it exposes one (graph's HUD-masked + de-aliased key), else the raw
            # frame hash. This makes "progress" mean what the tool actually
            # accomplishes — a graph exploring a click game reaches new internal
            # states even when the raw frame looks static/churny, so it is not
            # falsely stalled and retired.
            h = self._state_key(frame)
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

        self._maybe_draw_target(frame)

        # A confident primary (the tool whose own frame-based detect() is high for
        # this game) OWNS the game — it is NOT retired on a stall. The graph tool
        # clears m0r0/vc33 given the FULL budget but was retired after one tenure
        # when treated like any other tool; detect() is a reliable frame signal,
        # so trust it and let the right tool run. Low-confidence picks still swap.
        stalled = self._since_progress >= self.stall
        # Retiring the current tool on a stall is only worth it when some OTHER
        # non-failed tool detects strictly better RIGHT NOW — measured: on games
        # only the current tool can clear (deployed sweep lost lf52/lp85, both
        # solid isolated clears), swapping to a weaker tool is pure downside, and
        # no alternative tool has ever cleared a game the current one couldn't.
        need_decision = self._current is None or (
            stalled and not self._primary_owns and self._better_alternative_exists()
        )
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
